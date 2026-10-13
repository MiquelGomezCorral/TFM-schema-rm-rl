"""Turn FL-AT's clause product into the task Reward Machine.

FL-AT builds the synchronous product of the clause DFAs and says which DFA state each product
state is in. Everything else lives here: hard pruning, the rejecting well, finals, rewards and
the reward checks. FL-AT's own rewards and accepting states are ignored.
"""

import itertools
from collections import defaultdict, deque
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple

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

    Without a hard goal clause the machine has no final state (a rule-only task).

    Args:
        dfas (Sequence[dict]): One MONA DFA per clause, in clause order.
        soft (Sequence[bool]): Whether each clause is soft; the others are hard.

    Returns:
        RewardLayerResult: The machine, whether the task has a hard goal, and the soft
            clauses without any reward effect.

    Raises:
        ValueError: A clause DFA is not total, the clauses conflict (no step reaches a final
            state while every hard clause holds) or the rewards contain a positive cycle.
    """
    for index, dfa in enumerate(dfas):
        _check_complete(index, dfa)

    hard_clauses = [index for index, is_soft in enumerate(soft) if not is_soft]
    soft_clauses = [index for index, is_soft in enumerate(soft) if is_soft]
    hard_goal = any(_is_goal(dfas[index]) for index in hard_clauses)

    product = _clause_product(dfas)
    edges, finals = _prune_by_hard_clauses(product, hard_clauses, hard_goal)
    priced, paying = _price_edges(edges, product, finals, soft_clauses)
    machine = _structure(product.initial, priced, finals)
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
    predecessors = _adjacency(
        (destination, source) for (source, _), destination in dfa["transitions"].items()
    )
    can_accept = _closure(accepting, predecessors)
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
    transitions = (
        (source, guard, destination) for (source, guard), destination in dfa["transitions"].items()
    )
    quiet = _quiet_destination(transitions, dfa["initial_state"], dfa["alphabet"])
    return quiet not in dfa["accepting_states"]


def _quiet_destination(
    transitions: Iterable[tuple[str, str, str]], source: str, alphabet: Collection[str]
) -> str:
    """Where ``source`` goes on a step where no proposition is true."""
    quiet = dict.fromkeys(alphabet, False)
    for start, guard, destination in transitions:
        if start == source and evaluate_boolean_guard(parse_boolean_guard(guard, alphabet), quiet):
            return destination
    raise ValueError(f"State {source} has no transition when no proposition is true")


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
    violated = {
        state
        for state, states in labels.items()
        if any(states[index] is ClauseState.VIOLATED for index in hard_clauses)
    }
    edges = _redirect(product.edges, violated)

    finals: set[str] = set()
    if hard_goal:
        finals = {
            state
            for state, states in labels.items()
            if all(states[index] is ClauseState.SATISFIED for index in hard_clauses)
        }
        edges = [edge for edge in edges if edge.source not in finals]
        can_finish = _closure(finals, _adjacency((e.destination, e.source) for e in edges))
        edges = _redirect(edges, set(labels) - can_finish)

    reachable = _closure({product.initial}, _adjacency((e.source, e.destination) for e in edges))
    kept = [edge for edge in edges if edge.source in reachable]
    if hard_goal and not any(edge.destination in finals for edge in kept):
        raise ValueError(
            "Task has conflicting clauses: no step reaches a final state while every hard "
            "clause holds"
        )
    return kept, finals & reachable


def _redirect(edges: Iterable[_Edge], targets: set[str]) -> list[_Edge]:
    """Point every edge that enters ``targets`` at the well."""
    return [
        edge._replace(destination=_WELL) if edge.destination in targets else edge for edge in edges
    ]


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
    progress = _progress(edges, finals, product)
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


def _progress(edges: Sequence[_Edge], finals: set[str], product: _Product) -> dict[_Edge, float]:
    """Potential-based shaping: pay per step closer to a final along the longest path.

    Each cycle is collapsed to one node, so edges inside a cycle pay nothing and no cycle can
    be farmed. Edges into the well pay no progress.
    """
    if not finals:
        return {}

    inner = [edge for edge in edges if edge.destination != _WELL]
    successors = _adjacency((edge.source, edge.destination) for edge in inner)
    states = set(successors) | {edge.destination for edge in inner}
    components = _components(states, successors)
    component_of = {state: index for index, members in enumerate(components) for state in members}

    remaining: dict[str, int] = {}
    for index, members in enumerate(components):
        if finals.isdisjoint(members):
            leaving = {
                child
                for node in members
                for child in successors.get(node, ())
                if component_of[child] != index
            }
            steps = 1 + max(remaining[child] for child in leaving)
        else:
            steps = 0
        remaining.update(dict.fromkeys(members, steps))

    # A rule clause's pre-step start (never re-entered) scores like its quiet successor, so an
    # idle first step pays 0.
    start = product.initial
    quiet = _quiet_destination(edges, start, product.alphabet)
    returns_to_start = start in _closure(successors.get(start, ()), successors)
    if quiet != _WELL and not returns_to_start:
        remaining[start] = remaining[quiet]

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


def _adjacency(pairs: Iterable[tuple[str, str]]) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for source, destination in pairs:
        adjacency[source].add(destination)
    return adjacency


def _closure(starts: Iterable[str], neighbors: Mapping[str, Iterable[str]]) -> set[str]:
    """The states reachable from ``starts`` through ``neighbors``, starts included."""
    seen = set(starts)
    queue = deque(seen)
    while queue:
        for neighbor in neighbors.get(queue.popleft(), ()):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def _components(states: Iterable[str], successors: Mapping[str, Iterable[str]]) -> list[list[str]]:
    """Strongly connected components (Tarjan), each listed after every component it reaches."""
    order: dict[str, int] = {}
    lowest: dict[str, int] = {}
    stack: list[str] = []
    work: list[tuple[str, Iterator[str]]] = []  # the depth-first path with each node's children
    components: list[list[str]] = []

    def visit(state: str) -> None:
        order[state] = lowest[state] = len(order)
        stack.append(state)
        work.append((state, iter(successors.get(state, ()))))

    for root in states:
        if root in order:
            continue
        visit(root)
        while work:
            node, children = work[-1]
            child = next(children, None)
            if child is None:
                work.pop()
                if work:
                    parent = work[-1][0]
                    lowest[parent] = min(lowest[parent], lowest[node])
                if lowest[node] == order[node]:
                    components.append(_pop_component(stack, node))
            elif child not in order:
                visit(child)
            elif child in stack:
                lowest[node] = min(lowest[node], order[child])
    return components


def _pop_component(stack: list[str], root: str) -> list[str]:
    start = stack.index(root)
    component = stack[start:]
    del stack[start:]
    return component
