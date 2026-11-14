"""Direct finite-trace judge for the eight DECLARE templates.

The judge belongs to neither pipeline: it reads only a trace (the reference labels after each
step) and a clause list, never a pipeline's labeling or Reward Machine, and never calls nl2ltl.
Each clause gets ``holds``, ``broken`` (with the 1-based step it broke) or ``open_at_end``.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

HOLDS, BROKEN, OPEN_AT_END = "holds", "broken", "open_at_end"
HARD, SOFT = "hard", "soft"

# Each template: number of propositions, then the LTLf string nl2ltl's ``to_ltlf`` gives it
# (raw, as FL-AT and MONA read it, and spaced for reading). ``{a}`` and ``{b}`` are the
# propositions. Copied by hand so the judge never imports nl2ltl; the unit test compares them.
LTLF_DISPLAY: dict[str, tuple[int, str, str]] = {
    "Existence": (1, "(F{a})", "(F {a})"),
    "ExistenceTwo": (1, "(F({a}&(X(F{a}))))", "(F ({a} & (X (F {a}))))"),
    "Absence": (1, "(~(F{a}))", "(~(F {a}))"),
    "RespondedExistence": (2, "((F{a})->(F{b}))", "((F {a}) -> (F {b}))"),
    "Response": (2, "(G({a}->(F{b})))", "(G ({a} -> (F {b})))"),
    "Precedence": (2, "(((~{b})U{a})|(G(~{b})))", "(((~{b}) U {a}) | (G (~{b})))"),
    "ChainResponse": (2, "(G({a}->(X{b})))", "(G ({a} -> (X {b})))"),
    "NotCoExistence": (2, "((F{a})->(~(F{b})))", "((F {a}) -> (~(F {b})))"),
}

Clause = tuple[str, tuple[str, ...], str]  # (template, propositions, hard|soft)
Verdict = tuple[str, int | None]  # (status, 1-based step of a break)


class ClauseError(ValueError):
    """A clause is not ``[template, [propositions], hard|soft]`` of a supported template."""


def as_clause(raw: Sequence[object]) -> Clause:
    """Validate one clause in card shape and return it as a tuple.

    Raises:
        ClauseError: If the shape, template, number of propositions or priority is wrong.
    """
    if not isinstance(raw, Sequence) or isinstance(raw, str) or len(raw) != 3:
        raise ClauseError(f"clause must be [template, [propositions], priority], got {raw!r}")
    template, propositions, priority = raw
    if template not in LTLF_DISPLAY:
        raise ClauseError(f"unknown template {template!r}; known: {', '.join(LTLF_DISPLAY)}")
    if not isinstance(propositions, Sequence) or isinstance(propositions, str):
        raise ClauseError(f"{template}: propositions must be a list, got {propositions!r}")
    if len(propositions) != LTLF_DISPLAY[template][0]:
        raise ClauseError(f"{template} takes {LTLF_DISPLAY[template][0]} proposition(s)")
    if priority not in (HARD, SOFT):
        raise ClauseError(f"{template}: priority must be hard or soft, got {priority!r}")
    return template, tuple(str(name) for name in propositions), priority


def ltlf_of(clause: Clause) -> dict[str, str]:
    """The clause's LTLf as the pipeline serializes it (``raw``) and spaced for reading."""
    template, propositions, _ = clause
    names = dict(zip("ab", propositions, strict=False))
    _, raw, readable = LTLF_DISPLAY[template]
    return {"raw": raw.format(**names), "readable": readable.format(**names)}


def describe_clauses(clauses: Sequence[Clause]) -> list[dict[str, object]]:
    """Clauses with their LTLf, for the pages and reports that show a card result."""
    return [
        {"clause": [clause[0], list(clause[1]), clause[2]], "ltlf": ltlf_of(clause)}
        for clause in clauses
    ]


# ======================================================================================
#                                    TEMPLATE RULES
# ======================================================================================
# Every rule takes the per-step truth values of a and b (b is [] for one-proposition
# templates) and returns a verdict. Steps are 0-based inside, 1-based in the verdict.


def _first(values: Sequence[bool]) -> int | None:
    return next((index for index, value in enumerate(values) if value), None)


def _last(values: Sequence[bool]) -> int | None:
    return next((index for index in reversed(range(len(values))) if values[index]), None)


def _existence(a: Sequence[bool], _b: Sequence[bool]) -> Verdict:
    return (HOLDS, None) if any(a) else (OPEN_AT_END, None)


def _existence_two(a: Sequence[bool], _b: Sequence[bool]) -> Verdict:
    return (HOLDS, None) if sum(a) >= 2 else (OPEN_AT_END, None)


def _absence(a: Sequence[bool], _b: Sequence[bool]) -> Verdict:
    first = _first(a)
    return (HOLDS, None) if first is None else (BROKEN, first + 1)


def _response(a: Sequence[bool], b: Sequence[bool]) -> Verdict:
    last_a = _last(a)
    last_b = _last(b)
    if last_a is None or (last_b is not None and last_a <= last_b):
        return HOLDS, None
    return OPEN_AT_END, None


def _precedence(a: Sequence[bool], b: Sequence[bool]) -> Verdict:
    first_a, first_b = _first(a), _first(b)
    # A b on the same step as the first a is fine; a b before every a, or with no a, breaks it.
    if first_b is not None and (first_a is None or first_b < first_a):
        return BROKEN, first_b + 1
    return HOLDS, None


def _chain_response(a: Sequence[bool], b: Sequence[bool]) -> Verdict:
    steps = len(a)
    for index, value in enumerate(a):
        if value and index + 1 < steps and not b[index + 1]:
            return BROKEN, index + 2
    return (OPEN_AT_END, None) if steps and a[-1] else (HOLDS, None)


def _responded_existence(a: Sequence[bool], b: Sequence[bool]) -> Verdict:
    return (OPEN_AT_END, None) if any(a) and not any(b) else (HOLDS, None)


def _not_co_existence(a: Sequence[bool], b: Sequence[bool]) -> Verdict:
    first_a, first_b = _first(a), _first(b)
    if first_a is None or first_b is None:
        return HOLDS, None
    return BROKEN, max(first_a, first_b) + 1


# Activation: did the event that gives the clause something to check happen? A clause that holds
# without being activated is an empty pass (a conditional rule whose trigger never fired).
# Existence templates are activated by their own event, so they never pass empty; Absence is a
# pure prohibition with no trigger (None: not applicable) and a do-nothing agent passes it.


def _activated_by_a(a: Sequence[bool], _b: Sequence[bool]) -> bool | None:
    return any(a)


def _activated_by_b(_a: Sequence[bool], b: Sequence[bool]) -> bool | None:
    return any(b)  # Precedence guards b: a trace with no b has nothing to check


def _activated_by_either(a: Sequence[bool], b: Sequence[bool]) -> bool | None:
    return any(a) or any(b)  # NotCoExistence is symmetric: both a and b are the guarded events


def _no_trigger(_a: Sequence[bool], _b: Sequence[bool]) -> bool | None:
    return None


ACTIVATION: dict[str, Callable[[Sequence[bool], Sequence[bool]], bool | None]] = {
    "Existence": _activated_by_a,
    "ExistenceTwo": _activated_by_a,
    "Absence": _no_trigger,
    "RespondedExistence": _activated_by_a,
    "Response": _activated_by_a,
    "Precedence": _activated_by_b,
    "ChainResponse": _activated_by_a,
    "NotCoExistence": _activated_by_either,
}

RULES: dict[str, Callable[[Sequence[bool], Sequence[bool]], Verdict]] = {
    "Existence": _existence,
    "ExistenceTwo": _existence_two,
    "Absence": _absence,
    "RespondedExistence": _responded_existence,
    "Response": _response,
    "Precedence": _precedence,
    "ChainResponse": _chain_response,
    "NotCoExistence": _not_co_existence,
}


# ======================================================================================
#                                       JUDGMENT
# ======================================================================================


@dataclass(frozen=True)
class ClauseVerdict:
    """One clause's verdict on one trace; ``step`` is the 1-based step of a break.

    ``activated`` is whether the clause's trigger happened (None: the template has none).
    """

    clause: Clause
    status: str
    step: int | None = None
    activated: bool | None = None

    @property
    def text(self) -> str:
        """``holds``, ``broken@i`` or ``open_at_end``."""
        return f"{BROKEN}@{self.step}" if self.status == BROKEN else self.status


@dataclass(frozen=True)
class Judgment:
    """The clause verdicts on one trace and the counts the metrics use.

    Judged success is every hard clause holding; soft clauses are counted, never gate success.
    """

    verdicts: tuple[ClauseVerdict, ...]

    @property
    def success(self) -> bool:
        return all(v.status == HOLDS for v in self.verdicts if v.clause[2] == HARD)

    @property
    def non_empty_success(self) -> bool:
        """Success where every hard clause with a trigger was activated (no empty pass)."""
        return self.success and all(
            v.activated is not False for v in self.verdicts if v.clause[2] == HARD
        )

    def count(self, status: str, priority: str) -> int:
        return sum(1 for v in self.verdicts if v.status == status and v.clause[2] == priority)

    def failed(self) -> list[int]:
        """Indices of the clauses that do not hold (broken or open at the end)."""
        return [index for index, v in enumerate(self.verdicts) if v.status != HOLDS]

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "non_empty_success": self.non_empty_success,
            "verdicts": [verdict.text for verdict in self.verdicts],
            "activated": [verdict.activated for verdict in self.verdicts],
            "hard_breaks": self.count(BROKEN, HARD),
            "soft_breaks": self.count(BROKEN, SOFT),
            "hard_open": self.count(OPEN_AT_END, HARD),
            "soft_open": self.count(OPEN_AT_END, SOFT),
        }


def judge_clause(clause: Clause, labels: Sequence[Mapping[str, bool]]) -> ClauseVerdict:
    """Judge one clause on a trace: ``labels[i]`` are the reference labels after step ``i + 1``."""
    template, propositions, _ = clause
    a = [bool(step.get(propositions[0], False)) for step in labels]
    b = [bool(step.get(propositions[1], False)) for step in labels] if len(propositions) > 1 else []
    status, step = RULES[template](a, b)
    return ClauseVerdict(clause, status, step, ACTIVATION[template](a, b))


def judge_trace(clauses: Sequence[Clause], labels: Sequence[Mapping[str, bool]]) -> Judgment:
    """Judge every clause on a trace; a proposition missing from a step counts as false."""
    return Judgment(tuple(judge_clause(clause, labels) for clause in clauses))
