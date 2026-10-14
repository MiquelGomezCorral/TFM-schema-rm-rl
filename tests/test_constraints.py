"""Environment constraints: the parser and the pass that removes unreachable states."""

import unittest
from pathlib import Path

from src.arm_fm.runtime import RewardMachineRuntime
from src.compiler import (
    ClauseProposal,
    Proposal,
    build_compilation_result,
    parse_paper_reward_machine,
    parse_reward_machine,
    serialize_reward_machine,
)
from src.compiler.constraints import prune_by_constraints
from src.compiler.reward_machine import RewardMachineStructure, Transition
from src.config import PriorityLevel
from src.models import (
    EnvironmentDescription,
    EnvironmentValidationError,
    ExclusiveConstraint,
    LatchConstraint,
    OrderConstraint,
)

ROOT = Path(__file__).parents[1]
KEY_CORRIDOR_ENVIRONMENT = ROOT / "examples" / "arm-fm" / "minigrid-key-corridor" / "environment.md"
KEY_CORRIDOR_RM = Path(__file__).parent / "data" / "key_corridor_13_states.rm"

PROPOSITIONS = (
    "# Demo\n## Propositions\n- `key`: Key held\n- `door`: Door open\n- `goal`: At goal\n"
)

# F key and F goal, the same shapes as the reward layer tests.
KEY = {
    "alphabet": {"key"},
    "states": {"K0", "K1"},
    "initial_state": "K0",
    "accepting_states": {"K1"},
    "transitions": {("K0", "!key"): "K0", ("K0", "key"): "K1", ("K1", ""): "K1"},
}
GOAL = {
    "alphabet": {"goal"},
    "states": {"G0", "G1"},
    "initial_state": "G0",
    "accepting_states": {"G1"},
    "transitions": {("G0", "!goal"): "G0", ("G0", "goal"): "G1", ("G1", ""): "G1"},
}


def environment(constraints: str) -> EnvironmentDescription:
    markdown = PROPOSITIONS + ("\n## Constraints\n\n" + constraints if constraints else "")
    return EnvironmentDescription.from_markdown(markdown, source="demo.md")


def machine(*transitions: tuple[int, int, str], final: int) -> RewardMachineStructure:
    """A zero-reward machine over states 0..max, starting at 0, from (source, destination, guard)."""
    states = range(max(max(source, destination) for source, destination, _ in transitions) + 1)
    return RewardMachineStructure(
        states=tuple(states),
        initial_state=0,
        final_state=final,
        rejecting_states=(),
        transitions=tuple(
            Transition(source, destination, (guard,), 0.0)
            for source, destination, guard in transitions
        ),
    )


def episode_rewards(structure: RewardMachineStructure, steps: list[set[str]]) -> list[float]:
    """Run one episode of true-proposition sets through the serialized, parsed machine."""
    names = EnvironmentDescription.from_file(KEY_CORRIDOR_ENVIRONMENT).proposition_ids
    text = serialize_reward_machine(structure)
    runtime = RewardMachineRuntime(parse_paper_reward_machine(text, propositions=names))
    return [runtime.step({name: name in step for name in names}).reward for step in steps]


def compile_key_and_goal(constraints: str):
    proposal = Proposal(
        "Get the key and reach the goal",
        tuple(
            ClauseProposal(f"Eventually {name}", "Existence", (name,), PriorityLevel.HARD, "unused")
            for name in ("key", "goal")
        ),
    )
    return build_compilation_result(environment(constraints), proposal, (KEY, GOAL))


class ConstraintParserTests(unittest.TestCase):
    def test_the_three_shapes_parse_and_the_reason_is_ignored(self):
        parsed = environment(
            "- `goal` cannot become true before `door`: only an open door leads there.\n"
            "- `key` and `goal` never hold together: one object at a time.\n"
            "- `door` cannot become false once true\n"
        )

        self.assertEqual(
            parsed.constraints,
            (
                OrderConstraint("goal", "door"),
                ExclusiveConstraint("key", "goal"),
                LatchConstraint("door"),
            ),
        )

    def test_an_absent_section_means_no_constraints(self):
        self.assertEqual(environment("").constraints, ())

    def test_an_undeclared_proposition_is_rejected_with_its_line(self):
        with self.assertRaisesRegex(
            EnvironmentValidationError, r"demo.md:\d+: .*undeclared.*'gate'"
        ):
            environment("- `gate` cannot become false once true\n")

    def test_a_constraint_naming_one_proposition_twice_is_rejected(self):
        with self.assertRaisesRegex(EnvironmentValidationError, r"demo.md:\d+: .*twice"):
            environment("- `key` and `key` never hold together\n")

    def test_a_duplicate_constraints_section_is_rejected(self):
        markdown = PROPOSITIONS + "\n## Constraints\n\n## Constraints\n"

        with self.assertRaisesRegex(EnvironmentValidationError, "duplicate '## Constraints'"):
            EnvironmentDescription.from_markdown(markdown, source="demo.md")

    def test_a_bullet_in_no_shape_is_rejected_with_its_line(self):
        with self.assertRaisesRegex(EnvironmentValidationError, r"demo.md:\d+: expected"):
            environment("- `goal` usually happens after `door`\n")


class ConstraintPruningTests(unittest.TestCase):
    def test_key_corridor_keeps_only_the_states_the_environment_can_reach(self):
        machine = parse_reward_machine(KEY_CORRIDOR_RM.read_text(encoding="utf-8"))
        constraints = EnvironmentDescription.from_file(KEY_CORRIDOR_ENVIRONMENT).constraints

        pruning = prune_by_constraints(machine, constraints)

        pruned = pruning.reward_machine
        self.assertEqual(len(machine.states), 13)
        self.assertEqual(len(pruned.states), 6)
        self.assertEqual(pruning.removed_states, (1, 2, 4, 5, 6, 8, 11))
        self.assertEqual(pruned.rejecting_states, ())
        self.assertIsNotNone(pruned.final_state)
        original = {(item.condition, item.reward) for item in machine.transitions}
        self.assertLessEqual(
            {(item.condition, item.reward) for item in pruned.transitions}, original
        )

    def test_key_corridor_pays_the_same_rewards_on_runs_the_environment_can_produce(self):
        full = parse_reward_machine(KEY_CORRIDOR_RM.read_text(encoding="utf-8"))
        constraints = EnvironmentDescription.from_file(KEY_CORRIDOR_ENVIRONMENT).constraints
        pruned = prune_by_constraints(full, constraints).reward_machine
        in_order = [
            {"key_found"},
            {"has_matching_key"},
            {"target_door_open"},
            {"target_room_entered"},
            {"target_picked_up"},
        ]
        together = [{"key_found", "has_matching_key"}, {"target_door_open", "target_room_entered"}]

        for steps in (in_order, [*together, {"target_picked_up"}]):
            with self.subTest(steps=steps):
                rewards = episode_rewards(pruned, steps)
                self.assertEqual(rewards, episode_rewards(full, steps))
                self.assertGreater(rewards[-1], 1.0)

    def test_before_counts_the_same_step_and_a_latch_blocks_falling_back(self):
        # In state 0 no `a` has been seen yet, so `b&!a` is impossible; `a&b` counts as `a` first.
        order = prune_by_constraints(
            machine((0, 1, "b&!a"), (0, 2, "a&b"), (0, 3, "a&!b"), (3, 2, "b"), final=2),
            (OrderConstraint("b", "a"),),
        )
        latch = prune_by_constraints(
            machine((0, 1, "a"), (1, 2, "!a"), (1, 3, "a"), final=3), (LatchConstraint("a"),)
        )

        self.assertEqual((order.removed_states, order.removed_transitions), ((1,), 1))
        self.assertIn(("a&b",), [item.condition for item in order.reward_machine.transitions])
        self.assertEqual(latch.removed_states, (2,))
        self.assertEqual(
            [item.condition for item in latch.reward_machine.transitions], [("a",), ("a",)]
        )

    def test_an_exclusive_pair_never_fires_together(self):
        pruning = prune_by_constraints(
            machine((0, 1, "a&b"), (0, 2, "a&!b"), final=2), (ExclusiveConstraint("a", "b"),)
        )

        self.assertEqual(pruning.removed_states, (1,))
        self.assertEqual(pruning.removed_transitions, 1)

    def test_without_constraints_even_a_wide_machine_is_returned_as_is(self):
        guard = "&".join(f"p{index}" for index in range(20))
        wide = machine((0, 1, guard), final=1)

        self.assertIs(prune_by_constraints(wide, ()).reward_machine, wide)

    def test_no_constraints_returns_the_machine_unchanged(self):
        machine = parse_reward_machine(KEY_CORRIDOR_RM.read_text(encoding="utf-8"))

        pruning = prune_by_constraints(machine, ())

        self.assertIs(pruning.reward_machine, machine)
        self.assertEqual((pruning.removed_states, pruning.removed_transitions), ((), 0))

    def test_the_removal_is_named_in_the_compile_warnings(self):
        result = compile_key_and_goal("- `goal` cannot become true before `key`\n")

        notes = [
            warning for warning in result.warnings if warning.startswith("Constraints removed")
        ]
        self.assertEqual(len(notes), 1)
        self.assertRegex(
            notes[0], r"^Constraints removed \d+ states and \d+ transitions \S.*reach$"
        )
        self.assertEqual(compile_key_and_goal("").warnings, ())

    def test_constraints_that_cut_off_the_final_state_fail_the_compilation(self):
        with self.assertRaisesRegex(ValueError, "final state unreachable"):
            compile_key_and_goal(
                "- `goal` cannot become true before `key`\n"
                "- `key` cannot become true before `goal`\n"
                "- `key` and `goal` never hold together\n"
            )


if __name__ == "__main__":
    unittest.main()
