"""The too-simple machine check and the "episode could not start" limit.

Run with ``PYTHONPATH=app python -m unittest tests.test_early_end``.
"""

import unittest

from src.benchmark.early_end import episode_cannot_start, machine_too_simple, start_limit
from src.compiler.rm_format import parse_paper_reward_machine


def machine(finals: str, transitions: str, states: str = "u0, u1, u2") -> object:
    text = (
        f"REWARD_MACHINE:\nSTATES: {states}\nINITIAL_STATE: u0\nFINAL_STATES: {finals}\n"
        f"TRANSITION_FUNCTION:\n{transitions}\nREWARD_FUNCTION:\n"
    )
    return parse_paper_reward_machine(text)


class MachineTooSimpleTest(unittest.TestCase):
    def test_flags_a_final_start_and_a_final_reached_with_no_proposition(self):
        start_final = machine(
            "u0, u1", "(u0, a) -> u1\n(u0, else) -> u0\n(u1, else) -> u1", "u0, u1"
        )
        self.assertIn("start state u0 is final", machine_too_simple(start_final))
        chain = machine("u2", "(u0, else) -> u1\n(u1, else) -> u2\n(u2, else) -> u2", "u0, u1, u2")
        self.assertIn("u0 -> u1 -> u2", machine_too_simple(chain))

    def test_keeps_a_machine_that_needs_a_proposition_or_ends_in_a_rejecting_state(self):
        normal = machine("u1", "(u0, a) -> u1\n(u0, else) -> u0\n(u1, else) -> u1", "u0, u1")
        self.assertIsNone(machine_too_simple(normal))
        rejecting_text = (
            "REWARD_MACHINE:\nSTATES: u0, u1, u2\nINITIAL_STATE: u0\nFINAL_STATES: u2\n"
            "REJECTING_STATES: u1\nTRANSITION_FUNCTION:\n(u0, else) -> u1\n(u1, else) -> u1\n"
            "(u2, else) -> u2\nREWARD_FUNCTION:\n"
        )
        self.assertIsNone(machine_too_simple(parse_paper_reward_machine(rejecting_text)))


class StartLabelsTest(unittest.TestCase):
    def test_a_negated_guard_is_free_only_when_the_proposition_is_false_at_reset(self):
        unlocked_task = machine(
            "u1", "(u0, !door_locked) -> u1\n(u0, else) -> u0\n(u1, else) -> u1", "u0, u1"
        )
        locked = {1: {"door_locked": True}}
        self.assertIsNone(machine_too_simple(unlocked_task))  # static: not always true
        self.assertIsNone(machine_too_simple(unlocked_task, locked))
        self.assertIn(
            "seeds [2]", machine_too_simple(unlocked_task, {**locked, 2: {"door_locked": False}})
        )

    def test_a_guard_true_in_the_start_layout_is_flagged_with_the_seeds(self):
        room = machine("u1", "(u0, in_room_a) -> u1\n(u0, else) -> u0\n(u1, else) -> u1", "u0, u1")
        self.assertIsNone(machine_too_simple(room))  # static scan cannot see the layout
        reason = machine_too_simple(room, {1: {"in_room_a": True}, 2: {"in_room_a": False}})
        self.assertIn("u0 -> u1", reason)
        self.assertIn("seeds [1]", reason)
        self.assertIsNone(machine_too_simple(room, {2: {"in_room_a": False}}))

    def test_a_walk_holds_the_labels_fixed_across_states(self):
        chain = machine(
            "u2",
            "(u0, a) -> u1\n(u0, else) -> u0\n(u1, a) -> u2\n(u1, else) -> u1\n(u2, else) -> u2",
        )
        self.assertIn("u0 -> u1 -> u2", machine_too_simple(chain, {1: {"a": True}}))
        self.assertIsNone(machine_too_simple(chain, {1: {"a": False}}))

    def test_a_final_start_is_flagged_with_and_without_labels(self):
        start_final = machine("u0", "(u0, a) -> u1\n(u0, else) -> u0\n(u1, else) -> u1", "u0, u1")
        self.assertIn("start state u0 is final", machine_too_simple(start_final))
        self.assertIn("start state u0 is final", machine_too_simple(start_final, {1: {"a": False}}))

    def test_a_rejecting_state_stops_the_walk(self):
        text = (
            "REWARD_MACHINE:\nSTATES: u0, u1, u2\nINITIAL_STATE: u0\nFINAL_STATES: u2\n"
            "REJECTING_STATES: u1\nTRANSITION_FUNCTION:\n(u0, a) -> u1\n(u0, else) -> u0\n"
            "(u1, a) -> u2\n(u1, else) -> u1\n(u2, else) -> u2\nREWARD_FUNCTION:\n"
        )
        self.assertIsNone(machine_too_simple(parse_paper_reward_machine(text), {1: {"a": True}}))


class CannotStartTest(unittest.TestCase):
    def test_limit_is_a_tenth_of_the_expected_length_and_never_below_one_step(self):
        self.assertEqual(start_limit(21), 3)
        self.assertEqual(start_limit(21, 0.05), 2)
        self.assertEqual(start_limit(None), 1)
        self.assertEqual(start_limit(4), 1)

    def test_only_a_machine_stop_in_a_final_state_within_the_limit_counts(self):
        self.assertTrue(episode_cannot_start(1, True, 21))
        self.assertTrue(episode_cannot_start(3, True, 21))
        self.assertFalse(episode_cannot_start(4, True, 21))
        self.assertFalse(episode_cannot_start(1, False, 21))  # env ended it, or a rejecting state


if __name__ == "__main__":
    unittest.main()
