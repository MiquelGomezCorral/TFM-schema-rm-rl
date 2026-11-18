"""Turn FL-AT's clause product into the task Reward Machine.

FL-AT builds the synchronous product of the clause DFAs and says which DFA state each product
state is in. Everything else lives here: hard pruning, the start merge, the rejecting well,
finals, rewards and the reward checks. FL-AT's own rewards and accepting states are ignored.
"""

import itertools
from collections import defaultdict, deque
from collections.abc import Collection, Iterable, Sequence
from copy import deepcopy
from dataclasses import dataclass, fields, replace
from enum import StrEnum
from typing import NamedTuple, Self

import networkx as nx
from flat_tool import automatas_to_rm

from src.config import Configuration

from .reward_machine import (
    EndJudgment,
    RewardMachineStructure,
    Transition,
    evaluate_boolean_guard,
    parse_boolean_guard,
)

_WELL = "W"
_FINAL = "F"
_EPSILON = 1e-9


class ClauseState(StrEnum):
    """Where one clause's DFA stands: done, still open, or unable to accept again.

    The label belongs to the DFA state. A soft rule's violated state may still be left in the
    Reward Machine when the recurrent soft penalty is on.
    """

    SATISFIED = "satisfied"
    PENDING = "pending"
    VIOLATED = "violated"


# No soft clause pays a bonus for finishing while it holds; the key stays for the lookup.
_FINISH_REWARD = {
    ClauseState.SATISFIED: 0.0,
    ClauseState.PENDING: Configuration.SOFT_PENDING_AT_FINISH_REWARD,
    ClauseState.VIOLATED: 0.0,
}


class _Edge(NamedTuple):
    source: str
    guard: str
    destination: str


@dataclass(frozen=True)
class _Product:
    initial: str
    alphabet: set[str]
    edges: list[_Edge]
    labels: dict[str, tuple[ClauseState, ...]]  # per product state, one label per clause
    # per product state, the chain-weighted stages each clause still owes (the one owed measure)
    open_steps: dict[str, tuple[int, ...]]


@dataclass(frozen=True)
class RewardLayerResult:
    """The task Reward Machine, whether it has a hard goal, and the inert soft clauses.

    Soft clauses are listed by index; an inert one never changes a reward.
    """

    reward_machine: RewardMachineStructure
    hard_goal: bool
    inert_soft_clauses: tuple[int, ...]


@dataclass(frozen=True)
class RewardSwitches:
    """Which reward parts the machine pays; a part switched off pays 0.

    The defaults are the ``Configuration`` class defaults, and the field names are its field
    names. Completion is never switched off. ``reward_end_judgment`` and ``reward_promise_cost``
    are off by default. ``soft_break_cost`` is what one soft break costs, in pay units. The
    recurrent soft penalty changes the machine's structure (see ``_rearm_violated``); the other
    switches only change the rewards (and, for the end judgment, the machine's end lines).
    """

    reward_progress: bool = Configuration.reward_progress
    reward_well: bool = Configuration.reward_well
    reward_soft_break: bool = Configuration.reward_soft_break
    reward_soft_pending: bool = Configuration.reward_soft_pending
    reward_end_judgment: bool = Configuration.reward_end_judgment
    reward_promise_cost: bool = Configuration.reward_promise_cost
    recurrent_soft_penalty: bool = Configuration.recurrent_soft_penalty
    soft_break_cost: float = Configuration.soft_break_cost

    @classmethod
    def from_config(cls, CONFIG: Configuration) -> Self:
        """The switches a run's configuration sets."""
        return cls(**{item.name: getattr(CONFIG, item.name) for item in fields(cls)})


def build_reward_machine(
    dfas: Sequence[dict], soft: Sequence[bool], switches: RewardSwitches | None = None
) -> RewardLayerResult:
    """Compile the clause DFAs into one Reward Machine with hard pruning and rewards.

    ``soft[i]`` marks clause ``i`` soft; the others are hard. With ``recurrent_soft_penalty`` a
    soft rule's violated state takes the start state's edges, so each new break pays again
    instead of once per episode. Without a hard goal clause the machine has no final
    state (a rule-only task) and progress aims at the states where no clause is pending. With
    ``reward_end_judgment`` the machine carries an end judgment for the stages still owed where
    the environment ends the episode; without it the runtime pays the flat time-limit penalty on
    a truncated step that did not terminate, and nothing on a termination. The other
    ``switches`` default to the ``Configuration`` class defaults.
    Raises ``ValueError`` on a non-total DFA, conflicting clauses, or a positive reward cycle.
    """
    switches = switches or RewardSwitches()
    if len(dfas) != len(soft):
        raise ValueError(
            f"Expected one DFA per clause, got {len(dfas)} DFAs for {len(soft)} clauses"
        )

    for index, dfa in enumerate(dfas):
        _check_complete(index, dfa)

    hard_clauses = [index for index, is_soft in enumerate(soft) if not is_soft]
    soft_clauses = [index for index, is_soft in enumerate(soft) if is_soft]
    hard_goal = any(_is_goal(dfas[index]) for index in hard_clauses)

    rearm = [switches.recurrent_soft_penalty and is_soft for is_soft in soft]
    product = _clause_product(dfas, rearm)
    edges, finals = _prune_by_hard_clauses(product, hard_clauses, hard_goal)
    initial, edges = _drop_pre_step_start(edges, product, finals)
    priced, paying = _price_edges(edges, product, finals, soft_clauses, switches)
    machine = _structure(initial, priced, finals, product, soft_clauses)
    if not switches.reward_end_judgment:
        machine = replace(machine, judgment=None)
    if _has_positive_cycle(machine):
        raise ValueError("Reward Machine has a positive reward cycle")

    inert = tuple(index for index in soft_clauses if index not in paying)
    return RewardLayerResult(machine, hard_goal, inert)


# ======================================================================================
#                                    CLAUSE STATES
# ======================================================================================


def _clause_labels(dfa: dict) -> dict[str, ClauseState]:
    """Label each DFA state: accepting, one that can still reach accepting, or neither."""
    accepting = set(dfa["accepting_states"])
    can_accept = _reaching(_graph(dfa["states"], _dfa_edges(dfa)), accepting)
    return {
        state: (
            ClauseState.SATISFIED
            if state in accepting
            else ClauseState.PENDING
            if state in can_accept
            else ClauseState.VIOLATED
        )
        for state in dfa["states"]
    }


def _check_complete(index: int, dfa: dict) -> None:
    """Reject a clause DFA with no, or several, transitions from a state on some valuation."""
    alphabet = sorted(dfa["alphabet"])
    guards = defaultdict(list)
    for (source, guard), _ in dfa["transitions"].items():
        guards[source].append(parse_boolean_guard(guard, alphabet))

    for state in dfa["states"]:
        for values in itertools.product((False, True), repeat=len(alphabet)):
            valuation = dict(zip(alphabet, values, strict=True))
            matches = sum(evaluate_boolean_guard(guard, valuation) for guard in guards[state])
            if matches != 1:
                raise ValueError(
                    f"Clause {index + 1} DFA has {matches} transitions from state {state} "
                    f"on {valuation}; every state needs exactly one per valuation"
                )


def _is_goal(dfa: dict) -> bool:
    """A goal clause is still unsatisfied after a step where no proposition is true."""
    quiet = _quiet_destination(_dfa_edges(dfa), dfa["initial_state"], dfa["alphabet"])
    return quiet not in dfa["accepting_states"]


def _dfa_edges(dfa: dict) -> list[tuple[str, str, str]]:
    return [
        (source, guard, destination) for (source, guard), destination in dfa["transitions"].items()
    ]


def _quiet_destination(
    transitions: Iterable[tuple[str, str, str]], source: str, alphabet: Collection[str]
) -> str:
    """Where ``source`` goes on a step where no proposition is true."""
    return _destination(transitions, source, alphabet, dict.fromkeys(alphabet, False))


def _destination(
    transitions: Iterable[tuple[str, str, str]],
    source: str,
    alphabet: Collection[str],
    valuation: dict[str, bool],
) -> str:
    """Where ``source`` goes on one valuation of ``alphabet``."""
    for start, guard, destination in transitions:
        if start == source and evaluate_boolean_guard(
            parse_boolean_guard(guard, alphabet), valuation
        ):
            return destination
    raise ValueError(f"State {source} has no transition on {valuation}")


def _rearm_violated(dfa: dict, by_state: dict[str, ClauseState]) -> dict:
    """Copy ``dfa`` so each violated state leaves the way the start state does.

    A violated state drops its own edges and takes the start's: a step that would not break
    the rule goes where it would from the start, and a step that would break it again stays,
    already paid. No state is added.
    """
    start = dfa["initial_state"]
    violated = {state for state, label in by_state.items() if label is ClauseState.VIOLATED}
    start_edges = [
        (guard, destination)
        for (source, guard), destination in dfa["transitions"].items()
        if source == start
    ]

    rearmed = deepcopy(dfa)
    rearmed["transitions"] = {
        (source, guard): destination
        for (source, guard), destination in dfa["transitions"].items()
        if source not in violated
    }
    for state in violated:
        for guard, destination in start_edges:
            rearmed["transitions"][(state, guard)] = (
                state if destination in violated else destination
            )
    return rearmed


def _steps_to_accept(dfa: dict) -> dict[str, int]:
    """The longest path from each DFA state to an accepting one; states that reach none are left out.

    Accepting states absorb: their outgoing edges are left out, so a rule that waits for an answer
    (``Response``) still has one. Each cycle is collapsed to one node, so no loop can be farmed.
    """
    accepting = set(dfa["accepting_states"])
    graph = _graph(dfa["states"], [edge for edge in _dfa_edges(dfa) if edge[0] not in accepting])
    dag = nx.condensation(graph.subgraph(_reaching(graph, accepting)))
    steps: dict[int, int] = {}
    for component in reversed(list(nx.topological_sort(dag))):
        if accepting.isdisjoint(dag.nodes[component]["members"]):
            steps[component] = 1 + max(steps[child] for child in dag.successors(component))
        else:
            steps[component] = 0
    return {state: steps[component] for state, component in dag.graph["mapping"].items()}


def _forced_propositions(dfa: dict, closing: bool) -> set[str]:
    """The propositions every closing (or, if not ``closing``, opening) edge of the DFA forces true.

    A closing edge takes the rule from pending to satisfied; an opening one takes it from not
    pending to pending. The DFA's own start state is skipped: it is the duplicate start that
    ``_drop_pre_step_start`` drops. A rule that different events can close or open forces
    nothing, so it hands off to no one.
    """
    alphabet = sorted(dfa["alphabet"])
    labels = _clause_labels(dfa)
    forced_per_edge = []
    for (source, guard), destination in dfa["transitions"].items():
        before, after = labels[source], labels[destination]
        if closing:
            matches = before is ClauseState.PENDING and after is ClauseState.SATISFIED
        else:
            matches = before is not ClauseState.PENDING and after is ClauseState.PENDING
        if source == dfa["initial_state"] or not matches:
            continue

        parsed = parse_boolean_guard(guard, alphabet)
        valuations = (
            dict(zip(alphabet, values, strict=True))
            for values in itertools.product((False, True), repeat=len(alphabet))
        )
        true_on = [
            valuation for valuation in valuations if evaluate_boolean_guard(parsed, valuation)
        ]
        forced_per_edge.append(
            {name for name in alphabet if true_on and all(v[name] for v in true_on)}
        )
    return set.intersection(*forced_per_edge) if forced_per_edge else set()


def _chain_weights(dfas: Sequence[dict]) -> list[int]:
    """One weight per clause: 1 plus the weights of every clause that closing it opens.

    Clause ``i`` hands off to clause ``j`` when a proposition that closes ``i`` also opens ``j``.
    Hand-off cycles are collapsed, so a cycle counts once.
    """
    closing = [_forced_propositions(dfa, closing=True) for dfa in dfas]
    opening = [_forced_propositions(dfa, closing=False) for dfa in dfas]
    hand_offs = nx.DiGraph()
    hand_offs.add_nodes_from(range(len(dfas)))
    hand_offs.add_edges_from(
        (first, second)
        for first, second in itertools.permutations(range(len(dfas)), 2)
        if closing[first] & opening[second]
    )

    chains = nx.condensation(hand_offs)
    weight: dict[int, int] = {}
    for chain in reversed(list(nx.topological_sort(chains))):
        weight[chain] = 1 + sum(weight[next_chain] for next_chain in chains.successors(chain))
    return [weight[chains.graph["mapping"][clause]] for clause in range(len(dfas))]


def _open_steps(dfa: dict, by_state: dict[str, ClauseState], weight: int) -> dict[str, int]:
    """The steps each state of the clause DFA still needs, times the clause's chain weight.

    A violated state counts 0: a broken soft rule was paid when it broke, and a broken hard rule
    ends in the well.
    """
    steps = _steps_to_accept(dfa)
    return {
        state: 0 if by_state[state] is ClauseState.VIOLATED else weight * steps[state]
        for state in dfa["states"]
    }


def _clause_product(dfas: Sequence[dict], rearm: Sequence[bool]) -> _Product:
    # Labels come from the original DFAs: the re-armed state would read as pending, and its
    # break would never be paid.
    clause_labels = [_clause_labels(dfa) for dfa in dfas]
    # FL-AT annotates its input DFAs in place, so it gets copies.
    copies = [
        _rearm_violated(dfa, by_state) if rearm_clause else deepcopy(dfa)
        for dfa, by_state, rearm_clause in zip(dfas, clause_labels, rearm, strict=True)
    ]
    # Steps are measured on the DFAs the product uses, before FL-AT touches them. Chain weights
    # come from the original DFAs, like the labels.
    chain_weights = _chain_weights(dfas)
    clause_steps = [
        _open_steps(used, by_state, weight)
        for used, by_state, weight in zip(copies, clause_labels, chain_weights, strict=True)
    ]
    machine = automatas_to_rm(copies, [1] * len(dfas))
    labels = {
        state: tuple(
            by_state[clause_state]
            for by_state, clause_state in zip(clause_labels, clause_states, strict=True)
        )
        for state, clause_states in machine["state_tuples"].items()
    }
    open_steps = {
        state: tuple(
            steps[clause_state]
            for steps, clause_state in zip(clause_steps, clause_states, strict=True)
        )
        for state, clause_states in machine["state_tuples"].items()
    }
    edges = [
        _Edge(source, guard, destination)
        for (source, guard), (destination, _) in machine["transitions"].items()
    ]
    return _Product(machine["initial_state"], machine["alphabet"], edges, labels, open_steps)


# ======================================================================================
#                                      HARD CLAUSES
# ======================================================================================


def _prune_by_hard_clauses(
    product: _Product, hard_clauses: Sequence[int], hard_goal: bool
) -> tuple[list[_Edge], set[str]]:
    """Send hard violations and dead ends to the well; return the kept edges and the finals.

    A final is a state where every hard clause holds, and only a task with a hard goal has
    any. Finals absorb, so their outgoing edges are dropped before anything else is judged.
    """
    labels = product.labels
    edges = product.edges
    dead = {
        state
        for state, states in labels.items()
        if any(states[index] is ClauseState.VIOLATED for index in hard_clauses)
    }

    finals: set[str] = set()
    if hard_goal:
        finals = {
            state
            for state, states in labels.items()
            if all(states[index] is ClauseState.SATISFIED for index in hard_clauses)
        }
        edges = [edge for edge in edges if edge.source not in finals]
        dead = set(labels) - _reaching(_graph(labels, edges), finals)

    edges = _redirect(edges, dead)
    reachable = nx.descendants(_graph(labels, edges), product.initial) | {product.initial}
    kept = [edge for edge in edges if edge.source in reachable]
    if hard_goal and not any(edge.destination in finals for edge in kept):
        raise ValueError(
            "Task has conflicting clauses: no step reaches a final state while every hard "
            "clause holds"
        )
    return kept, finals


def _redirect(edges: Iterable[_Edge], targets: set[str]) -> list[_Edge]:
    """Point every edge that enters ``targets`` at the well."""
    return [
        edge._replace(destination=_WELL) if edge.destination in targets else edge for edge in edges
    ]


# ======================================================================================
#                                      START STATE
# ======================================================================================


def _drop_pre_step_start(
    edges: list[_Edge], product: _Product, finals: set[str]
) -> tuple[str, list[_Edge]]:
    """Return the start state and the edges, without MONA's "no step yet" start when it is a twin.

    A rule clause gives the product a start that nothing re-enters and that goes to the same
    state as its idle successor on every input. Then the successor becomes the start and the old
    start and its edges are dropped; otherwise nothing changes. Rewards stay the same because no
    catalog template is broken by an idle step, so the soft terms price both states alike.
    """
    start = product.initial
    alphabet = sorted(product.alphabet)
    idle = _quiet_destination(edges, start, alphabet)
    if idle in {start, _WELL} or idle in finals or any(edge.destination == start for edge in edges):
        return start, edges

    for values in itertools.product((False, True), repeat=len(alphabet)):
        valuation = dict(zip(alphabet, values, strict=True))
        if _destination(edges, start, alphabet, valuation) != _destination(
            edges, idle, alphabet, valuation
        ):
            return start, edges
    return idle, [edge for edge in edges if edge.source != start]


# ======================================================================================
#                                        REWARDS
# ======================================================================================


def _price_edges(
    edges: Sequence[_Edge],
    product: _Product,
    finals: set[str],
    soft_clauses: Sequence[int],
    switches: RewardSwitches,
) -> tuple[list[tuple[_Edge, float]], set[int]]:
    """Reward each edge from its destination's clause labels; also return the soft clauses paid.

    An edge into the well pays the well reward plus the end charge of the state it leaves (the
    stages it still owes, ``_owed``), so a break always costs more than timing out there.
    Progress pays a soft clause where the clause starts or stops waiting. That is a proxy,
    approximate both ways: it can call a clause paid
    that changes nothing, or inert when it changes rewards. It follows the ``switches``: a part
    switched off pays 0, so a soft clause that only that part paid counts as inert. With the
    promise cost on, every edge out of a state with a hard promise open (the well and finishing
    edges too) pays it once; idle loops there become priced edges, so they stay in the machine.
    """
    labels = product.labels
    progress = (
        _progress(edges, product, finals) if switches.reward_progress else dict.fromkeys(edges, 0.0)
    )
    paying: set[int] = set()
    priced = []
    for edge in edges:
        hard, soft = _owed(product.open_steps[edge.source], soft_clauses)
        promise_cost = (
            Configuration.PROMISE_COST_REWARD if switches.reward_promise_cost and hard else 0.0
        )
        if edge.destination == _WELL:
            charge = (
                hard * Configuration.HARD_FAILED_REWARD + soft * Configuration.SOFT_FAILED_REWARD
                if switches.reward_end_judgment
                else 0.0
            )
            well = Configuration.WELL_REWARD if switches.reward_well else 0.0
            priced.append((edge, round(well + charge + promise_cost, 9)))
            continue

        finishing = edge.destination in finals
        reward = progress[edge] + promise_cost
        if finishing:
            reward += Configuration.TASK_COMPLETION_REWARD
        for clause in soft_clauses:
            before, after = labels[edge.source][clause], labels[edge.destination][clause]
            term = _soft_term(before, after, finishing, switches)
            waits = (before is ClauseState.PENDING) != (after is ClauseState.PENDING)
            if term or (waits and progress[edge]):
                paying.add(clause)
                reward += term
        priced.append((edge, round(reward, 9)))
    return priced, paying


def _soft_term(
    before: ClauseState, after: ClauseState, finishing: bool, switches: RewardSwitches
) -> float:
    """A soft clause pays when it breaks, and how it ends when the task finishes."""
    broke = before is not ClauseState.VIOLATED and after is ClauseState.VIOLATED
    term = -switches.soft_break_cost if broke and switches.reward_soft_break else 0.0
    if finishing and switches.reward_soft_pending:
        term += _FINISH_REWARD[after]
    return term


def _progress(edges: Sequence[_Edge], product: _Product, finals: set[str]) -> dict[_Edge, float]:
    """Potential-based shaping: pay per step a clause gets closer to done, charge per step back.

    Each clause counts the longest path its own DFA still has to an accepting state (see
    ``_steps_to_accept``), times its chain weight (see ``_chain_weights``): a rule that hands off
    to another is worth the chain behind it, so the middle steps of a chain pay too. A state owes
    the sum over its clauses, and finals owe nothing. A soft clause that a step breaks pays
    nothing on that step, so the break is never refunded by the stages the clause owed; the
    loops that remain sum to 0 or less, so nothing can be farmed. Edges into the well, and into
    a state that reaches no target, pay no progress. The targets are the finals; a task without
    one aims at the states where no clause is pending.
    """
    inner = [edge for edge in edges if edge.destination != _WELL]
    labels = product.labels
    targets = finals or {
        state for state, states in labels.items() if ClauseState.PENDING not in states
    }
    reachable = _reaching(_graph(labels, inner), targets)
    owed = {
        state: (0,) * len(steps) if state in finals else steps
        for state, steps in product.open_steps.items()
    }

    def paid_stages(edge: _Edge) -> int:
        return sum(
            before - after
            for before, after, label in zip(
                owed[edge.source], owed[edge.destination], labels[edge.destination], strict=True
            )
            if label is not ClauseState.VIOLATED
        )

    return {
        edge: Configuration.PROGRESS_REWARD * paid_stages(edge)
        if edge.destination in reachable
        else 0.0
        for edge in inner
    }


def _has_positive_cycle(machine: RewardMachineStructure) -> bool:
    """Bellman-Ford on the undiscounted rewards: a gain still growing after n rounds loops."""
    gain = dict.fromkeys(machine.states, 0.0)
    for _ in machine.states:
        improved = False
        for transition in machine.transitions:
            candidate = gain[transition.source] + transition.reward
            if candidate > gain[transition.destination] + _EPSILON:
                gain[transition.destination] = candidate
                improved = True
        if not improved:
            return False
    return True


# ======================================================================================
#                                        OUTPUT
# ======================================================================================


def _structure(
    initial: str,
    priced: Sequence[tuple[_Edge, float]],
    finals: set[str],
    product: _Product,
    soft_clauses: Sequence[int],
) -> RewardMachineStructure:
    """Merge the finals into one node, number the states breadth first, drop implicit loops.

    The machine also gets its end judgment, read from the numbered states.
    """
    merged = [
        (
            edge._replace(destination=_FINAL if edge.destination in finals else edge.destination),
            reward,
        )
        for edge, reward in priced
    ]
    outgoing = defaultdict(list)
    for edge, _ in merged:
        outgoing[edge.source].append(edge)

    numbers = {initial: 0}
    queue = deque([initial])
    while queue:
        for edge in sorted(outgoing[queue.popleft()], key=lambda item: item.guard):
            if edge.destination not in numbers:
                numbers[edge.destination] = len(numbers)
                queue.append(edge.destination)

    transitions = sorted(
        (
            Transition(numbers[edge.source], numbers[edge.destination], (edge.guard,), reward)
            for edge, reward in merged
            if edge.source != edge.destination or reward != 0
        ),
        key=lambda item: (item.source, item.condition),
    )
    return RewardMachineStructure(
        states=tuple(range(len(numbers))),
        initial_state=0,
        final_state=numbers.get(_FINAL),
        rejecting_states=(numbers[_WELL],) if _WELL in numbers else (),
        transitions=tuple(transitions),
        judgment=_end_judgment(numbers, product, soft_clauses),
    )


def _owed(steps: tuple[int, ...], soft_clauses: Sequence[int]) -> tuple[int, int]:
    """The hard and soft stages a state still owes: the stages the progress pay counts.

    ``steps`` is one product state's ``open_steps``. The end judgment and the end charge on the
    edges into the well both charge by this count, not by the clauses still open.
    """
    soft = sum(steps[clause] for clause in soft_clauses)
    return sum(steps) - soft, soft


def _end_judgment(
    numbers: dict[str, int], product: _Product, soft_clauses: Sequence[int]
) -> EndJudgment:
    """Split the numbered states into accepting ones and ones that still owe stages.

    A state is accepting when it owes nothing, that is, no clause is pending. A soft rule broken
    for good was paid when it broke, so it counts as kept; the well and the final are in neither
    list. In a machine with a final every other state has a hard clause open (the goal or a hard
    rule), so none accepts.
    """
    accepting: list[int] = []
    pending: list[tuple[int, int, int]] = []
    for state, number in numbers.items():
        if state in {_WELL, _FINAL}:
            continue
        hard, soft = _owed(product.open_steps[state], soft_clauses)
        if hard or soft:
            pending.append((number, hard, soft))
        else:
            accepting.append(number)
    return EndJudgment(
        tuple(accepting),
        tuple(pending),
        Configuration.HARD_FAILED_REWARD,
        Configuration.SOFT_FAILED_REWARD,
    )


# ======================================================================================
#                                        GRAPHS
# ======================================================================================


def _graph(nodes: Iterable[str], edges: Iterable[tuple[str, str, str]]) -> nx.DiGraph:
    """The directed graph of ``(source, guard, destination)`` edges plus the given ``nodes``."""
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((source, destination) for source, _, destination in edges)
    return graph


def _reaching(graph: nx.DiGraph, targets: set[str]) -> set[str]:
    """The targets and every node with a path to one of them."""
    return targets.union(*(nx.ancestors(graph, target) for target in targets))
