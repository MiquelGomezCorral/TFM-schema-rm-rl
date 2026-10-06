"""Normalize MONA DFAs and serialize compact executable Reward Machines."""

import re
from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import product

from src.config import Configuration, PriorityLevel
from src.engines.structured import SUPPORTED_TEMPLATES

TOKEN = re.compile(r"\s*([a-z_][a-z0-9_]*|[!~&|()])", re.IGNORECASE)
Valuation = tuple[bool, ...]


@dataclass(frozen=True)
class Transition:
    """One disjoint executable Reward Machine transition."""

    source: int
    destination: int
    condition: tuple[str, ...]
    reward: float


@dataclass(frozen=True)
class RewardMachineStructure:
    """A numeric Reward Machine with one success final state."""

    states: tuple[int, ...]
    initial_state: int
    final_state: int
    rejecting_states: tuple[int, ...]
    transitions: tuple[Transition, ...]


@dataclass(frozen=True)
class _NormalizedDFA:
    propositions: tuple[str, ...]
    valuations: tuple[Valuation, ...]
    states: tuple[int, ...]
    initial_state: int
    final_state: int
    transitions: dict[tuple[int, Valuation], int]


# ======================================================================================
#                                    BOOLEAN GUARDS
# ======================================================================================


class _GuardParser:
    def __init__(self, guard: str, propositions: set[str]) -> None:
        self.tokens = self._tokenize(guard)
        self.position = 0
        self.propositions = propositions

    def parse(self):
        expression = self._parse_or()
        if self.position != len(self.tokens):
            raise ValueError(f"Unexpected guard token '{self.tokens[self.position]}'")
        return expression

    @staticmethod
    def _tokenize(guard: str) -> list[str]:
        tokens: list[str] = []
        position = 0
        while position < len(guard):
            if not guard[position:].strip():
                break
            match = TOKEN.match(guard, position)
            if match is None:
                raise ValueError(f"Invalid Boolean guard near '{guard[position:]}'")
            lexeme = match.group(1).lower()
            tokens.append("!" if lexeme == "~" else lexeme)
            position = match.end()
        if not tokens:
            return ["true"]
        return tokens

    def _parse_or(self):
        expression = self._parse_and()
        while self._accept("|"):
            expression = ("or", expression, self._parse_and())
        return expression

    def _parse_and(self):
        expression = self._parse_not()
        while self._accept("&"):
            expression = ("and", expression, self._parse_not())
        return expression

    def _parse_not(self):
        if self._accept("!"):
            return ("not", self._parse_not())
        return self._parse_primary()

    def _parse_primary(self):
        if self._accept("("):
            expression = self._parse_or()
            self._expect(")")
            return expression
        if self.position >= len(self.tokens):
            raise ValueError("Boolean guard ended unexpectedly")
        lexeme = self.tokens[self.position]
        self.position += 1
        if lexeme in {"true", "false"}:
            return ("constant", lexeme == "true")
        if lexeme not in self.propositions:
            raise ValueError(f"Boolean guard uses undeclared proposition '{lexeme}'")
        return ("atom", lexeme)

    def _accept(self, token: str) -> bool:
        if self.position < len(self.tokens) and self.tokens[self.position] == token:
            self.position += 1
            return True
        return False

    def _expect(self, token: str) -> None:
        if not self._accept(token):
            raise ValueError(f"Expected guard token '{token}'")


def _evaluate(expression, valuation: dict[str, bool]) -> bool:
    operator = expression[0]
    if operator == "constant":
        return expression[1]
    if operator == "atom":
        return valuation[expression[1]]
    if operator == "not":
        return not _evaluate(expression[1], valuation)
    if operator == "and":
        return _evaluate(expression[1], valuation) and _evaluate(expression[2], valuation)
    if operator == "or":
        return _evaluate(expression[1], valuation) or _evaluate(expression[2], valuation)
    raise ValueError(f"Unsupported Boolean operator '{operator}'")


def parse_boolean_guard(guard: str, propositions: Sequence[str] | set[str]):
    """Parse a Boolean guard for consumers outside the numeric compiler."""
    names = {str(proposition).lower() for proposition in propositions}
    return _GuardParser(str(guard).lower(), names).parse()


def evaluate_boolean_guard(expression, valuation: dict[str, bool]) -> bool:
    """Evaluate a parsed guard against one complete valuation."""
    return _evaluate(
        expression, {str(key).lower(): bool(value) for key, value in valuation.items()}
    )


# ======================================================================================
#                                   CLAUSE MACHINES
# ======================================================================================


def normalize_reward_machine(
    dfa: dict,
    pattern: str,
    proposition_ids: tuple[str, ...],
    priority: PriorityLevel,
) -> RewardMachineStructure:
    """Minimize one DFA and add one-time completion rewards."""
    _validate_clause_shape(pattern, proposition_ids, priority)

    normalized = _normalize_dfa(dfa, proposition_ids)
    rejecting_states = _states_without_path_to_final(normalized)
    preferred_state = None
    reverse_state = None

    if pattern == "Precedence" and priority is PriorityLevel.HARD:
        _validate_hard_precedence(normalized, rejecting_states)
    else:
        if rejecting_states:
            raise ValueError("A non-hard completion DFA cannot contain a rejecting state")
        if pattern == "Existence":
            _validate_existence(normalized)
        elif pattern == "ExistenceTwo":
            _validate_existence_two(normalized)
        else:
            preferred_state, reverse_state = _validate_non_hard_precedence(normalized)

    return RewardMachineStructure(
        states=normalized.states,
        initial_state=normalized.initial_state,
        final_state=normalized.final_state,
        rejecting_states=tuple(sorted(rejecting_states)),
        transitions=_reward_transitions(
            normalized, pattern, priority, preferred_state, reverse_state
        ),
    )


def _validate_clause_shape(
    pattern: str, proposition_ids: tuple[str, ...], priority: PriorityLevel
) -> None:
    if pattern not in SUPPORTED_TEMPLATES:
        raise ValueError(f"Unsupported executable DECLARE pattern: {pattern!r}")
    _, arity, priorities = SUPPORTED_TEMPLATES[pattern]
    if len(proposition_ids) != arity:
        raise ValueError(f"{pattern} requires exactly {arity} proposition(s)")
    if priority not in priorities:
        allowed = " or ".join(repr(value.value) for value in priorities)
        raise ValueError(f"{pattern} requires priority {allowed}")


def _reward_transitions(
    normalized: _NormalizedDFA,
    pattern: str,
    priority: PriorityLevel,
    preferred_state: int | None,
    reverse_state: int | None,
) -> tuple[Transition, ...]:
    """Emit every state change or rewarded step, paying only at classified completions."""
    transitions = []
    for source in normalized.states:
        for valuation in normalized.valuations:
            destination = normalized.transitions[(source, valuation)]
            reward = 0.0
            if source != normalized.final_state and destination == normalized.final_state:
                if pattern in {"Existence", "ExistenceTwo"} or priority is PriorityLevel.HARD:
                    reward = Configuration.CLAUSE_COMPLETION_REWARD
                elif source == normalized.initial_state and all(valuation):
                    reward = 0.0
                elif source == preferred_state and valuation[1]:
                    reward = Configuration.CLAUSE_COMPLETION_REWARD
                elif source == reverse_state and valuation[0]:
                    reward = 0.0
                else:
                    raise ValueError("Could not classify a precedence completion transition")

            if destination != source or reward != 0:
                transitions.append(
                    Transition(
                        source=source,
                        destination=destination,
                        condition=_condition(normalized.propositions, valuation),
                        reward=reward,
                    )
                )
    return tuple(transitions)


# ======================================================================================
#                                     COMPOSITION
# ======================================================================================


def compose_reward_machines(
    clauses: Sequence[tuple[RewardMachineStructure, tuple[str, ...]]],
) -> RewardMachineStructure:
    """Compose clause machines conjunctively into one reachable task machine."""
    clauses = tuple(clauses)
    if not clauses:
        raise ValueError("At least one clause Reward Machine is required")

    propositions = tuple(
        dict.fromkeys(
            proposition for _, clause_propositions in clauses for proposition in clause_propositions
        )
    )
    valuations = _valuations(propositions)
    proposition_positions = {name: index for index, name in enumerate(propositions)}
    transition_maps = tuple(
        _clause_transition_map(machine, clause_propositions)
        for machine, clause_propositions in clauses
    )
    initial = tuple(machine.initial_state for machine, _ in clauses)
    final = tuple(machine.final_state for machine, _ in clauses)
    names: dict[tuple[int, ...] | None, int] = {initial: 0}
    queue: deque[tuple[int, ...] | None] = deque([initial])
    transitions = []

    while queue:
        source = queue.popleft()
        if source is None or source == final:
            continue
        source_name = names[source]
        for valuation in valuations:
            destination_state, reward = _step_clauses(
                source, valuation, clauses, transition_maps, proposition_positions
            )
            if destination_state == final:
                reward += Configuration.TASK_COMPLETION_REWARD
            if destination_state not in names:
                names[destination_state] = len(names)
                queue.append(destination_state)
            destination_name = names[destination_state]
            if destination_name != source_name or reward != 0:
                transitions.append(
                    Transition(
                        source=source_name,
                        destination=destination_name,
                        condition=_condition(propositions, valuation),
                        reward=reward,
                    )
                )

    if final not in names:
        raise ValueError("Task clauses are incompatible; no accepting state is reachable")
    rejecting_states = (names[None],) if None in names else ()
    return RewardMachineStructure(
        states=tuple(range(len(names))),
        initial_state=0,
        final_state=names[final],
        rejecting_states=rejecting_states,
        transitions=tuple(transitions),
    )


def _step_clauses(
    source: tuple[int, ...],
    valuation: Valuation,
    clauses: Sequence[tuple[RewardMachineStructure, tuple[str, ...]]],
    transition_maps: Sequence[dict[tuple[int, Valuation], tuple[int, float]]],
    proposition_positions: dict[str, int],
) -> tuple[tuple[int, ...] | None, float]:
    """Advance every clause machine on one valuation.

    Returns the joint destination, ``None`` when a clause machine rejects, and the summed reward.
    """
    destinations = []
    reward = 0.0
    for index, ((machine, clause_propositions), transition_map) in enumerate(
        zip(clauses, transition_maps, strict=True)
    ):
        clause_valuation = tuple(
            valuation[proposition_positions[name]] for name in clause_propositions
        )
        destination, clause_reward = transition_map.get(
            (source[index], clause_valuation),
            (source[index], 0.0),
        )
        if destination in machine.rejecting_states:
            return None, 0.0
        destinations.append(destination)
        reward += clause_reward
    return tuple(destinations), reward


def _clause_transition_map(
    machine: RewardMachineStructure,
    propositions: tuple[str, ...],
) -> dict[tuple[int, Valuation], tuple[int, float]]:
    transitions = {}
    expected = set(propositions)
    for transition in machine.transitions:
        values = {
            literal.removeprefix("!"): not literal.startswith("!")
            for literal in transition.condition
        }
        if set(values) != expected:
            raise ValueError("Clause transition condition does not match its propositions")
        valuation = tuple(values[proposition] for proposition in propositions)
        transitions[(transition.source, valuation)] = (
            transition.destination,
            transition.reward,
        )
    return transitions


# ======================================================================================
#                                  DFA NORMALIZATION
# ======================================================================================


def _normalize_dfa(dfa: dict, proposition_ids: tuple[str, ...]) -> _NormalizedDFA:
    propositions = tuple(proposition.lower() for proposition in proposition_ids)
    if len(set(propositions)) != len(propositions):
        raise ValueError("Task proposition identifiers must be unique")

    _check_alphabet(dfa, propositions)
    states, initial_state, accepting_states = _declared_states(dfa)
    outgoing = _guarded_transitions(dfa, states, propositions)
    complete_transitions = _complete_transitions(states, outgoing, propositions)

    reachable = _reachable_states(initial_state, complete_transitions, propositions)
    reachable_transitions = {
        (source, valuation): destination
        for (source, valuation), destination in complete_transitions.items()
        if source in reachable
    }
    return _minimize_dfa(
        propositions,
        reachable,
        initial_state,
        accepting_states & reachable,
        reachable_transitions,
    )


def _check_alphabet(dfa: dict, propositions: tuple[str, ...]) -> None:
    alphabet = {str(symbol).lower() for symbol in dfa.get("alphabet", ())}
    if alphabet == set(propositions):
        return
    missing = set(propositions) - alphabet
    unexpected = alphabet - set(propositions)
    details = []
    if missing:
        details.append(f"missing {', '.join(sorted(missing))}")
    if unexpected:
        details.append(f"unexpected {', '.join(sorted(unexpected))}")
    raise ValueError(f"DFA alphabet does not match the task ({'; '.join(details)})")


def _declared_states(dfa: dict) -> tuple[set[str], str, set[str]]:
    states = {str(state) for state in dfa.get("states", ())}
    initial_state = str(dfa.get("initial_state", ""))
    accepting_states = {str(state) for state in dfa.get("accepting_states", ())}
    if not initial_state or initial_state not in states:
        raise ValueError("DFA has no declared initial state")
    if not accepting_states or not accepting_states <= states:
        raise ValueError("DFA has invalid accepting states")
    return states, initial_state, accepting_states


def _guarded_transitions(
    dfa: dict, states: set[str], propositions: tuple[str, ...]
) -> dict[str, list[tuple[object, str]]]:
    """Group the DFA's guarded transitions by source state, parsing each guard."""
    outgoing: dict[str, list[tuple[object, str]]] = defaultdict(list)
    for key, raw_destination in dfa.get("transitions", {}).items():
        if not isinstance(key, tuple) or len(key) != 2:
            raise ValueError("DFA returned a malformed transition key")
        source, guard = str(key[0]), str(key[1])
        destination = str(raw_destination)
        if source not in states or destination not in states:
            raise ValueError("DFA transition references an undeclared state")
        expression = _GuardParser(guard.lower(), set(propositions)).parse()
        outgoing[source].append((expression, destination))
    return outgoing


def _complete_transitions(
    states: set[str],
    outgoing: dict[str, list[tuple[object, str]]],
    propositions: tuple[str, ...],
) -> dict[tuple[str, Valuation], str]:
    """Resolve exactly one destination per state and valuation."""
    valuations = _valuations(propositions)
    complete_transitions: dict[tuple[str, Valuation], str] = {}
    for state in states:
        for valuation in valuations:
            values = dict(zip(propositions, valuation, strict=True))
            destinations = [
                destination
                for expression, destination in outgoing[state]
                if _evaluate(expression, values)
            ]
            if len(destinations) != 1:
                condition = ",".join(_condition(propositions, valuation))
                raise ValueError(
                    f"DFA must have one transition from {state} on {condition}; "
                    f"found {len(destinations)}"
                )
            complete_transitions[(state, valuation)] = destinations[0]
    return complete_transitions


def _reachable_states(
    initial_state: str,
    transitions: dict[tuple[str, Valuation], str],
    propositions: tuple[str, ...],
) -> set[str]:
    valuations = _valuations(propositions)
    reachable = {initial_state}
    queue = deque([initial_state])
    while queue:
        source = queue.popleft()
        for valuation in valuations:
            destination = transitions[(source, valuation)]
            if destination not in reachable:
                reachable.add(destination)
                queue.append(destination)
    return reachable


def _minimize_dfa(
    propositions: tuple[str, ...],
    states: set[str],
    initial_state: str,
    accepting_states: set[str],
    transitions: dict[tuple[str, Valuation], str],
) -> _NormalizedDFA:
    valuations = _valuations(propositions)
    partitions = _equivalence_partitions(states, accepting_states, transitions, valuations)
    state_to_partition = {
        state: index for index, partition in enumerate(partitions) for state in partition
    }
    initial_partition = state_to_partition[initial_state]
    partition_transitions = {
        (index, valuation): state_to_partition[transitions[(next(iter(partition)), valuation)]]
        for index, partition in enumerate(partitions)
        for valuation in valuations
    }

    names = {initial_partition: 0}
    queue = deque([initial_partition])
    while queue:
        source = queue.popleft()
        for valuation in valuations:
            destination = partition_transitions[(source, valuation)]
            if destination not in names:
                names[destination] = len(names)
                queue.append(destination)

    accepting_partitions = {state_to_partition[state] for state in accepting_states}
    accepting = {names[partition] for partition in accepting_partitions}
    if len(accepting) != 1:
        raise ValueError("Executable DFA must minimize to one success state")
    final_state = next(iter(accepting))
    minimized_transitions = {
        (names[source], valuation): names[destination]
        for (source, valuation), destination in partition_transitions.items()
    }
    for valuation in valuations:
        if minimized_transitions[(final_state, valuation)] != final_state:
            raise ValueError("Executable DFA success state must be absorbing")

    return _NormalizedDFA(
        propositions=propositions,
        valuations=valuations,
        states=tuple(range(len(names))),
        initial_state=0,
        final_state=final_state,
        transitions=minimized_transitions,
    )


def _equivalence_partitions(
    states: set[str],
    accepting_states: set[str],
    transitions: dict[tuple[str, Valuation], str],
    valuations: tuple[Valuation, ...],
) -> list[frozenset[str]]:
    """Refine accepting/non-accepting states until behaviourally equal states share a block."""
    partitions = [
        frozenset(partition)
        for partition in (accepting_states, states - accepting_states)
        if partition
    ]
    while True:
        state_to_partition = {
            state: index for index, partition in enumerate(partitions) for state in partition
        }
        refined = []
        for partition in partitions:
            groups: dict[tuple[int, ...], list[str]] = defaultdict(list)
            for state in sorted(partition):
                signature = tuple(
                    state_to_partition[transitions[(state, valuation)]] for valuation in valuations
                )
                groups[signature].append(state)
            refined.extend(
                frozenset(group) for _, group in sorted(groups.items(), key=lambda item: item[1][0])
            )
        if refined == partitions:
            return partitions
        partitions = refined


def states_without_path_to_final(
    states: Iterable[int],
    edges: Iterable[tuple[int, int]],
    final_state: int,
) -> set[int]:
    """Return the states from which no transition path reaches ``final_state``."""
    predecessors: dict[int, set[int]] = defaultdict(set)
    for source, destination in edges:
        predecessors[destination].add(source)

    can_reach_final = {final_state}
    queue = deque([final_state])
    while queue:
        destination = queue.popleft()
        for source in predecessors[destination]:
            if source not in can_reach_final:
                can_reach_final.add(source)
                queue.append(source)
    return set(states) - can_reach_final


def _states_without_path_to_final(dfa: _NormalizedDFA) -> set[int]:
    edges = ((source, destination) for (source, _), destination in dfa.transitions.items())
    return states_without_path_to_final(dfa.states, edges, dfa.final_state)


# ======================================================================================
#                                  PATTERN VALIDATION
# ======================================================================================


def _validate_existence(dfa: _NormalizedDFA) -> None:
    if dfa.transitions[(dfa.initial_state, (False,))] != dfa.initial_state:
        raise ValueError("Existence DFA must ignore non-occurrences")
    if dfa.transitions[(dfa.initial_state, (True,))] != dfa.final_state:
        raise ValueError("Existence DFA must complete on the first occurrence")


def _validate_existence_two(dfa: _NormalizedDFA) -> None:
    if dfa.transitions[(dfa.initial_state, (False,))] != dfa.initial_state:
        raise ValueError("ExistenceTwo DFA must ignore non-occurrences")
    progress_state = dfa.transitions[(dfa.initial_state, (True,))]
    if progress_state in {dfa.initial_state, dfa.final_state}:
        raise ValueError("ExistenceTwo DFA must retain the first occurrence")
    if dfa.transitions[(progress_state, (False,))] != progress_state:
        raise ValueError("ExistenceTwo DFA must retain progress between occurrences")
    if dfa.transitions[(progress_state, (True,))] != dfa.final_state:
        raise ValueError("ExistenceTwo DFA must complete on the second occurrence")


def _validate_non_hard_precedence(dfa: _NormalizedDFA) -> tuple[int, int]:
    a_only = (True, False)
    b_only = (False, True)
    both = (True, True)
    preferred_state = dfa.transitions[(dfa.initial_state, a_only)]
    reverse_state = dfa.transitions[(dfa.initial_state, b_only)]
    if preferred_state in {dfa.initial_state, dfa.final_state}:
        raise ValueError("Precedence DFA did not retain preferred-order progress")
    if reverse_state in {dfa.initial_state, dfa.final_state, preferred_state}:
        raise ValueError("Precedence DFA did not retain reverse-order progress")
    if dfa.transitions[(dfa.initial_state, both)] != dfa.final_state:
        raise ValueError("Non-hard simultaneous precedence must complete")
    if dfa.transitions[(preferred_state, b_only)] != dfa.final_state:
        raise ValueError("Preferred precedence order does not complete")
    if dfa.transitions[(reverse_state, a_only)] != dfa.final_state:
        raise ValueError("Reverse precedence order does not complete")
    return preferred_state, reverse_state


def _validate_hard_precedence(
    dfa: _NormalizedDFA,
    rejecting_states: set[int],
) -> None:
    if len(rejecting_states) != 1:
        raise ValueError("Hard precedence requires exactly one rejecting sink")
    rejecting_state = next(iter(rejecting_states))
    if any(
        dfa.transitions[(rejecting_state, valuation)] != rejecting_state
        for valuation in dfa.valuations
    ):
        raise ValueError("Hard precedence rejecting state must be a sink")

    a_only = (True, False)
    b_only = (False, True)
    both = (True, True)
    if dfa.transitions[(dfa.initial_state, b_only)] != rejecting_state:
        raise ValueError("Reverse hard precedence must enter the rejecting sink")
    if dfa.transitions[(dfa.initial_state, both)] != rejecting_state:
        raise ValueError("Simultaneous hard precedence must enter the rejecting sink")
    preferred_state = dfa.transitions[(dfa.initial_state, a_only)]
    if preferred_state in {dfa.initial_state, dfa.final_state, rejecting_state}:
        raise ValueError("Hard precedence did not retain preferred-order progress")
    if dfa.transitions[(preferred_state, b_only)] != dfa.final_state:
        raise ValueError("Preferred hard precedence order does not complete")


def _valuations(propositions: tuple[str, ...]) -> tuple[Valuation, ...]:
    return tuple(product((False, True), repeat=len(propositions)))


def _condition(
    propositions: tuple[str, ...],
    valuation: Valuation,
) -> tuple[str, ...]:
    return tuple(
        proposition if value else f"!{proposition}"
        for proposition, value in zip(propositions, valuation, strict=True)
    )
