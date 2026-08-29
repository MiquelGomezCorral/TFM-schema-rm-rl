"""Normalize and serialize FL-AT Reward Machines."""

import math
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import product


TOKEN = re.compile(r"\s*([a-z_][a-z0-9_]*|[!~&|()])", re.IGNORECASE)


@dataclass(frozen=True)
class Transition:
    """One disjoint Reward Machine transition."""

    source: str
    guard: str
    destination: str
    reward: float


@dataclass(frozen=True)
class RewardMachineStructure:
    """Deterministically named Reward Machine structure."""

    states: tuple[str, ...]
    initial_state: str
    accepting_states: tuple[str, ...]
    transitions: tuple[Transition, ...]


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


def _expand_guard(guard: str, proposition_ids: tuple[str, ...]) -> tuple[str, ...]:
    expression = _GuardParser(guard.lower(), set(proposition_ids)).parse()
    conjunctions = []
    for values in product((False, True), repeat=len(proposition_ids)):
        valuation = dict(zip(proposition_ids, values, strict=True))
        if _evaluate(expression, valuation):
            conjunctions.append(
                "&".join(
                    proposition if value else f"!{proposition}"
                    for proposition, value in valuation.items()
                )
                or "true"
            )
    return tuple(conjunctions)


def normalize_reward_machine(
    flat_reward_machine: dict,
    proposition_ids: tuple[str, ...],
) -> RewardMachineStructure:
    """Expand guards and rename reachable states in breadth-first order."""
    if len(set(proposition_ids)) != len(proposition_ids):
        raise ValueError("Proposition identifiers must be unique")
    alphabet = {str(symbol).lower() for symbol in flat_reward_machine.get("alphabet", ())}
    undeclared = alphabet - set(proposition_ids)
    if undeclared:
        raise ValueError(
            f"FL-AT produced undeclared proposition(s): {', '.join(sorted(undeclared))}"
        )

    initial_state = str(flat_reward_machine.get("initial_state", ""))
    if not initial_state:
        raise ValueError("FL-AT Reward Machine has no initial state")

    raw_transitions: list[tuple[str, str, str, float]] = []
    deterministic_rows: dict[tuple[str, str], tuple[str, float]] = {}
    all_states = {str(state) for state in flat_reward_machine.get("states", ())}
    all_states.add(initial_state)
    for key, value in flat_reward_machine.get("transitions", {}).items():
        if not isinstance(key, tuple) or len(key) != 2:
            raise ValueError("FL-AT returned a malformed transition key")
        if not isinstance(value, tuple) or len(value) != 2:
            raise ValueError("FL-AT returned a malformed transition value")
        source, guard = str(key[0]), str(key[1])
        destination, reward = str(value[0]), value[1]
        if (
            isinstance(reward, bool)
            or not isinstance(reward, (int, float))
            or not math.isfinite(reward)
        ):
            raise ValueError("FL-AT returned a non-finite transition reward")
        all_states.update((source, destination))
        for conjunction in _expand_guard(guard, proposition_ids):
            row_key = (source, conjunction)
            row_value = (destination, float(reward))
            previous = deterministic_rows.get(row_key)
            if previous is not None and previous != row_value:
                raise ValueError(
                    f"FL-AT produced ambiguous transitions from {source} on {conjunction}"
                )
            deterministic_rows[row_key] = row_value

    for (source, guard), (destination, reward) in deterministic_rows.items():
        raw_transitions.append((source, guard, destination, reward))

    outgoing = defaultdict(list)
    for transition in raw_transitions:
        outgoing[transition[0]].append(transition)

    state_names = {initial_state: "u0"}
    queue = deque([initial_state])
    while queue:
        source = queue.popleft()
        for _, guard, destination, reward in sorted(
            outgoing[source], key=lambda item: (item[1], item[2], item[3])
        ):
            if destination not in state_names:
                state_names[destination] = f"u{len(state_names)}"
                queue.append(destination)
    for state in sorted(all_states - set(state_names)):
        state_names[state] = f"u{len(state_names)}"

    state_order = {state: index for index, state in enumerate(state_names)}
    transitions = tuple(
        Transition(
            state_names[source],
            guard,
            state_names[destination],
            reward,
        )
        for source, guard, destination, reward in sorted(
            raw_transitions,
            key=lambda item: (
                state_order[item[0]],
                item[1],
                state_order[item[2]],
                item[3],
            ),
        )
    )
    accepting_states = tuple(
        state_names[str(state)]
        for state in sorted(
            flat_reward_machine.get("accepting_states", ()),
            key=lambda state: state_order[str(state)],
        )
    )
    return RewardMachineStructure(
        tuple(state_names.values()),
        "u0",
        accepting_states,
        transitions,
    )


def serialize_reward_machine(reward_machine: RewardMachineStructure) -> str:
    """Serialize exactly the reference section-based Reward Machine format."""
    lines = [
        "REWARD_MACHINE:",
        f"STATES: {', '.join(reward_machine.states)}",
        f"INITIAL_STATE: {reward_machine.initial_state}",
        "TRANSITION_FUNCTION:",
    ]
    lines.extend(
        f"({transition.source}, {transition.guard}) -> {transition.destination}"
        for transition in reward_machine.transitions
    )
    lines.append("REWARD_FUNCTION:")
    lines.extend(
        f"({transition.source}, {transition.guard}, {transition.destination}) "
        f"-> {transition.reward}"
        for transition in reward_machine.transitions
        if transition.reward != 0
    )
    return "\n".join(lines) + "\n"
