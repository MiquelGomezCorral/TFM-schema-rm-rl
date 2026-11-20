"""Exact clues for the critic, computed from a candidate's clauses, clause DFAs and machine.

Three clues, no LLM call: each clause in plain words, the hard clauses the other hard clauses
already imply, and the events every finishing run contains. They know the clauses, not the level:
a path they show may be impossible there.

Every search walks the edges of a DFA, a product of DFAs or the machine, never the event sets: a
guard becomes cubes (the events it needs and the events it rules out, as bit masks over the sorted
propositions), and an edge is taken with its cheapest event set, the one holding exactly the
events it needs. That finds what a search over every event set finds, in the same order, without
the 2^n event sets per state.
"""

from collections import deque
from collections.abc import Callable, Iterable, Sequence

from src.config import PriorityLevel

from .pipeline import ClauseProposal
from .reward_layer import ClauseState, clause_labels
from .reward_machine import RewardMachineStructure, parse_boolean_guard

PLAIN = {
    "Existence": "{0} happens at least once",
    "ExistenceTwo": "{0} happens on at least two different steps",
    "Absence": "{0} never happens",
    "Response": "every {0} is followed by {1}, on that step or later",
    "ChainResponse": "every {0} is followed by {1} on the very next step",
    "Precedence": "{1} may not happen before the first {0}",
    "RespondedExistence": "if {0} happens, {1} happens too, before or after",
    "NotCoExistence": "{0} and {1} never both happen in one episode",
}

# A machine has up to 2^n transitions per state over n propositions: above this there is no block.
MAX_PROPOSITIONS = 12

# One way to take a step: (events it needs, events it rules out, state it leads to). A state is a
# DFA state name or a machine state number.
Edge = tuple[int, int, str | int]
Edges = dict[str | int, list[Edge]]


# ======================================================================================
#                                    GUARDS AND EDGES
# ======================================================================================


class _Guards:
    """Reads guards as cubes over the sorted propositions: (events needed, events ruled out)."""

    def __init__(self, alphabet: Sequence[str]):
        self.alphabet = list(alphabet)
        self.literals: dict[str, tuple[int, int]] = {}
        for number, proposition in enumerate(self.alphabet):
            name = proposition.lower()
            self.literals[name] = (1 << number, 0)
            self.literals[f"!{name}"] = (0, 1 << number)

    def table(self, rows: Iterable[tuple[str | int, str, str | int]]) -> Edges:
        """The edges of each state, from (source, guard, destination) rows."""
        edges: Edges = {}
        for source, guard, destination in rows:
            for needed, ruled_out in self.cubes(guard):
                edges.setdefault(source, []).append((needed, ruled_out, destination))
        return edges

    def cubes(self, guard: str) -> list[tuple[int, int]]:
        """The guard as an or of cubes; a cube that needs and rules out one event is dropped."""
        needed = ruled_out = 0
        for part in guard.lower().split("&"):
            literal = self.literals.get(part.strip())
            if literal is None:
                # A compiled guard is a plain conjunction; only others need the shared parser,
                # which reads the 175,099 guards of an 11-proposition machine in 1.7 s, not 0.3 s.
                return self._or_of_cubes(parse_boolean_guard(guard, self.alphabet), False)
            needed |= literal[0]
            ruled_out |= literal[1]
        return [] if needed & ruled_out else [(needed, ruled_out)]

    def _or_of_cubes(self, expression, negated: bool) -> list[tuple[int, int]]:
        operator = expression[0]
        if operator == "constant":
            return [(0, 0)] if expression[1] != negated else []
        if operator == "atom":
            return [self.literals[f"!{expression[1]}" if negated else expression[1]]]
        if operator == "not":
            return self._or_of_cubes(expression[1], not negated)

        left, right = (self._or_of_cubes(part, negated) for part in expression[1:])
        if (operator == "or") != negated:
            return left + right
        return [
            (needed | other_needed, ruled_out | other_ruled_out)
            for needed, ruled_out in left
            for other_needed, other_ruled_out in right
            if not (needed | other_needed) & (ruled_out | other_ruled_out)
        ]


class _Dfa:
    """One clause DFA with its guards read and each state labeled."""

    def __init__(self, dfa: dict, guards: _Guards):
        self.initial = dfa["initial_state"]
        self.labels = clause_labels(dfa)
        self.edges = guards.table(
            (source, guard, destination)
            for (source, guard), destination in dfa["transitions"].items()
        )
        # The empty trace is no run: the start takes the label of the state after one empty step.
        quiet = next(
            (end for needed, _, end in self.edges.get(self.initial, ()) if not needed), None
        )
        if quiet is None:
            raise ValueError("incomplete DFA")
        self.quiet = quiet
        self.start_label = self.labels[quiet]

    def label(self, state: str) -> ClauseState:
        return self.start_label if state == self.initial else self.labels[state]


# ======================================================================================
#                                         PATHS
# ======================================================================================


def _rank(edge: Edge) -> tuple[int, list[int]]:
    """Where a search over event sets, smallest first, meets the edge's cheapest event set."""
    needed = edge[0]
    return needed.bit_count(), [
        number for number in range(needed.bit_length()) if needed >> number & 1
    ]


def _shortest(edges: Edges, start: str | int, goal: Callable, singles: bool) -> list[int] | None:
    """The shortest path of event sets from ``start`` to a state where ``goal`` holds, or None.

    A state's edges go smallest event set first, so the first path found is the one a search over
    every event set finds. ``singles`` allows at most one event per step.
    """
    seen = {start: None}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        if goal(state) and seen[state] is not None:
            path = []
            while seen[state] is not None:
                state, events = seen[state]
                path.append(events)
            return path[::-1]
        usable = [
            edge for edge in edges.get(state, ()) if not singles or edge[0] & (edge[0] - 1) == 0
        ]
        for needed, _, destination in sorted(usable, key=_rank):
            if destination not in seen:
                seen[destination] = (state, needed)
                queue.append(destination)
    return None


def _walk(edges: Edges, start: str | int, goal: Callable) -> list[int] | None:
    """The shortest path with one event per step, else with any event sets."""
    return _shortest(edges, start, goal, True) or _shortest(edges, start, goal, False)


# ======================================================================================
#                                         CLUES
# ======================================================================================


def _name(clause: ClauseProposal) -> str:
    return f"{clause.pattern}({', '.join(clause.propositions)})"


def _events(events: int, alphabet: Sequence[str]) -> list[str]:
    return sorted(name for number, name in enumerate(alphabet) if events >> number & 1)


def _path_text(path: Sequence[int], alphabet: Sequence[str]) -> str:
    return ", then ".join(
        "+".join(_events(events, alphabet)) or "(a step with none of these events)"
        for events in path
    )


def _plain_line(number: int, clause: ClauseProposal, dfa: _Dfa, alphabet: Sequence[str]) -> str:
    def reach(start: str, label: ClauseState):
        return _walk(dfa.edges, start, lambda state: dfa.label(state) is label)

    broken = reach(dfa.initial, ClauseState.VIOLATED)
    if broken:
        how = f"broken for good by: {_path_text(broken, alphabet)}"
    elif dfa.start_label is ClauseState.PENDING:
        how = "owed from the start until it is met"
    else:
        owed = reach(dfa.quiet, ClauseState.PENDING)
        how = f"owed after: {_path_text(owed, alphabet)}" if owed else "never owed"

    if clause.priority is not PriorityLevel.HARD:
        cost = "soft: a break costs a penalty and the episode goes on"
    elif broken:
        cost = "a hard break fails the episode"
    else:
        cost = "hard: still owed when the episode ends = failed"

    meaning = PLAIN[clause.pattern].format(*clause.propositions)
    return f"- R{number} {clause.priority.value} {_name(clause)}: {meaning}; {how}; {cost}."


def _successors(automata: Sequence[_Dfa], state: tuple[str, ...]) -> set[tuple[str, ...]]:
    """The product states one event set leads to: one edge of each DFA, all holding at once."""
    found = set()

    def extend(clause: int, needed: int, ruled_out: int, ends: tuple[str, ...]) -> None:
        if clause == len(state):
            found.add(ends)
            return
        for edge_needed, edge_ruled_out, destination in automata[clause].edges[state[clause]]:
            if not (needed | edge_needed) & (ruled_out | edge_ruled_out):
                extend(
                    clause + 1,
                    needed | edge_needed,
                    ruled_out | edge_ruled_out,
                    (*ends, destination),
                )

    extend(0, 0, 0, ())
    return found


def _unmet_sets(automata: Sequence[_Dfa], bits: Sequence[int], need_none: bool) -> set[int]:
    """Which clauses are unsatisfied, in each state of their product reached after a step.

    Each set is a bit mask; ``bits`` gives each DFA's bit. The start only counts as a state
    reached when it is its own successor. Stops early once every mask with one clause unsatisfied
    has been found (and the mask with none, when ``need_none``): the search can then say nothing
    new.
    """
    unmet = [
        {state: 0 if dfa.label(state) is ClauseState.SATISFIED else bit for state in dfa.labels}
        for dfa, bit in zip(automata, bits, strict=True)
    ]
    wanted = {*bits, *([0] if need_none else [])}

    def unsatisfied(state: tuple[str, ...]) -> int:
        mask = 0
        for number, name in enumerate(state):
            mask |= unmet[number][name]
        return mask

    start = tuple(dfa.initial for dfa in automata)
    reached = _successors(automata, start)
    queue = deque(reached)
    masks = {unsatisfied(state) for state in reached}
    while queue and not wanted <= masks:
        for state in _successors(automata, queue.popleft()):
            if state not in reached and state != start:
                reached.add(state)
                queue.append(state)
                masks.add(unsatisfied(state))
    return masks


def _groups(clauses: Sequence[ClauseProposal], hard: Sequence[int]) -> list[list[int]]:
    """Split the hard clauses (as positions in ``hard``) into groups that share no proposition."""
    groups: list[tuple[set[str], list[int]]] = []
    for position, index in enumerate(hard):
        propositions, members = set(clauses[index].propositions), [position]
        apart = []
        for group_propositions, group_members in groups:
            if group_propositions & propositions:
                propositions |= group_propositions
                members += group_members
            else:
                apart.append((group_propositions, group_members))
        groups = [*apart, (propositions, members)]
    return [members for _, members in groups]


def _implied(unmet_sets: Sequence[set[int]], groups: Sequence[Sequence[int]]) -> list[int]:
    """The positions of the hard clauses the others imply, going from the last to the first.

    A kept clause is needed when some state has it unsatisfied alone: its own group reaches such a
    state, and every other group reaches one with all its kept clauses satisfied. A clause that is
    not needed leaves the kept set, so two copies of a rule flag only the later one.
    """
    group_of = {position: number for number, group in enumerate(groups) for position in group}
    kept = (1 << len(group_of)) - 1
    implied = []
    for position in reversed(range(len(group_of))):
        bit = 1 << position
        alone = any(unmet & kept == bit for unmet in unmet_sets[group_of[position]])
        others_met = all(
            any(unmet & kept == 0 for unmet in found)
            for number, found in enumerate(unmet_sets)
            if number != group_of[position]
        )
        if not (alone and others_met):
            implied.append(position)
            kept ^= bit
    return implied


def _stays(dfa: _Dfa) -> bool:
    """Whether every state a step can lead to has a step that keeps it there."""
    ends = {end for edges in dfa.edges.values() for _, _, end in edges}
    return all(any(end == state for _, _, end in dfa.edges[state]) for state in ends)


def _redundant_lines(
    clauses: Sequence[ClauseProposal], automata: Sequence[_Dfa], hard: Sequence[int]
) -> list[str]:
    """Name each hard clause the other hard clauses already imply, or say there is none.

    A clause is implied when no state of the hard clauses' product, reached after at least one
    step, has every other kept hard clause satisfied and this one not. Hard clauses that share no
    proposition (directly or through others) are searched as separate smaller products. That is
    exact when each DFA can stay in any state it reaches, since then every group can wait in its
    state until the others get where they are; if one cannot, all the clauses form one group.
    """
    stays = all(_stays(automata[i]) for i in hard)
    groups = _groups(clauses, hard) if stays else [list(range(len(hard)))]
    unmet_sets = [
        _unmet_sets([automata[hard[p]] for p in group], [1 << p for p in group], len(groups) > 1)
        for group in groups
    ]

    implied = [hard[position] for position in _implied(unmet_sets, groups)]
    if not implied:
        return ["Redundant: none."]
    return [
        f"Redundant: R{i + 1} {_name(clauses[i])} is already implied by the other hard rules: "
        "every run they accept keeps it, so the machine accepts the same runs without it."
        for i in reversed(implied)
    ]


def _finishes_without(edges: Edges, start: int, final: int, event: int) -> bool:
    """Whether the machine can go from ``start`` to ``final`` on edges that do not need ``event``."""
    seen, stack = {start}, [start]
    while stack:
        for needed, _, destination in edges.get(stack.pop(), ()):
            if needed & event:
                continue
            if destination == final:
                return True
            if destination not in seen:
                seen.add(destination)
                stack.append(destination)
    return False


def _forced_line(machine: RewardMachineStructure, guards: _Guards) -> str | None:
    """Name the events every finishing run contains, or None when the machine cannot finish.

    An event is forced when the final state cannot be reached on steps that leave it out. They
    come in the order of the shortest finishing path, then by name. A machine keeps one guard per
    transition, and its guards never overlap, so an edge can be taken without an event exactly
    when its cube does not need it.
    """
    final = machine.final_state
    if final is None:
        return None

    start = machine.initial_state
    edges = guards.table(
        (transition.source, transition.condition[0], transition.destination)
        for transition in machine.transitions
    )
    path = _walk(edges, start, lambda state: state == final)
    if not path:
        return None

    forced = [
        name
        for number, name in enumerate(guards.alphabet)
        if not _finishes_without(edges, start, final, 1 << number)
    ]
    first_step: dict[str, int] = {}
    for number, events in enumerate(path):
        for name in _events(events, guards.alphabet):
            first_step.setdefault(name, number)
    forced.sort(key=lambda event: (first_step[event], event))

    return f"Every way to finish includes: {', '.join(forced) if forced else 'no single event'}."


def critic_clues(
    clauses: Sequence[ClauseProposal],
    dfas: Sequence[dict],
    reward_machine: RewardMachineStructure,
) -> str:
    """Write the clue block for one candidate, or "" when there is none to give.

    Args:
        clauses (Sequence[ClauseProposal]): The candidate's clauses, in proposal order.
        dfas (Sequence[dict]): One compiled DFA per clause, in the same order.
        reward_machine (RewardMachineStructure): The machine those clauses compiled to.

    Returns:
        str: One plain-words line per clause, then the redundant hard clauses (only with two or
        more hard clauses), then the events every finishing run contains (only with a final state
        that can be reached). Empty without clauses, or over ``MAX_PROPOSITIONS`` propositions.
    """
    alphabet = sorted({proposition for clause in clauses for proposition in clause.propositions})
    if not clauses or len(alphabet) > MAX_PROPOSITIONS:
        return ""

    guards = _Guards(alphabet)
    automata = [_Dfa(dfa, guards) for dfa in dfas]

    lines = ["Rules in plain words:"]
    for number, (clause, automaton) in enumerate(zip(clauses, automata, strict=True), start=1):
        lines.append(_plain_line(number, clause, automaton, alphabet))

    hard = [i for i, clause in enumerate(clauses) if clause.priority is PriorityLevel.HARD]
    if len(hard) > 1:
        lines += _redundant_lines(clauses, automata, hard)

    forced_line = _forced_line(reward_machine, guards)
    if forced_line:
        lines.append(forced_line)
    return "\n".join(lines)
