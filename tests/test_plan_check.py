"""The plan check's rule table: what each way a plan's episode ends says about the machine."""

import unittest

from src.arm_fm.artifacts import ArtifactBundle, BundleManifest
from src.benchmark.declare_judge import judge_trace
from src.benchmark.plan_check import FINAL, OPEN, SOFT_UNPAID, WELL, _price_soft_breaks, _problems
from src.benchmark.traces import (
    HARD_BREAK,
    SOFT_BREAK,
    SOLVE,
    Replay,
    TraceRecord,
    _pay_open_solves,
    check_row,
)
from src.compiler.rm_format import parse_paper_reward_machine

# kind, has a final state, where the episode stopped, step it stopped at, owed, rewards, problem
CASES = [
    (SOLVE, True, FINAL, 5, 0.0, [0.0, 1.0], None),
    (SOLVE, True, WELL, 5, 0.0, [0.0], "enters the well at step 5"),
    (SOLVE, True, OPEN, 9, 0.0, [0.0], "ends in u2, not the final"),
    (SOLVE, False, OPEN, 9, 0.0, [0.0], None),
    (SOLVE, False, OPEN, 9, -1.0, [0.0], "ends owing -1.0"),
    (HARD_BREAK, True, FINAL, 4, 0.0, [0.0], "reaches the final at step 4"),
    (HARD_BREAK, True, OPEN, 9, 0.0, [0.0], None),
    (HARD_BREAK, False, OPEN, 9, 0.0, [0.0], None),  # with no final, the pay test judges it
    (HARD_BREAK, False, WELL, 3, 0.0, [0.0], None),
    (SOFT_BREAK, True, FINAL, 4, 0.0, [0.0, -0.5], None),
    (SOFT_BREAK, True, FINAL, 4, 0.0, [0.0, 1.0], SOFT_UNPAID),
    (SOLVE, True, FINAL, 0, 0.0, [], "ends the episode before the agent acts"),
    (HARD_BREAK, True, WELL, 0, 0.0, [], "ends the episode before the agent acts"),
]


class ProblemsTest(unittest.TestCase):
    def test_each_ending(self):
        for kind, has_final, end, steps, owed, rewards, problem in CASES:
            with self.subTest(kind=kind, end=end, steps=steps, owed=owed):
                ending = {"end": end, "steps": steps, "end_state": "u2", "owed": owed}
                found = _problems(kind, has_final, ending, rewards)
                self.assertEqual(found, [problem] if problem else [])


# A soft break with no negative step, against a solving run that ends in the final paying [12, 10.08]:
# where it ends, its plain pay, and whether it stays unpaid
SOFT_CASES = [
    (FINAL, 7.0, False),  # Existence broken at the end: priced by a smaller payout
    (FINAL, 12.0, True),  # soft clause dropped: less discounted pay (6.33) alone does not count
    (OPEN, 1.0, True),  # soft rule compiled as hard: the plan reaches the goal, not the final
]
SOLVE_RUN = {"kind": SOLVE, "seed": 1, "problems": [], "end": FINAL, "pay": [12.0, 10.08]}


class SoftBreakPayTest(unittest.TestCase):
    def test_against_the_solving_run(self):
        for end, paid, unpaid in SOFT_CASES:
            with self.subTest(end=end, paid=paid):
                soft = {"kind": SOFT_BREAK, "seed": 1, "end": end, "pay": [paid, 6.33]}
                soft["problems"] = [SOFT_UNPAID]
                _price_soft_breaks([SOLVE_RUN, soft])
                self.assertEqual(soft["problems"], [SOFT_UNPAID] if unpaid else [])


# The FARM machine of "Try to flip the switch on the wall at some point" (soft Existence): no final
# state and no end judgment, so no trace ends accepted. {reward} is what the flip pays.
SWITCH_RM = """REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES:
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, switch_toggled) -> u1
REWARD_FUNCTION:
(u0, switch_toggled, u1) -> {reward}
"""
OFF, ON = {"switch_toggled": False}, {"switch_toggled": True}


def _record(plan: str, labels: list[dict[str, bool]]) -> TraceRecord:
    return TraceRecord(
        suite="templates",
        card_id="switch",
        plan=plan,
        source="plan",
        gym_id="",
        env_kwargs={},
        layout=None,
        layout_seed=None,
        reset_seed=1,
        actions=[0, 0],
        labels=labels,
        env_rewards=[0.0, 0.0],
        terminated=False,
        truncated=True,
    )


class NoFinalSolvePayTest(unittest.TestCase):
    """R43 judges a solve its machine cannot accept by pay, as the plan check does (D3)."""

    def test_solve_against_the_wrong_trace(self):
        for reward, passed in ((1, True), (0, False)):  # a flip that pays nothing is no better
            with self.subTest(reward=reward):
                machine = parse_paper_reward_machine(SWITCH_RM.format(reward=reward))
                bundle = ArtifactBundle(BundleManifest("flip the switch", "MiniGrid"), machine)
                traces = [
                    (_record("solve", [OFF, ON]), Replay(["u0", "u0", "u1"], [], [0.0, reward])),
                    (_record("wrong-0", [OFF, OFF]), Replay(["u0", "u0", "u0"], [], [0.0, 0.0])),
                ]
                expect = [("Existence", ("switch_toggled",), "soft")]
                rows = [
                    check_row(bundle, record, judge_trace(expect, record.labels), replay)
                    for record, replay in traces
                ]
                _pay_open_solves(rows, machine)
                self.assertEqual(rows[0]["ok"], passed)


if __name__ == "__main__":
    unittest.main()
