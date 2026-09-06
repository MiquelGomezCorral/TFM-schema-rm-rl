"""Normalize MONA DFAs and serialize compact executable Reward Machines."""

import math
import re
from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product

from src.models import (
    CLAUSE_COMPLETION_REWARD,
    TASK_COMPLETION_REWARD,
    PriorityLevel,
)


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
            token = match.group(1).lower()
            tokens.append("!" if token == "~" else token)
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
        token = self.tokens[self.position]
        self.position += 1
        if token in {"true", "false"}:
            return ("constant", token == "true")
        if token not in self.propositions:
            raise ValueError(f"Boolean guard uses undeclared proposition '{token}'")
        return ("atom", token)

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


def normalize_reward_machine(
    dfa: dict,
    pattern: str,
    proposition_ids: tuple[str, ...],
    priority: PriorityLevel,
) -> RewardMachineStructure:
    """Minimize one DFA and add one-time completion rewards."""
    if pattern not in {"Existence", "ExistenceTwo", "Precedence"}:
        raise ValueError(f"Unsupported executable DECLARE pattern: {pattern!r}")
    if pattern in {"Existence", "ExistenceTwo"}:
        if len(proposition_ids) != 1:
            raise ValueError(f"{pattern} requires exactly one proposition")
        if priority is not PriorityLevel.NONE:
            raise ValueError(f"{pattern} requires priority 'none'")
    else:
        if len(proposition_ids) != 2:
            raise ValueError("Precedence requires exactly two propositions")
        if priority not in {PriorityLevel.SOFT, PriorityLevel.HARD}:
            raise ValueError("Precedence requires priority 'soft' or 'hard'")

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

    transitions = []
    for source in normalized.states:
        for valuation in normalized.valuations:
            destination = normalized.transitions[(source, valuation)]
            reward = 0.0
            if source != normalized.final_state and destination == normalized.final_state:
                if pattern in {"Existence", "ExistenceTwo"} or priority is PriorityLevel.HARD:
                    reward = CLAUSE_COMPLETION_REWARD
                elif source == normalized.initial_state and all(valuation):
                    reward = 0.0
                elif source == preferred_state and valuation[1]:
                    reward = CLAUSE_COMPLETION_REWARD
                elif source == reverse_state and valuation[0]:
                    reward = 0.0
                else:
                    raise ValueError("Could not classify a precedence completion transition")

            if reward is None:
                raise ValueError("Rejecting precedence transitions cannot carry rewards")
            if destination != source or reward != 0:
                transitions.append(
                    Transition(
                        source=source,
                        destination=destination,
                        condition=_condition(normalized.propositions, valuation),
                        reward=reward,
                    )
                )

    return RewardMachineStructure(
        states=normalized.states,
        initial_state=normalized.initial_state,
        final_state=normalized.final_state,
        rejecting_states=tuple(sorted(rejecting_states)),
        transitions=tuple(transitions),
    )


def compose_reward_machines(
    clauses: Sequence[tuple[RewardMachineStructure, tuple[str, ...]]],
) -> RewardMachineStructure:
    """Compose clause machines conjunctively into one reachable task machine."""
    clauses = tuple(clauses)
    if not clauses:
        raise ValueError("At least one clause Reward Machine is required")

    propositions = tuple(
        dict.fromkeys(
            proposition
            for _, clause_propositions in clauses
            for proposition in clause_propositions
        )
    )
    valuations = tuple(product((False, True), repeat=len(propositions)))
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
            destinations = []
            reward = 0.0
            rejected = False
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
                    rejected = True
                    break
                destinations.append(destination)
                reward += clause_reward

            destination_state = None if rejected else tuple(destinations)
            if destination_state == final:
                reward += TASK_COMPLETION_REWARD
            elif rejected:
                reward = 0.0
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


def _normalize_dfa(dfa: dict, proposition_ids: tuple[str, ...]) -> _NormalizedDFA:
    propositions = tuple(proposition.lower() for proposition in proposition_ids)
    if len(set(propositions)) != len(propositions):
        raise ValueError("Task proposition identifiers must be unique")

    alphabet = {str(symbol).lower() for symbol in dfa.get("alphabet", ())}
    if alphabet != set(propositions):
        missing = set(propositions) - alphabet
        unexpected = alphabet - set(propositions)
        details = []
        if missing:
            details.append(f"missing {', '.join(sorted(missing))}")
        if unexpected:
            details.append(f"unexpected {', '.join(sorted(unexpected))}")
        raise ValueError(f"DFA alphabet does not match the task ({'; '.join(details)})")

    states = {str(state) for state in dfa.get("states", ())}
    initial_state = str(dfa.get("initial_state", ""))
    accepting_states = {str(state) for state in dfa.get("accepting_states", ())}
    if not initial_state or initial_state not in states:
        raise ValueError("DFA has no declared initial state")
    if not accepting_states or not accepting_states <= states:
        raise ValueError("DFA has invalid accepting states")

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

    valuations = tuple(product((False, True), repeat=len(propositions)))
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

    reachable = {initial_state}
    queue = deque([initial_state])
    while queue:
        source = queue.popleft()
        for valuation in valuations:
            destination = complete_transitions[(source, valuation)]
            if destination not in reachable:
                reachable.add(destination)
                queue.append(destination)

    reachable_transitions = {
        (source, valuation): destination
        for (source, valuation), destination in complete_transitions.items()
        if source in reachable
    }
    reachable_accepting = accepting_states & reachable
    return _minimize_dfa(
        propositions,
        valuations,
        reachable,
        initial_state,
        reachable_accepting,
        reachable_transitions,
    )


def _minimize_dfa(
    propositions: tuple[str, ...],
    valuations: tuple[Valuation, ...],
    states: set[str],
    initial_state: str,
    accepting_states: set[str],
    transitions: dict[tuple[str, Valuation], str],
) -> _NormalizedDFA:
    partitions = [
        frozenset(partition)
        for partition in (accepting_states, states - accepting_states)
        if partition
    ]
    while True:
        state_to_partition = {
            state: index
            for index, partition in enumerate(partitions)
            for state in partition
        }
        refined = []
        for partition in partitions:
            groups: dict[tuple[int, ...], list[str]] = defaultdict(list)
            for state in sorted(partition):
                signature = tuple(
                    state_to_partition[transitions[(state, valuation)]]
                    for valuation in valuations
                )
                groups[signature].append(state)
            refined.extend(
                frozenset(group)
                for _, group in sorted(groups.items(), key=lambda item: item[1][0])
            )
        if refined == partitions:
            break
        partitions = refined

    state_to_partition = {
        state: index
        for index, partition in enumerate(partitions)
        for state in partition
    }
    initial_partition = state_to_partition[initial_state]
    partition_transitions = {
        (index, valuation): state_to_partition[
            transitions[(next(iter(partition)), valuation)]
        ]
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

    accepting_partitions = {
        state_to_partition[state] for state in accepting_states
    }
    accepting = {names[partition] for partition in accepting_partitions}
    if len(accepting) != 1:
        raise ValueError("Executable DFA must minimize to one success state")
    final_state = next(iter(accepting))
    minimized_transitions = {
        (names[source], valuation): names[destination]
        for (source, valuation), destination in partition_transitions.items()
    }
    states_by_name = tuple(range(len(names)))
    for valuation in valuations:
        if minimized_transitions[(final_state, valuation)] != final_state:
            raise ValueError("Executable DFA success state must be absorbing")

    return _NormalizedDFA(
        propositions=propositions,
        valuations=valuations,
        states=states_by_name,
        initial_state=0,
        final_state=final_state,
        transitions=minimized_transitions,
    )


def _states_without_path_to_final(dfa: _NormalizedDFA) -> set[int]:
    predecessors: dict[int, set[int]] = defaultdict(set)
    for (source, _), destination in dfa.transitions.items():
        predecessors[destination].add(source)

    can_reach_final = {dfa.final_state}
    queue = deque([dfa.final_state])
    while queue:
        destination = queue.popleft()
        for source in predecessors[destination]:
            if source not in can_reach_final:
                can_reach_final.add(source)
                queue.append(source)
    return set(dfa.states) - can_reach_final


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


def _condition(
    propositions: tuple[str, ...],
    valuation: Valuation,
) -> tuple[str, ...]:
    return tuple(
        proposition if value else f"!{proposition}"
        for proposition, value in zip(propositions, valuation, strict=True)
    )


def serialize_reward_machine(reward_machine: RewardMachineStructure) -> str:
    """Serialize the current TFM numeric semicolon format."""
    non_final_states = tuple(
        state for state in reward_machine.states if state != reward_machine.final_state
    )
    lines = [
        f"s: {', '.join(str(state) for state in non_final_states)}",
        f"i: {reward_machine.initial_state}",
        f"f: {reward_machine.final_state}",
        "r: 0",
    ]
    lines.extend(
        "; ".join(
            (
                str(transition.source),
                str(transition.destination),
                ",".join(transition.condition),
                _format_reward(transition.reward),
            )
        )
        for transition in reward_machine.transitions
    )
    return "\n".join(lines) + "\n"


def parse_reward_machine(text: str) -> RewardMachineStructure:
    """Parse the current numeric semicolon Reward Machine format."""
    if not isinstance(text, str):
        raise ValueError("Reward Machine content must be text")

    lines = text.splitlines()
    if len(lines) < 4:
        raise ValueError("Reward Machine must contain s, i, f, and r headers")
    headers = {}
    for expected, line in zip(("s", "i", "f", "r"), lines[:4], strict=True):
        match = re.fullmatch(rf"{expected}:[ \t]*(.*)", line)
        if match is None:
            raise ValueError(f"Reward Machine must start with an '{expected}:' header")
        headers[expected] = match.group(1).strip()

    if headers["r"] != "0":
        raise ValueError("Reward Machine reward header must be 'r: 0'")

    non_final_states = _parse_state_list(headers["s"])
    final_state = _parse_state(headers["f"], "final")
    initial_state = _parse_state(headers["i"], "initial")
    if final_state in non_final_states:
        raise ValueError("Final state must not be listed in the non-final state header")
    states = tuple(non_final_states) + (final_state,)
    if initial_state not in states:
        raise ValueError("Initial state is not declared")
    if initial_state == final_state:
        raise ValueError("Initial and final states must differ")

    transitions: list[Transition] = []
    seen_conditions: set[tuple[int, frozenset[str]]] = set()
    declared_states = set(states)
    for line_number, line in enumerate(lines[4:], start=5):
        if not line.strip():
            continue
        fields = [field.strip() for field in line.split(";")]
        if len(fields) != 4 or any(field == "" for field in fields[:2] + fields[3:]):
            raise ValueError(f"Malformed transition on line {line_number}")
        source = _parse_state(fields[0], f"transition source on line {line_number}")
        destination = _parse_state(fields[1], f"transition destination on line {line_number}")
        if source not in declared_states or destination not in declared_states:
            raise ValueError(f"Transition on line {line_number} references an undeclared state")
        condition = _parse_condition(fields[2], line_number)
        condition_key = (source, frozenset(condition))
        if condition_key in seen_conditions:
            raise ValueError(f"Duplicate transition condition on line {line_number}")
        seen_conditions.add(condition_key)
        reward = _parse_reward(fields[3], line_number)
        transitions.append(Transition(source, destination, condition, reward))

    predecessors: dict[int, set[int]] = defaultdict(set)
    for transition in transitions:
        predecessors[transition.destination].add(transition.source)
    can_reach_final = {final_state}
    queue = deque([final_state])
    while queue:
        destination = queue.popleft()
        for source in predecessors[destination]:
            if source not in can_reach_final:
                can_reach_final.add(source)
                queue.append(source)
    rejecting_states = tuple(sorted(declared_states - can_reach_final))
    return RewardMachineStructure(
        states=states,
        initial_state=initial_state,
        final_state=final_state,
        rejecting_states=rejecting_states,
        transitions=tuple(transitions),
    )


def _parse_state_list(value: str) -> tuple[int, ...]:
    if not value:
        return ()
    states = tuple(_parse_state(item.strip(), "state") for item in value.split(","))
    if len(set(states)) != len(states):
        raise ValueError("Reward Machine state header contains duplicates")
    return states


def _parse_state(value: str, description: str) -> int:
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError(f"Invalid {description} state")
    return int(value)


def _parse_condition(value: str, line_number: int) -> tuple[str, ...]:
    if not value:
        return ()
    literals = tuple(literal.strip() for literal in value.split(","))
    if any(not re.fullmatch(r"!?[a-z_][a-z0-9_]*", literal) for literal in literals):
        raise ValueError(f"Invalid guard on line {line_number}")
    propositions = {literal.removeprefix("!") for literal in literals}
    if len(propositions) != len(literals):
        raise ValueError(f"Guard repeats a proposition on line {line_number}")
    return literals


def _parse_reward(value: str, line_number: int) -> float:
    if not re.fullmatch(r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?", value):
        raise ValueError(f"Invalid reward on line {line_number}")
    reward = float(value)
    if not math.isfinite(reward):
        raise ValueError(f"Reward on line {line_number} must be finite")
    return reward


def _format_reward(reward: float) -> str:
    if reward == 0:
        return "0"
    return f"{reward:.2f}"
