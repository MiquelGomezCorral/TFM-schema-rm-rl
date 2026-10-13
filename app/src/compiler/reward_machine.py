"""Reward Machine structures and the Boolean guards their transitions carry."""

import re
from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

TOKEN = re.compile(r"\s*([a-z_][a-z0-9_]*|[!~&|()])", re.IGNORECASE)


@dataclass(frozen=True)
class Transition:
    """One disjoint executable Reward Machine transition."""

    source: int
    destination: int
    condition: tuple[str, ...]
    reward: float


@dataclass(frozen=True)
class RewardMachineStructure:
    """A numeric Reward Machine with at most one success final state.

    A rule-only machine (no hard goal) has no final state: ``final_state`` is ``None``.
    """

    states: tuple[int, ...]
    initial_state: int
    final_state: int | None
    rejecting_states: tuple[int, ...]
    transitions: tuple[Transition, ...]


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
    """Parse a Boolean guard into an expression tree."""
    names = {str(proposition).lower() for proposition in propositions}
    return _GuardParser(str(guard).lower(), names).parse()


def evaluate_boolean_guard(expression, valuation: dict[str, bool]) -> bool:
    """Evaluate a parsed guard against one complete valuation."""
    return _evaluate(
        expression, {str(key).lower(): bool(value) for key, value in valuation.items()}
    )


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
