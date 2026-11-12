"""The DECLARE judge on hand-made traces, and its LTLf display table against nl2ltl's.

A pattern string is one proposition over the steps: ``"0100"`` is true at step 2 only.
Run with ``PYTHONPATH=app python -m unittest tests.test_declare_judge``.
"""

import unittest
from typing import ClassVar

from src.benchmark.declare_judge import (
    BROKEN,
    HOLDS,
    LTLF_DISPLAY,
    OPEN_AT_END,
    ClauseError,
    as_clause,
    judge_clause,
    judge_trace,
    ltlf_of,
)
from src.utils import presentation


def trace(**patterns: str) -> list[dict[str, bool]]:
    """The labels after each step, from one pattern string per proposition."""
    length = len(next(iter(patterns.values())))
    return [{name: pattern[i] == "1" for name, pattern in patterns.items()} for i in range(length)]


def verdict(template: str, a: str, b: str = "") -> tuple[str, int | None]:
    names = ("a", "b") if b else ("a",)
    clause = (template, names, "hard")
    judged = judge_clause(clause, trace(a=a, b=b) if b else trace(a=a))
    return judged.status, judged.step


class TemplateVerdicts(unittest.TestCase):
    # template: [(a, b, expected status, expected 1-based break step)]
    CASES: ClassVar[dict[str, list[tuple[str, str, str, int | None]]]] = {
        "Existence": [("000", "", OPEN_AT_END, None), ("010", "", HOLDS, None)],
        "ExistenceTwo": [
            ("010", "", OPEN_AT_END, None),
            ("0101", "", HOLDS, None),
            ("011", "", HOLDS, None),  # a state that lasts two steps counts twice
        ],
        "Absence": [("000", "", HOLDS, None), ("0010", "", BROKEN, 3)],
        "Response": [
            ("0100", "0010", HOLDS, None),
            ("0110", "0010", HOLDS, None),  # b on the same step as the last a is enough
            ("0100", "0000", OPEN_AT_END, None),
            ("0010", "0100", OPEN_AT_END, None),  # a b before the a does not answer it
            ("0101", "0010", OPEN_AT_END, None),  # the last a has no b at or after it
            ("0000", "0000", HOLDS, None),
        ],
        "Precedence": [
            ("0100", "0010", HOLDS, None),
            ("0100", "0100", HOLDS, None),  # same step as the first a is fine
            ("0100", "0000", HOLDS, None),
            ("0010", "0100", BROKEN, 2),
            ("0000", "0010", BROKEN, 3),  # b with no a at all
        ],
        "ChainResponse": [
            ("0100", "0010", HOLDS, None),
            ("0100", "0001", BROKEN, 3),
            ("0110", "0010", BROKEN, 4),
            ("0001", "0000", OPEN_AT_END, None),  # a at the last step: the answer can still come
            ("0000", "0000", HOLDS, None),
        ],
        "RespondedExistence": [
            ("0100", "0000", OPEN_AT_END, None),
            ("0100", "0001", HOLDS, None),
            ("0010", "0100", HOLDS, None),  # b may come before a
            ("0000", "0000", HOLDS, None),
        ],
        "NotCoExistence": [
            ("0100", "0000", HOLDS, None),
            ("0100", "0010", BROKEN, 3),
            ("0100", "0100", BROKEN, 2),
        ],
    }

    def test_every_template_has_cases(self) -> None:
        self.assertEqual(set(self.CASES), set(LTLF_DISPLAY))

    def test_verdicts(self) -> None:
        for template, cases in self.CASES.items():
            for a, b, status, step in cases:
                with self.subTest(template=template, a=a, b=b):
                    self.assertEqual(verdict(template, a, b), (status, step))


class TraceJudging(unittest.TestCase):
    CLAUSES = (
        as_clause(["Existence", ["goal"], "hard"]),
        as_clause(["Absence", ["bad"], "soft"]),
        as_clause(["Response", ["a", "b"], "soft"]),
    )

    def test_success_needs_only_the_hard_clauses(self) -> None:
        judged = judge_trace(self.CLAUSES, trace(goal="001", bad="010", a="010", b="000"))
        self.assertEqual([v.text for v in judged.verdicts], [HOLDS, "broken@2", OPEN_AT_END])
        self.assertTrue(judged.success)
        self.assertEqual((judged.count(BROKEN, "soft"), judged.count(OPEN_AT_END, "soft")), (1, 1))
        self.assertEqual(judged.failed(), [1, 2])

    def test_an_open_hard_clause_fails_the_trace(self) -> None:
        judged = judge_trace(self.CLAUSES, trace(goal="000", bad="000", a="000", b="000"))
        self.assertFalse(judged.success)
        self.assertEqual(judged.to_dict()["hard_open"], 1)

    def test_a_proposition_missing_from_the_labels_is_false(self) -> None:
        judged = judge_trace([as_clause(["Absence", ["x"], "hard"])], [{"y": True}, {"y": True}])
        self.assertTrue(judged.success)

    def test_a_clause_must_be_well_formed(self) -> None:
        for raw in (
            ["Nope", ["a"], "hard"],
            ["Response", ["a"], "hard"],
            ["Existence", ["a"], "firm"],
            ["Existence", "a", "hard"],
            ["Existence", ["a"]],
        ):
            with self.subTest(raw=raw), self.assertRaises(ClauseError):
                as_clause(raw)


class LtlfTable(unittest.TestCase):
    def test_display_strings_equal_nl2ltl(self) -> None:
        for template, (count, _, _) in LTLF_DISPLAY.items():
            propositions = ("has_key", "door_open")[:count]
            with self.subTest(template=template):
                shown = ltlf_of((template, propositions, "hard"))
                raw = presentation.ltlf_of(template, propositions)
                self.assertEqual(shown["raw"], raw)
                self.assertEqual(shown["readable"], presentation.pretty_ltlf(raw))


if __name__ == "__main__":
    unittest.main()
