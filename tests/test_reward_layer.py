"""Reward layer contracts on hand-built clause DFAs (no MONA needed)."""

import itertools
import unittest
from types import SimpleNamespace

from scripts.rebuild_rewards import rebuild_switches
from src.arm_fm.pay_order import ceiling_priced, pay_order, record_pay_order
from src.arm_fm.runtime import RewardMachineRuntime
from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.reward_layer import (
    RewardSwitches,
    _Edge,
    _Product,
    _stand_ins,
    build_reward_machine,
    hard_break_charge,
)
from src.config import Configuration

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
# Not an Absence: `a` breaks the rule on the first step only. Its clean state P forgives `a` where
# the broken state R, re-armed like the start Q, would charge it again, so they are no twins.
FIRST_STEP_ONLY = {
    "alphabet": {"a"},
    "states": {"P", "Q", "R"},
    "initial_state": "Q",
    "accepting_states": {"P", "Q"},
    "transitions": {
        ("Q", "a"): "R",
        ("Q", "!a"): "P",
        ("P", "a"): "P",
        ("P", "!a"): "P",
        ("R", "a"): "R",
        ("R", "!a"): "R",
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
# G(x -> F y): `x` without `y` leaves an answer owed (state Q) until a later `y`.
RESPONSE = {
    "alphabet": {"x", "y"},
    "states": {"R", "Q"},
    "initial_state": "R",
    "accepting_states": {"R"},
    "transitions": {
        ("R", "!x"): "R",
        ("R", "x&y"): "R",
        ("R", "x&!y"): "Q",
        ("Q", "y"): "R",
        ("Q", "!y"): "Q",
    },
}
# Precedence(a, b): `b` before any `a` breaks it for good; once `a` is seen the rule is met.
PRECEDENCE = {
    "alphabet": {"a", "b"},
    "states": {"W", "S", "V"},
    "initial_state": "W",
    "accepting_states": {"W", "S"},
    "transitions": {
        ("W", "a"): "S",
        ("W", "!a&!b"): "W",
        ("W", "!a&b"): "V",
        ("S", ""): "S",
        ("V", ""): "V",
    },
}


def never(name):
    """G !name, the shape of NO_LAVA on another proposition."""
    return {
        "alphabet": {name},
        "states": {"R0", "R1", "R2"},
        "initial_state": "R0",
        "accepting_states": {"R1"},
        "transitions": {
            ("R0", f"!{name}"): "R1",
            ("R0", name): "R2",
            ("R1", f"!{name}"): "R1",
            ("R1", name): "R2",
            ("R2", ""): "R2",
        },
    }


def response(trigger, answer, name):
    """G(trigger -> F answer) as MONA gives it: a start state `<name>S` that its idle step leaves."""
    start, open_, owed = f"{name}S", f"{name}R", f"{name}Q"
    return {
        "alphabet": {trigger, answer},
        "states": {start, open_, owed},
        "initial_state": start,
        "accepting_states": {start, open_},
        "transitions": {
            (state, guard): destination
            for state in (start, open_)
            for guard, destination in (
                (f"!{trigger}", open_),
                (f"{trigger}&{answer}", open_),
                (f"{trigger}&!{answer}", owed),
            )
        }
        | {(owed, answer): open_, (owed, f"!{answer}"): owed},
    }


def rewards_of(clauses, soft, propositions, steps, **switches):
    """Run one episode of true-proposition sets through the compiled, serialized machine."""
    machine = build_reward_machine(clauses, soft, RewardSwitches(**switches)).reward_machine
    text = serialize_reward_machine(machine)
    runtime = RewardMachineRuntime(parse_paper_reward_machine(text, propositions=propositions))
    return [runtime.step({name: name in step for name in propositions}).reward for step in steps]


def stand_ins(follows, open_steps, finals=()):
    """``_stand_ins`` on states that go to ``follows[state]`` on ``x``, stay on ``!x`` and pay 0.

    ``open_steps`` gives each state's stages owed per clause; clause 1 is the soft one.
    """
    priced = [
        (_Edge(state, guard, destination), 0.0)
        for state, step in follows.items()
        for guard, destination in (("!x", state), ("x", step))
    ]
    product = _Product("", {"x"}, [], {}, open_steps, {})
    return _stand_ins(priced, product, set(finals), (1,))


class RewardLayerTests(unittest.TestCase):
    def test_a_cycle_counts_as_one_step_and_pays_no_progress(self):
        machine = build_reward_machine((BOUNCE,), (False,)).reward_machine

        for transition in machine.transitions:
            expected = 11.0 if transition.destination == machine.final_state else 0.0
            self.assertEqual(transition.reward, expected)

    def test_hard_violation_enters_one_well_and_the_headers_name_final_and_well(self):
        result = build_reward_machine(
            (GOAL, NO_LAVA), (False, False), RewardSwitches(reward_end_judgment=True)
        )
        text = serialize_reward_machine(result.reward_machine)
        machine = parse_paper_reward_machine(text, propositions=("goal", "lava"))

        self.assertEqual(len(machine.final_states), 1)
        self.assertEqual(len(machine.rejecting_states), 1)
        self.assertIn("REJECTING_STATES: " + machine.rejecting_states[0], text.splitlines())

        runtime = RewardMachineRuntime(machine)
        step = runtime.step({"goal": False, "lava": True})
        # The well's -10 plus the -10 the open goal would cost at the time limit.
        self.assertEqual((step.destination, step.reward), (machine.rejecting_states[0], -20.0))

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
        # A soft rule: each break pays -1 (the default cost) and, as the break and the start share
        # a component, no progress. Finishing pays 11 (1 progress + 10) whether or not the rule held.
        never_lava = ((GOAL, NO_LAVA), (False, True), ("goal", "lava"))
        self.assertEqual(
            rewards_of(*never_lava, [{"lava"}, {"lava"}, {"goal"}]), [-1.0, -1.0, 11.0]
        )
        self.assertEqual(rewards_of(*never_lava, [{"goal"}]), [11.0])

        # A soft goal: finishing without it pays -5; holding it adds nothing.
        get_key = ((GOAL, KEY), (False, True), ("goal", "key"))
        self.assertEqual(rewards_of(*get_key, [{"goal"}]), [7.0])
        self.assertEqual(rewards_of(*get_key, [{"goal", "key"}]), [12.0])
        self.assertEqual(rewards_of(*get_key, [{"key"}, {"goal"}]), [1.0, 11.0])

    def test_each_reward_switch_drops_only_its_own_term_and_completion_stays(self):
        lava = ((GOAL, NO_LAVA), (False, False), ("goal", "lava"))
        soft_lava = ((GOAL, NO_LAVA), (False, True), ("goal", "lava"))
        soft_key = ((GOAL, KEY), (False, True), ("goal", "key"))
        # A hard no-lava rule with the goal still open and soft: the lava edge pays the well (-10)
        # plus the soft end charge (-5), so each part left alone shows a different value.
        open_goal = ((GOAL, NO_LAVA), (True, False), ("goal", "lava"))
        # With the end judgment on (it is off by default) the pay is [11], [-15], [0, 11], [7], [-15].
        rows = (
            ("reward_progress", ((GOAL,), (False,), ("goal",)), [{"goal"}], [10.0]),
            ("reward_well", open_goal, [{"lava"}], [-5.0]),
            ("reward_soft_break", soft_lava, [{"lava"}, {"goal"}], [0.0, 11.0]),
            ("reward_soft_pending", soft_key, [{"goal"}], [12.0]),
            ("reward_end_judgment", open_goal, [{"lava"}], [-10.0]),
        )
        for switch, setup, steps, expected in rows:
            with self.subTest(switch):
                # The flat well: the hard ceiling would price this well edge above -10.
                on = {"reward_end_judgment": True, "hard_ceiling": False}
                self.assertEqual(rewards_of(*setup, steps, **{**on, switch: False}), expected)

        well_off = build_reward_machine(*lava[:2], RewardSwitches(reward_well=False))
        judgment_on = build_reward_machine(*lava[:2], RewardSwitches(reward_end_judgment=True))
        self.assertTrue(well_off.reward_machine.rejecting_states)
        self.assertIsNone(build_reward_machine(*lava[:2]).reward_machine.judgment)
        self.assertIsNotNone(judgment_on.reward_machine.judgment)

    def test_the_promise_cost_adds_one_charge_to_each_step_that_leaves_an_open_hard_promise(self):
        def added(clauses, soft, propositions, steps):
            off = rewards_of(clauses, soft, propositions, steps)
            on = rewards_of(clauses, soft, propositions, steps, reward_promise_cost=True)
            return [round(after - before, 9) for after, before in zip(on, off, strict=True)]

        # Nothing owed pays nothing; an idle step and the closing step with a promise open pay it.
        owed = ((RESPONSE,), (False,), ("x", "y"))
        self.assertEqual(added(*owed, [set(), {"x"}, set(), {"y"}, set()]), [0, 0, -0.1, -0.1, 0])

        # Two promises open still pay it once, flat.
        two = ((response("a", "b", "A"), response("c", "d", "B")), (False, False), "abcd")
        self.assertEqual(added(*two, [{"a", "c"}, set(), {"b"}, set(), {"d"}]), [0, *[-0.1] * 4])

        # The finishing step and the step into the well pay it on top of their own reward.
        open_goal = ((GOAL, NO_LAVA), (False, False), ("goal", "lava"))
        self.assertEqual(added(*open_goal, [set(), {"goal"}]), [-0.1, -0.1])
        self.assertEqual(added(*open_goal, [{"lava"}]), [-0.1])

    def test_a_soft_rule_pays_every_new_break_with_the_recurrent_penalty_and_once_without(self):
        never_lava = ((NO_LAVA,), (True,), ("lava",))

        # A step that breaks it again while still broken pays too: every break costs.
        self.assertEqual(rewards_of(*never_lava, [{"lava"}, {"lava"}]), [-1.0, -1.0])
        self.assertEqual(rewards_of(*never_lava, [{"lava"}, set(), {"lava"}]), [-1.0, 0.0, -1.0])
        self.assertEqual(
            rewards_of(*never_lava, [{"lava"}, set(), {"lava"}], recurrent_soft_penalty=False),
            [-1.0, 0.0, 0.0],
        )

    def test_folding_a_soft_absence_removes_its_broken_state_and_never_changes_the_pay(self):
        never_lava = ((NO_LAVA,), (True,), ("lava",))
        steps = [{"lava"}, {"lava"}, set(), {"lava"}]

        def states(**switches):
            return len(
                build_reward_machine(
                    *never_lava[:2], RewardSwitches(**switches)
                ).reward_machine.states
            )

        self.assertEqual((states(), states(fold_soft_absence=False)), (1, 2))
        self.assertEqual(
            rewards_of(*never_lava, steps), rewards_of(*never_lava, steps, fold_soft_absence=False)
        )
        # Nothing is re-armed without the recurrent penalty, so there is nothing to fold.
        self.assertEqual(states(recurrent_soft_penalty=False), 2)

        # Only an Absence folds: here the fold used to charge the `a` that the clean state forgives.
        first_step_only = ((FIRST_STEP_ONLY,), (True,), ("a",))
        self.assertEqual(rewards_of(*first_step_only, [set(), {"a"}]), [0.0, 0.0])

    def test_minimizing_merges_states_and_keeps_every_pay_and_end(self):
        props = ("goal", "lava", "a", "b")
        # The Absence fold is off, so the soft rule's broken state is left for the minimization.
        # The soft Precedence pays on a broken start, so only its pay tells its start from its end.
        switches = {"fold_soft_absence": False, "reward_end_judgment": True}

        def machine(minimize):
            built = build_reward_machine(
                (GOAL, NO_LAVA, PRECEDENCE),
                (False, True, True),
                RewardSwitches(minimize_machine=minimize, **switches),
            )
            return parse_paper_reward_machine(
                serialize_reward_machine(built.reward_machine), propositions=props
            )

        def play(paper, valuations):
            runtime, seen = RewardMachineRuntime(paper), []
            for valuation in valuations:
                moved = runtime.step(valuation)
                end = paper.judgment
                kind = (
                    "final"
                    if moved.destination in paper.final_states
                    else "well"
                    if moved.destination in paper.rejecting_states
                    else (moved.destination in end.accepting, end.end_charge(moved.destination))
                )
                seen.append((moved.reward, kind))
            return seen

        full, minimal = machine(False), machine(True)
        self.assertLess(len(minimal.states), len(full.states))

        every_valuation = [
            dict(zip(props, values, strict=True))
            for values in itertools.product((False, True), repeat=len(props))
        ]
        for episode in itertools.product(every_valuation, repeat=3):
            self.assertEqual(play(minimal, episode), play(full, episode))

    def test_states_that_step_alike_stay_apart_when_an_end_fact_differs(self):
        apart = {"a": "a", "b": "b"}
        cases = {
            "same facts (control)": ({"a": (1, 1), "b": (1, 1)}, (), {"a": "a", "b": "a"}),
            "a hard stage owed": ({"a": (1, 0), "b": (0, 0)}, (), apart),
            "a soft stage owed": ({"a": (0, 1), "b": (0, 0)}, (), apart),
            "a hard against a soft stage": ({"a": (1, 0), "b": (0, 1)}, (), apart),
            "final": ({"a": (0, 0), "b": (0, 0)}, ("b",), apart),
            "well": ({"a": (0, 0), "W": (0, 0)}, (), {"a": "a", "W": "W"}),
        }
        for name, (open_steps, finals, expected) in cases.items():
            with self.subTest(name):
                follows = {state: state for state in open_steps}
                self.assertEqual(stand_ins(follows, open_steps, finals), expected)

    def test_states_that_differ_only_two_steps_ahead_are_told_apart(self):
        # s0 -> s1 -> s2 ends owing a hard stage; t0 -> t1 -> t2 owes nothing, so the first pass
        # splits only s1 from t1 and a second one is needed to split s0 from t0.
        follows = {"s0": "s1", "s1": "s2", "s2": "s2", "t0": "t1", "t1": "t2", "t2": "t2"}
        open_steps = dict.fromkeys(follows, (0, 0)) | {"s2": (1, 0)}
        self.assertEqual(
            stand_ins(follows, open_steps),
            {"s0": "s0", "s1": "s1", "s2": "s2", "t0": "t0", "t1": "t0", "t2": "t0"},
        )

    def test_without_a_final_progress_runs_toward_the_states_where_no_answer_is_owed(self):
        for soft in (False, True):
            with self.subTest(soft=soft):
                clauses, priorities, propositions = (RESPONSE,), (soft,), ("x", "y")

                # The trigger costs one step of progress and the answer pays it back.
                self.assertEqual(
                    rewards_of(clauses, priorities, propositions, [{"x"}, {"y"}]), [-1.0, 1.0]
                )
                self.assertEqual(
                    rewards_of(clauses, priorities, propositions, [{"x"}, set(), {"y"}]),
                    [-1.0, 0.0, 1.0],
                )
                result = build_reward_machine(clauses, priorities)
                self.assertIsNone(result.reward_machine.final_state)
                self.assertEqual(result.inert_soft_clauses, ())

    def test_a_rule_is_weighted_by_the_chain_it_hands_off_to(self):
        names = ("a", "b", "c", "d")

        # Each answer closes one rule and opens the next, so each middle step pays like the last.
        chain = (response("a", "b", "R0"), response("b", "c", "R1"), response("c", "d", "R2"))
        self.assertEqual(
            rewards_of(chain, (False,) * 3, names, [{"a"}, {"b"}, {"c"}, {"d"}]),
            [-3.0, 1.0, 1.0, 1.0],
        )

        # One event closes a rule and opens two: the rule weighs both (sum), so the step pays 1.
        fork = (response("a", "b", "R0"), response("b", "c", "R1"), response("b", "d", "R2"))
        self.assertEqual(
            rewards_of(fork, (False,) * 3, names, [{"a"}, {"b"}, {"c"}, {"d"}]),
            [-3.0, 1.0, 1.0, 1.0],
        )

    def test_the_end_charge_and_the_well_charge_count_the_stages_still_owed(self):
        names = ("a", "b", "c", "d", "lava")
        chain = (
            response("a", "b", "R0"),
            response("b", "c", "R1"),
            response("c", "d", "R2"),
            NO_LAVA,
        )
        switches = RewardSwitches(reward_end_judgment=True)
        machine = build_reward_machine(chain, (False,) * 4, switches).reward_machine
        text = serialize_reward_machine(machine)
        paper = parse_paper_reward_machine(text, propositions=names)

        def play(steps):
            runtime = RewardMachineRuntime(paper)
            return [runtime.step({name: name in step for name in names}) for step in steps]

        # The pay so far plus what the time limit would charge: 10 per stage owed, 11 with the
        # stage's progress already paid, so each answer lifts the end total by one stage.
        totals = []
        paid = 0.0
        for step in play([{"a"}, {"b"}, {"c"}, {"d"}]):
            paid += step.reward
            totals.append(paid + paper.judgment.end_charge(step.destination))
        self.assertEqual(totals, [-33.0, -22.0, -11.0, 0.0])

        # A hard break pays the well plus the same charge: three stages owed, not the one open rule.
        well = play([{"a"}, {"lava"}])[-1]
        self.assertEqual((well.destination, well.reward), (paper.rejecting_states[0], -40.0))

    def test_the_hard_break_costs_the_discounted_soft_ceiling_only_where_soft_rules_repeat(self):
        # k S (1 - g^T) / (1 - g) plus one progress unit, k soft breaks a step; k S T at g 1;
        # never under the flat 10 + 1. Rows: S, k, g, T, charge.
        table = (
            (1, 1, 0.99, 300, -96.0959),  # the default pricing
            (2.5, 1, 0.99, 300, -238.7398),
            (1, 2, 0.99, 300, -191.1918),
            (5, 1, 0.99, 300, -476.4796),
            (1, 1, 1, 300, -301),
            (1, 2, 1, 300, -601),
            (1, 1, 0.9, 5, -11),  # the flat well, not the ceiling, is the larger
        )
        for cost, breaks, gamma, limit, expected in table:
            with self.subTest(cost=cost, breaks=breaks, gamma=gamma, limit=limit):
                charge = hard_break_charge(cost, gamma, limit, breaks)
                self.assertAlmostEqual(charge, expected, places=4)

        def well_charges(soft, **switches):
            clauses = (GOAL, NO_LAVA, *soft)
            priorities = (False, False, *[True] * len(soft))
            machine = build_reward_machine(
                clauses, priorities, RewardSwitches(**switches)
            ).reward_machine
            return {
                transition.reward
                for transition in machine.transitions
                if transition.destination in machine.rejecting_states
            }

        # The defaults price the ceiling at S 1, g 0.99, one break a step: only the level's step
        # limit is left to name.
        ceiling = {"step_limit": 300}
        # The breaks per step are the user's setting (default 1), not the soft clause count.
        (one,) = well_charges((KEY,), **ceiling)
        self.assertAlmostEqual(one, hard_break_charge(1, 0.99, 300, 1), places=6)
        (still_one,) = well_charges((KEY, BOUNCE), **ceiling)
        self.assertAlmostEqual(still_one, hard_break_charge(1, 0.99, 300, 1), places=6)
        (two,) = well_charges((KEY, BOUNCE), **ceiling, soft_breaks_per_step=2)
        self.assertAlmostEqual(two, hard_break_charge(1, 0.99, 300, 2), places=6)
        # No soft rule (it needs no step limit), charge-once soft rules, or the rule off: the flat
        # well.
        self.assertEqual(well_charges(()), {-10.0})
        self.assertEqual(well_charges((KEY,), **ceiling, recurrent_soft_penalty=False), {-10.0})
        self.assertEqual(well_charges((KEY,), hard_ceiling=False), {-10.0})
        with self.assertRaisesRegex(ValueError, "step limit"):
            well_charges((KEY,))

    def test_the_default_pricing_passes_the_pay_order_where_the_flat_one_fails(self):
        # A hard and a soft Absence: a stream of soft breaks costs more than the flat hard break
        # (S 5: -475 against -10), so breaking the hard rule would pay better.
        clauses, priorities, names = (NO_LAVA, never("spill")), (False, True), ("lava", "spill")
        for label, switches, passes in (
            ("default", {"step_limit": 300}, True),
            ("flat S 5", {"hard_ceiling": False, "soft_break_cost": 5.0}, False),
        ):
            with self.subTest(label):
                layer = build_reward_machine(clauses, priorities, RewardSwitches(**switches))
                text = serialize_reward_machine(layer.reward_machine)
                machine = parse_paper_reward_machine(text, propositions=names)
                self.assertEqual(pay_order(machine, 0.99, 300).broken is None, passes)

    def test_a_rebuild_keeps_the_pricing_the_bundle_records_unless_the_command_gives_another(self):
        config = Configuration(step_limit=300)
        made_at_s5 = {"soft_break_cost": 5.0, "gamma": 0.99, "soft_breaks_per_step": 1}
        # Rows: the options given, what the bundle records, then the cost and ceiling of the
        # rebuild and where each came from.
        rows = (
            ({}, made_at_s5, 5.0, False, ("bundle", "bundle: made before the ceiling, so flat")),
            ({"hard_ceiling": False}, made_at_s5, 5.0, False, ("bundle", "command")),
            ({"hard_ceiling": True}, made_at_s5, 5.0, True, ("bundle", "command")),
            (
                {"hard_ceiling": True, "soft_break_cost": 1.0},
                made_at_s5,
                1.0,
                True,
                ("command", "command"),
            ),
            (
                {},
                {},
                1.0,
                False,
                ("default: the bundle records none", "bundle: made before the ceiling, so flat"),
            ),
        )
        for given, settings, cost, ceiling, origins in rows:
            with self.subTest(given=given, settings=settings):
                bundle = SimpleNamespace(
                    manifest=SimpleNamespace(effective_settings=settings),
                    reward_machine=SimpleNamespace(judgment=None),
                )
                switches, origin = rebuild_switches(config, bundle, given)
                self.assertEqual((switches.soft_break_cost, switches.hard_ceiling), (cost, ceiling))
                self.assertEqual((origin["soft_break_cost"], origin["hard_ceiling"]), origins)
                self.assertEqual((switches.step_limit, origin["step_limit"]), (300, "command"))
        bundle = SimpleNamespace(
            manifest=SimpleNamespace(effective_settings={}),
            reward_machine=SimpleNamespace(judgment=None),
        )
        switches, origin = rebuild_switches(Configuration(), bundle, {})
        self.assertEqual(
            (switches.step_limit, origin["step_limit"]), (None, "none: not recorded, not given")
        )

    def test_a_pay_order_check_that_cannot_run_is_recorded_and_never_raises(self):
        for step_limit, summary in (
            (None, "not checked: no step limit"),
            (300, "check failed: "),  # no machine to walk
        ):
            with self.subTest(step_limit=step_limit):
                settings = {"gamma": 0.99, "step_limit": step_limit, "soft_breaks_per_step": 1}
                manifest = SimpleNamespace(effective_settings=settings, generation={})
                record = record_pay_order(SimpleNamespace(manifest=manifest, reward_machine=None))
                self.assertIsNone(record["ok"])
                self.assertTrue(record["summary"].startswith(summary))
                self.assertEqual(settings["pay_order"], record)

    def test_only_a_bundle_priced_by_the_ceiling_ties_training_to_gamma_and_step_limit(self):
        hard, soft = [["Existence", ["a"], "hard"]], [["Absence", ["b"], "soft"]]
        ceiling = {"hard_ceiling": True}
        # Rows: recorded settings, stored clauses (None: none stored), whether the ceiling prices it.
        rows = (
            (ceiling, hard + soft, True),
            (ceiling, None, True),
            (ceiling, hard, False),  # no soft rule: the flat well, whatever gamma the run uses
            ({}, hard + soft, False),  # made before the ceiling existed
            ({**ceiling, "recurrent_soft_penalty": False}, hard + soft, False),
        )
        for settings, clauses, expected in rows:
            with self.subTest(settings=settings, clauses=clauses):
                generation = {} if clauses is None else {"clauses": clauses}
                manifest = SimpleNamespace(effective_settings=settings, generation=generation)
                self.assertEqual(ceiling_priced(SimpleNamespace(manifest=manifest)), expected)

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
