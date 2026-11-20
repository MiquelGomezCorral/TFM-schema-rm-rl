"""The critic clues' redundancy and forced-event lines on hand-built clause DFAs (no MONA)."""

import unittest

from src.compiler.critic_clues import critic_clues
from src.compiler.pipeline import ClauseProposal
from src.compiler.reward_layer import build_reward_machine
from src.config import PriorityLevel


def existence(event):
    """F event: pending until the event happens, then satisfied for good."""
    return {
        "alphabet": {event},
        "states": {"E0", "E1"},
        "initial_state": "E0",
        "accepting_states": {"E1"},
        "transitions": {("E0", f"!{event}"): "E0", ("E0", event): "E1", ("E1", ""): "E1"},
    }


def precedence(first, second):
    """`second` may not happen before the first `first`; the same step is fine."""
    return {
        "alphabet": {first, second},
        "states": {"P0", "P1", "W"},
        "initial_state": "P0",
        "accepting_states": {"P0", "P1"},
        "transitions": {
            ("P0", first): "P1",
            ("P0", f"!{first}&{second}"): "W",
            ("P0", f"!{first}&!{second}"): "P0",
            ("P1", ""): "P1",
            ("W", ""): "W",
        },
    }


def clue_lines(*clauses):
    """The clue block's lines for these hard (pattern, events) clauses."""
    proposals = [
        ClauseProposal(f"{pattern} {events}", pattern, events, PriorityLevel.HARD, "")
        for pattern, *events in clauses
    ]
    dfas = [
        existence(*events) if pattern == "Existence" else precedence(*events)
        for pattern, *events in clauses
    ]
    machine = build_reward_machine(dfas, [False] * len(dfas)).reward_machine
    return critic_clues(proposals, dfas, machine).splitlines()


def redundant_lines(*clauses):
    """The `Redundant:` lines of the clue block for these hard (pattern, events) clauses."""
    return [line for line in clue_lines(*clauses) if line.startswith("Redundant:")]


class RedundantClueTests(unittest.TestCase):
    def test_flags_only_the_existence_a_hard_chain_forces(self) -> None:
        chain = [
            ("Precedence", "blocker_moved", "door_open"),
            ("Precedence", "door_open", "target_picked_up"),
            ("Precedence", "has_door_key", "door_open"),
        ]
        every_step = redundant_lines(
            ("Existence", "blocker_moved"),
            ("Existence", "has_door_key"),
            ("Existence", "target_picked_up"),
            *chain,
        )
        last_step = clue_lines(("Existence", "target_picked_up"), *chain)

        self.assertEqual(len(every_step), 2)
        self.assertTrue(every_step[0].startswith("Redundant: R1 Existence(blocker_moved) "))
        self.assertTrue(every_step[1].startswith("Redundant: R2 Existence(has_door_key) "))
        self.assertEqual(last_step[-2], "Redundant: none.")
        self.assertEqual(
            last_step[-1],
            "Every way to finish includes: blocker_moved, has_door_key, door_open, "
            "target_picked_up.",
        )

    def test_flags_only_the_later_of_two_identical_clauses(self) -> None:
        lines = redundant_lines(("Existence", "at_goal"), ("Existence", "at_goal"))

        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("Redundant: R2 Existence(at_goal) "))


if __name__ == "__main__":
    unittest.main()
