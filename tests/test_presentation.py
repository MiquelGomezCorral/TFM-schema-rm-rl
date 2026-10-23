"""The shared result format: readable LTLf, the pipeline's own LTLf, the empty-reward note."""

import unittest

from pylogics.syntax.ltl import Atomic

from src.compiler import materialize_proposal
from src.config import PriorityLevel
from src.engines.structured import SUPPORTED_TEMPLATES, ProposalSelection
from src.utils import Example, ltlf_of, pretty_ltlf, result_block

# The eight IBM templates: the raw string IBM writes and the same string with spaces for reading.
READABLE = {
    "(Fhas_key)": "(F has_key)",
    "(F(door_open&(X(Fdoor_open))))": "(F (door_open & (X (F door_open))))",
    "(~(Fkey_lost))": "(~(F key_lost))",
    "((Fdoor_open)->(Fhas_key))": "((F door_open) -> (F has_key))",
    "(G(has_key->(Fdoor_open)))": "(G (has_key -> (F door_open)))",
    "(((~door_open)Uhas_key)|(G(~door_open)))": "(((~door_open) U has_key) | (G (~door_open)))",
    "(G(has_key->(Xdoor_open)))": "(G (has_key -> (X door_open)))",
    "((Fhas_key)->(~(Fkey_lost)))": "((F has_key) -> (~(F key_lost)))",
}


class PresentationTest(unittest.TestCase):
    def test_pretty_ltlf_spaces_the_eight_template_formulas(self):
        for raw, readable in READABLE.items():
            self.assertEqual(pretty_ltlf(raw), readable)

    def test_ltlf_of_equals_the_pipeline_formula(self):
        template_class, _ = SUPPORTED_TEMPLATES["Precedence"]
        selection = ProposalSelection(
            normalized_clause="Precedence(has_key, door_open)",
            pattern="Precedence",
            propositions=("has_key", "door_open"),
            priority=PriorityLevel.HARD,
            template=template_class(Atomic("has_key"), Atomic("door_open")),
        )
        proposal = materialize_proposal("open the door after the key", [selection])
        self.assertEqual(
            ltlf_of("Precedence", ["has_key", "door_open"]), proposal.clauses[0].ltlf_formula
        )

    def test_result_block_notes_an_empty_reward_function(self):
        example = Example(
            "Pick up the key.",
            [("Existence", ["has_key"], "soft")],
            "REWARD_FUNCTION:\n",
            inert_soft=True,
        )
        block = result_block(example)
        self.assertIn(" - (Fhas_key)", block)
        self.assertTrue(
            block.endswith(
                "# empty: every transition pays 0 (the soft clause is inert: it never changes a reward)"
            )
        )
