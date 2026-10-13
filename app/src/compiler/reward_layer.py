"""Turn FL-AT's clause product into the task Reward Machine.

FL-AT builds the synchronous product of the clause DFAs and says which DFA state each product
state is in. Everything else lives here: hard pruning, the start merge, the rejecting well,
finals, rewards and the reward checks. FL-AT's own rewards and accepting states are ignored.
"""

import itertools
from collections import defaultdict, deque
from collections.abc import Collection, Iterable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple

import networkx as nx
from flat_tool import automatas_to_rm

from src.config import Configuration

from .reward_machine import (
    RewardMachineStructure,
    Transition,
    evaluate_boolean_guard,
    parse_boolean_guard,
)

_WELL = "W"
_FINAL = "F"
_EPSILON = 1e-9


class ClauseState(StrEnum):
    """Where one clause stands: done, still open, or broken for good."""

    SATISFIED = "satisfied"
    PENDING = "pending"
    VIOLATED = "violated"


_FINISH_REWARD = {
    ClauseState.SATISFIED: Configuration.SOFT_SATISFIED_AT_FINISH_REWARD,
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


@dataclass(frozen=True)
class RewardLayerResult:
    """The task Reward Machine, whether it has a hard goal, and the inert soft clauses.

    Soft clauses are listed by index; an inert one never changes a reward.
    """

    reward_machine: RewardMachineStructure
    hard_goal: bool
    inert_soft_clauses: tuple[int, ...]


def build_reward_machine(dfas: Sequence[dict], soft: Sequence[bool]) -> RewardLayerResult:
    """Compile the clause DFAs into one Reward Machine with hard pruning and rewards.

    ``soft[i]`` marks clause ``i`` soft; the others are hard. Without a hard goal clause the
    machine has no final state (a rule-only task). Raises ``ValueError`` on a non-total DFA,
    conflicting clauses, or a positive reward cycle.
    """
    if len(dfas) != len(soft):
        raise ValueError(
            f"Expected one DFA per clause, got {len(dfas)} DFAs for {len(soft)} clauses"
        )

    for index, dfa in enumerate(dfas):
        _check_complete(index, dfa)

    hard_clauses = [index for index, is_soft in enumerate(soft) if not is_soft]
    soft_clauses = [index for index, is_soft in enumerate(soft) if is_soft]
    hard_goal = any(_is_goal(dfas[index]) for index in hard_clauses)

    product = _clause_product(dfas)
    edges, finals = _prune_by_hard_clauses(product, hard_clauses, hard_goal)
    initial, edges = _drop_pre_step_start(edges, product, finals)
    priced, paying = _price_edges(edges, product, finals, soft_clauses)
    machine = _structure(initial, priced, finals)
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


def _clause_product(dfas: Sequence[dict]) -> _Product:
    clause_labels = [_clause_labels(dfa) for dfa in dfas]
    # FL-AT annotates its input DFAs in place, so it gets copies.
    machine = automatas_to_rm(deepcopy(list(dfas)), [1] * len(dfas))
    labels = {
        state: tuple(
            by_state[clause_state]
            for by_state, clause_state in zip(clause_labels, clause_states, strict=True)
        )
        for state, clause_states in machine["state_tuples"].items()
    }
    edges = [
        _Edge(source, guard, destination)
        for (source, guard), (destination, _) in machine["transitions"].items()
    ]
    return _Product(machine["initial_state"], machine["alphabet"], edges, labels)


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
) -> tuple[list[tuple[_Edge, float]], set[int]]:
    """Reward each edge from its destination's clause labels; also return the soft clauses paid."""
    labels = product.labels
    progress = _progress(edges, finals)
    paying: set[int] = set()
    priced = []
    for edge in edges:
        if edge.destination == _WELL:
            priced.append((edge, Configuration.WELL_REWARD))
            continue

        finishing = edge.destination in finals
        reward = progress.get(edge, 0.0)
        if finishing:
            reward += Configuration.TASK_COMPLETION_REWARD
        for clause in soft_clauses:
            term = _soft_term(
                labels[edge.source][clause], labels[edge.destination][clause], finishing
            )
            if term:
                paying.add(clause)
                reward += term
        priced.append((edge, round(reward, 9)))
    return priced, paying


def _soft_term(before: ClauseState, after: ClauseState, finishing: bool) -> float:
    """A soft clause pays when it breaks, and how it ends when the task finishes."""
    broke = before is not ClauseState.VIOLATED and after is ClauseState.VIOLATED
    term = Configuration.SOFT_BREAK_REWARD if broke else 0.0
    if finishing:
        term += _FINISH_REWARD[after]
    return term


def _progress(edges: Sequence[_Edge], finals: set[str]) -> dict[_Edge, float]:
    """Potential-based shaping: pay per step closer to a final along the longest path.

    Each cycle is collapsed to one node, so edges inside a cycle pay nothing and no cycle can
    be farmed. Edges into the well pay no progress.
    """
    if not finals:
        return {}

    inner = [edge for edge in edges if edge.destination != _WELL]
    graph = _graph((), inner)
    dag = nx.condensation(graph)
    components = dag.graph["mapping"]
    steps: dict[int, int] = {}
    for component in reversed(list(nx.topological_sort(dag))):
        if finals.isdisjoint(dag.nodes[component]["members"]):
            steps[component] = 1 + max(steps[child] for child in dag.successors(component))
        else:
            steps[component] = 0
    remaining = {state: steps[component] for state, component in components.items()}

    return {
        edge: Configuration.PROGRESS_REWARD * (remaining[edge.source] - remaining[edge.destination])
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
    initial: str, priced: Sequence[tuple[_Edge, float]], finals: set[str]
) -> RewardMachineStructure:
    """Merge the finals into one node, number the states breadth first, drop implicit loops."""
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
