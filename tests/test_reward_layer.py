"""Reward layer contracts on hand-built clause DFAs (no MONA needed)."""

import unittest

from src.arm_fm.runtime import RewardMachineRuntime
from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.reward_layer import build_reward_machine

# F goal: unsatisfied until `goal` is seen, then it stays satisfied.
GOAL = {
    "alphabet": {"goal"},
    "states": {"G0", "G1"},
    "initial_state": "G0",
    "accepting_states": {"G1"},
    "transitions": {("G0", "!goal"): "G0", ("G0", "goal"): "G1", ("G1", ""): "G1"},
}
# F key, the same shape as GOAL on another proposition.
KEY = {
    "alphabet": {"key"},
    "states": {"K0", "K1"},
    "initial_state": "K0",
    "accepting_states": {"K1"},
    "transitions": {("K0", "!key"): "K0", ("K0", "key"): "K1", ("K1", ""): "K1"},
}
# G !lava: the first step already satisfies it; `lava` breaks it for good.
NO_LAVA = {
    "alphabet": {"lava"},
    "states": {"R0", "R1", "R2"},
    "initial_state": "R0",
    "accepting_states": {"R1"},
    "transitions": {
        ("R0", "!lava"): "R1",
        ("R0", "lava"): "R2",
        ("R1", "!lava"): "R1",
        ("R1", "lava"): "R2",
        ("R2", ""): "R2",
    },
}
# A goal that can bounce between two open states before `y` finishes it.
BOUNCE = {
    "alphabet": {"x", "y"},
    "states": {"P", "Q", "D"},
    "initial_state": "P",
    "accepting_states": {"D"},
    "transitions": {
        ("P", "!x&!y"): "P",
        ("P", "x&!y"): "Q",
        ("P", "y"): "D",
        ("Q", "!y"): "P",
        ("Q", "y"): "D",
        ("D", ""): "D",
    },
}


def rewards_of(clauses, soft, propositions, steps, recurrent_soft_penalty=True):
    """Run one episode of true-proposition sets through the compiled, serialized machine."""
    machine = build_reward_machine(clauses, soft, recurrent_soft_penalty).reward_machine
    text = serialize_reward_machine(machine)
    runtime = RewardMachineRuntime(parse_paper_reward_machine(text, propositions=propositions))
    return [runtime.step({name: name in step for name in propositions}).reward for step in steps]


class RewardLayerTests(unittest.TestCase):
    def test_a_cycle_counts_as_one_step_and_pays_no_progress(self):
        machine = build_reward_machine((BOUNCE,), (False,)).reward_machine

        for transition in machine.transitions:
            expected = 1.1 if transition.destination == machine.final_state else 0.0
            self.assertEqual(transition.reward, expected)

    def test_hard_violation_enters_one_well_and_the_headers_name_final_and_well(self):
        result = build_reward_machine((GOAL, NO_LAVA), (False, False))
        text = serialize_reward_machine(result.reward_machine)
        machine = parse_paper_reward_machine(text, propositions=("goal", "lava"))

        self.assertEqual(len(machine.final_states), 1)
        self.assertEqual(len(machine.rejecting_states), 1)
        self.assertIn("REJECTING_STATES: " + machine.rejecting_states[0], text.splitlines())

        runtime = RewardMachineRuntime(machine)
        step = runtime.step({"goal": False, "lava": True})
        self.assertEqual((step.destination, step.reward), (machine.rejecting_states[0], -1.0))

    def test_an_idle_first_step_pays_nothing_and_finishing_pays_the_same_either_way(self):
        clauses, soft, propositions = (GOAL, NO_LAVA), (False, False), ("goal", "lava")

        after_idle = rewards_of(clauses, soft, propositions, [set(), {"goal"}])
        at_once = rewards_of(clauses, soft, propositions, [{"goal"}])

        self.assertEqual(after_idle[0], 0.0)
        self.assertEqual(after_idle[1], at_once[0])

    def test_a_rule_clause_adds_no_no_step_yet_start(self):
        machine = build_reward_machine((GOAL, NO_LAVA), (False, False)).reward_machine

        # The start, the final and the well; an idle first step stays in the start.
        self.assertEqual(len(machine.states), 3)

    def test_a_broken_soft_rule_pays_the_break_and_a_pending_soft_goal_pays_at_the_finish(self):
        # A soft rule: the break pays -0.5 and, as the break and the start share a component, no
        # progress. Finishing pays 1.1 (0.1 progress + 1) whether or not the rule held.
        never_lava = ((GOAL, NO_LAVA), (False, True), ("goal", "lava"))
        self.assertEqual(rewards_of(*never_lava, [{"lava"}, {"lava"}, {"goal"}]), [-0.5, 0.0, 1.1])
        self.assertEqual(rewards_of(*never_lava, [{"goal"}]), [1.1])

        # A soft goal: finishing without it pays -0.5; holding it adds nothing.
        get_key = ((GOAL, KEY), (False, True), ("goal", "key"))
        self.assertEqual(rewards_of(*get_key, [{"goal"}]), [0.7])
        self.assertEqual(rewards_of(*get_key, [{"goal", "key"}]), [1.2])
        self.assertEqual(rewards_of(*get_key, [{"key"}, {"goal"}]), [0.1, 1.1])

    def test_a_soft_rule_pays_every_new_break_with_the_recurrent_penalty_and_once_without(self):
        never_lava = ((NO_LAVA,), (True,), ("lava",))

        # A step that breaks it again while still broken is free; the rule re-arms on the next.
        self.assertEqual(rewards_of(*never_lava, [{"lava"}, {"lava"}]), [-0.5, 0.0])
        self.assertEqual(rewards_of(*never_lava, [{"lava"}, set(), {"lava"}]), [-0.5, 0.0, -0.5])
        self.assertEqual(
            rewards_of(*never_lava, [{"lava"}, set(), {"lava"}], recurrent_soft_penalty=False),
            [-0.5, 0.0, 0.0],
        )

    def test_a_hard_goal_that_a_hard_rule_forbids_is_rejected(self):
        forbids_goal = {
            "alphabet": {"goal"},
            "states": {"N0", "N1", "N2"},
            "initial_state": "N0",
            "accepting_states": {"N1"},
            "transitions": {
                ("N0", "!goal"): "N1",
                ("N0", "goal"): "N2",
                ("N1", "!goal"): "N1",
                ("N1", "goal"): "N2",
                ("N2", ""): "N2",
            },
        }
        with self.assertRaisesRegex(ValueError, "conflicting clauses"):
            build_reward_machine((GOAL, forbids_goal), (False, False))


if __name__ == "__main__":
    unittest.main()
