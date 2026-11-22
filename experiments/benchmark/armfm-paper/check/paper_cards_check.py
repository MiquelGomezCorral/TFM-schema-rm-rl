"""No-model checks of the armfm-paper cards, on hand-written reference machines.

Per card of experiments/benchmark/armfm-paper/tasks.json:
  card    the card contract (load_cards) finds no problem
  plans   the plan checker passes with a hand-written machine of the task (ARM-FM's shape: one
          state per step, a key-lost edge back): the solving plan ends final, the wrong plan and
          the idle plan do not. It runs on the card's reset seed, and for a card with new maps
          also on the judge's 100 reset seeds (test-rl's default --seed-base 2000000); a plan
          that names colours runs only where they exist
  labels  a labeling hand-written from the env's ``environment-code.md`` truth conditions equals
          the reference labeler on every step of the plan traces and of 100 random walks
          (``Walks``: 50 fresh layouts, a uniform and a task walk each)
  bundles each generated bundle the card trains on (run-suite's ``bundle_path``, ``bundle_of``
          included) passes train-rl's pay check and the same plan and label checks; a bundle
          not generated yet is listed

Exits 1 when a check fails. Nothing trains and no model is called.

usage (repository root):
  PYTHONPATH=app python experiments/benchmark/armfm-paper/check/paper_cards_check.py
"""

import dataclasses
import json
import sys
from pathlib import Path

import yaml

from scripts.run_suite import bundle_path
from src.arm_fm.artifacts import ArtifactBundle, BundleManifest
from src.arm_fm.environments import _check_pay_assumptions, level_step_limit, make_environment
from src.benchmark.cards import Card, load_cards
from src.benchmark.labeling_repair import OK, Traces, check_labeling
from src.benchmark.plan_check import check_card_plans
from src.benchmark.plans import PlanError, run_plan
from src.benchmark.traces import make_record, plans_of
from src.compiler.rm_format import parse_paper_reward_machine
from src.config import Configuration

SUITE = Path("experiments/benchmark/armfm-paper")
TASKS = SUITE / "tasks.json"
RUNS_FILES = (SUITE / "runs.yaml", SUITE / "runs-5m.yaml")
JUDGE_SEEDS = tuple(range(2_000_000, 2_000_100))
WALK_LAYOUTS = 50  # two walks each: 100 walks
ARMS = ("farm", "arm-fm")

DOORKEY_MACHINE = """REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
TRANSITION_FUNCTION:
(u0, has_key) -> u1
(u0, else) -> u0
(u1, door_open) -> u2
(u1, key_lost) -> u0
(u1, else) -> u1
(u2, at_goal) -> u3
(u2, else) -> u2
(u3, else) -> u3
REWARD_FUNCTION:
(u0, has_key, u1) -> 0.1
(u1, door_open, u2) -> 0.2
(u1, key_lost, u0) -> -0.1
(u2, at_goal, u3) -> 1
"""

# experiments/benchmark/envs/minigrid-doorkey/environment-code.md, "Truth conditions in code".
DOORKEY_LABELING = """
def has_key(env):
    return env.carrying is not None and env.carrying.type == "key" and env.carrying.color == "yellow"


def door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])


def at_goal(env):
    return any(c is not None and c.type == "goal" for c in [env.grid.get(*env.agent_pos)])


def key_lost(env):
    prev = env.episode_memory["previous_valuation"]
    return prev["has_key"] and not has_key(env) and not door_open(env)
"""

UNLOCK_TO_UNLOCK_MACHINE = """REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4, u5
INITIAL_STATE: u0
FINAL_STATES: u5
TRANSITION_FUNCTION:
(u0, has_prerequisite_key) -> u1
(u0, else) -> u0
(u1, prerequisite_door_open) -> u2
(u1, required_key_lost) -> u0
(u1, else) -> u1
(u2, has_target_door_key) -> u3
(u2, else) -> u2
(u3, target_door_open) -> u4
(u3, required_key_lost) -> u2
(u3, else) -> u3
(u4, target_ball_picked_up) -> u5
(u4, else) -> u4
(u5, else) -> u5
REWARD_FUNCTION:
(u0, has_prerequisite_key, u1) -> 0.1
(u1, prerequisite_door_open, u2) -> 0.2
(u1, required_key_lost, u0) -> -0.1
(u2, has_target_door_key, u3) -> 0.1
(u3, target_door_open, u4) -> 0.2
(u3, required_key_lost, u2) -> -0.1
(u4, target_ball_picked_up, u5) -> 1
"""

# experiments/benchmark/envs/babyai-unlock-to-unlock/environment-code.md, "Truth conditions in code".
UNLOCK_TO_UNLOCK_LABELING = """
def has_prerequisite_key(env):
    return any(d is not None and d.type == "door" and env.carrying is not None and env.carrying.type == "key" and env.carrying.color == d.color for y in range(env.height) for d in [env.grid.get(10, y)])


def prerequisite_door_open(env):
    return any(d is not None and d.type == "door" and d.is_open for y in range(env.height) for d in [env.grid.get(10, y)])


def has_target_door_key(env):
    return any(d is not None and d.type == "door" and env.carrying is not None and env.carrying.type == "key" and env.carrying.color == d.color for y in range(env.height) for d in [env.grid.get(5, y)])


def target_door_open(env):
    return any(d is not None and d.type == "door" and d.is_open for y in range(env.height) for d in [env.grid.get(5, y)])


def target_ball_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball"


def required_key_lost(env):
    prev = env.episode_memory["previous_valuation"]
    return env.carrying is None and ((prev["has_prerequisite_key"] and not prerequisite_door_open(env)) or (prev["has_target_door_key"] and not target_door_open(env)))
"""

REFERENCES = {  # gym id prefix -> (machine, labeling)
    "MiniGrid-DoorKey-": (DOORKEY_MACHINE, DOORKEY_LABELING),
    "BabyAI-UnlockToUnlock-": (UNLOCK_TO_UNLOCK_MACHINE, UNLOCK_TO_UNLOCK_LABELING),
}


def reference_bundle(card: Card) -> ArtifactBundle:
    """The hand-written machine and labeling of ``card``'s env, as an in-memory bundle."""
    machine, labeling = next(
        pair for prefix, pair in REFERENCES.items() if card.env["gym_id"].startswith(prefix)
    )
    manifest = BundleManifest(task=card.task, environment=card.env["description"])
    return ArtifactBundle(manifest, parse_paper_reward_machine(machine), labeling)


def plan_traces(card: Card) -> list:
    """The plan records of ``card`` on its reset seeds (plans that cannot run are left out)."""
    records = []
    for seed in card.reset_seeds(1):
        for name, steps, _ in plans_of(card):
            try:
                records.append(make_record("", card, name, "plan", run_plan(card.env, steps, seed)))
            except PlanError as error:
                print(f"   plan {name}-s{seed} cannot run: {error}")
    return records


def check_plans(bundle: ArtifactBundle, card: Card) -> bool:
    """Print the plan checker's verdict on the card's seeds, and on the judge's for new maps."""
    cards = [card]
    if card.env["layout"] == "procedural":
        cards.append(dataclasses.replace(card, event_seeds=JUDGE_SEEDS))
    ok = True
    for checked in cards:
        record = check_card_plans(bundle, checked, 1)
        runs = [run for run in record["runs"] if "error" not in run]
        ends = {}
        for run in runs:
            ends.setdefault(run["plan"], set()).add(run["end"])
        seeds = "card seed" if checked is card else f"{len(JUDGE_SEEDS)} judge seeds"
        print(
            f"   plans, {seeds}: passed {record['passed']}, {len(runs)}/{len(record['runs'])} "
            f"runs played, ends {ends}, problems {record['problems'][:2]}"
        )
        ok &= record["passed"] is True
    return ok


def check_labels(bundle: ArtifactBundle, traces: Traces) -> bool:
    result = check_labeling(bundle, traces.block(0))
    fired = result.coverage.get("reference_true", {})
    print(f"   labels: {result.kind} over {len(traces.block(0))} traces; true steps {fired}")
    if result.kind != OK:
        print(f"   first differences: {result.evidence[:3]}")
    return result.kind == OK and all(fired.values())


def check_generated(card: Card, raw: dict, spec: dict, traces: Traces) -> bool:
    """The gates of each generated bundle the card trains on; True when every present one passes."""
    ok = True
    for arm in ARMS:
        folder = bundle_path(spec, raw, arm, None)
        if not (folder / "manifest.json").is_file():
            print(f"   {arm} bundle {folder}: not generated yet")
            continue
        bundle = ArtifactBundle.load(folder)
        env = make_environment(card.env["gym_id"], **card.env["env_kwargs"])
        _check_pay_assumptions(bundle, env, Configuration(bundle=folder))  # raises when refused
        env.close()
        print(f"   {arm} bundle {folder}: pay check accepted")
        ok &= check_plans(bundle, card)
        ok &= check_labels(bundle, traces)
    return ok


def main() -> int:
    card_file = load_cards(TASKS)
    # Card keeps no `bundle_of`; read it from the file.
    raw = {card["id"]: card for card in json.loads(TASKS.read_text(encoding="utf-8"))["cards"]}
    specs = {}
    for path in RUNS_FILES:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        specs |= dict.fromkeys(spec["only"], spec)
    failed = []
    for card in card_file.cards:
        env = make_environment(card.env["gym_id"], **card.env["env_kwargs"])
        print(
            f"== {card.id}: {card.env['gym_id']}, {card.env['layout']}, limit {level_step_limit(env)}"
        )
        env.close()
        problems = card_file.problems.get(card.id, [])
        print(
            f"   card problems: {problems or 'none'}; runs file budget {specs[card.id]['total_timesteps']}"
        )
        traces = Traces.of(plan_traces(card), WALK_LAYOUTS)
        bundle = reference_bundle(card)
        ok = not problems
        ok &= check_plans(bundle, card)
        ok &= check_labels(bundle, traces)
        ok &= check_generated(card, raw[card.id], specs[card.id], traces)
        if not ok:
            failed.append(card.id)
    print(f"\nfailed: {failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
