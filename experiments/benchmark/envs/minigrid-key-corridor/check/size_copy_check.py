"""Check KeyCorridor world-size cards on the FARM machine they borrow (`bundle_of`).

Per card of experiments/benchmark/base/tasks.json, on the judge's 100 reset seeds (test-rl's
default --seed-base 2000000):
  limit   train-rl's pay check accepts the bundle at the card's step limit
  card    the card contract (load_cards) finds no problem
  plans   the plan checker passes on those seeds: the solving plan ends final, the wrong plan and an
          idle plan (waits to the step limit, so it breaks every Existence clause) do not; the
          solving plan's steps to the final are printed against the limit. Where the planner finds
          no safe drop cell (S3R3's rooms are one cell wide), the solving plan runs again with any
          empty front cell as the drop cell and must still end final in the machine
  labels  the bundle's labeling equals the reference labeler on every step of the plan traces and
          of one seeded random walk per seed (forward-biased, run to the step limit)

usage (repository root):
  PYTHONPATH=app python experiments/benchmark/envs/minigrid-key-corridor/check/size_copy_check.py \
      base-key-corridor base-key-corridor-s3r3 ...
"""

import argparse
import dataclasses
import json
import random
import statistics
from collections import Counter
from pathlib import Path

from src.arm_fm.artifacts import ArtifactBundle
from src.arm_fm.environments import _check_pay_assumptions, level_step_limit, make_environment
from src.arm_fm.runtime import RewardMachineRuntime, load_labeling_functions
from src.benchmark.cards import Card, load_cards
from src.benchmark.plan_check import check_card_plans
from src.benchmark.plans import PlanError, PlanPlayer, run_plan
from src.benchmark.reference_labels import labeler_for
from src.benchmark.traces import make_record, plans_of, replay_in_bundle
from src.config import Configuration

TASKS = Path("experiments/benchmark/base/tasks.json")
BUNDLES = Path("experiments/benchmark/base/bundles/farm")
JUDGE_SEEDS = tuple(range(2_000_000, 2_000_100))
ACTIONS = [0, 1, 2, 2, 2, 2, 3, 4, 5]  # left, right, forward x4, pickup, drop, toggle


def with_idle(card: Card) -> Card:
    """The card on the judge's seeds, with an idle plan added as a wrong plan."""
    existence = [index for index, clause in enumerate(card.expect) if clause[0] == "Existence"]
    idle = {"breaks": existence, "steps": [{"do": "wait", "n": 10**6}]}
    return dataclasses.replace(card, event_seeds=JUDGE_SEEDS, wrong=(*card.wrong, idle))


def label_differences(env_spec: dict, seed: int, actions: list[int], labeling: tuple) -> Counter:
    """Replay ``actions``; count the steps where each labeled proposition differs from the reference.

    ``steps`` counts the steps compared, ``crashed`` a labeling that raised, and ``fires <p>``
    the episode once when the reference turns ``p`` true (so a zero difference means something).
    """
    machine, functions = labeling
    env = make_environment(env_spec["gym_id"], **env_spec["env_kwargs"])
    env.reset(seed=seed)
    reference = labeler_for(env_spec["gym_id"], env)
    runtime = RewardMachineRuntime(machine)
    differ, fired = Counter(), set()
    for action in actions:
        _, _, terminated, truncated, _ = env.step(action)
        expected = reference.labels(env.unwrapped)
        try:
            actual = runtime.evaluate_labeling(env, functions)
        except Exception:  # a labeling that crashes is a result
            differ["crashed"] += 1
            break
        differ["steps"] += 1
        differ.update(prop for prop, value in actual.items() if value != expected[prop])
        fired |= {f"fires {prop}" for prop in actual if expected[prop]}
        if terminated or truncated:
            break
    env.close()
    differ.update(fired)
    return differ


def random_walk(seed: int, limit: int) -> list[int]:
    rng = random.Random(seed)
    return [rng.choice(ACTIONS) for _ in range(limit)]


class FreeDropPlayer(PlanPlayer):
    """The plan player with any empty front cell as a drop cell, even one that blocks a path."""

    def is_safe_drop(self, cell: tuple[int, int], _doors: object) -> bool:
        return self.cell(*cell) is None


def free_drop_solves(card: Card, bundle: ArtifactBundle, seeds: list[int], labeling: tuple) -> None:
    """Run the solving plan with a free drop on ``seeds``; print where the machine stops."""
    machine = bundle.reward_machine
    stops = set(machine.final_states) | set(machine.rejecting_states)
    ends, steps, labels = Counter(), [], Counter()
    for seed in seeds:
        env = make_environment(card.env["gym_id"], **card.env["env_kwargs"])
        env.reset(seed=seed)
        try:
            player = FreeDropPlayer(
                env, labeler_for(card.env["gym_id"], env), card.env["gym_id"], seed
            )
            rollout = player.run(card.solve)
        except PlanError as error:
            ends[f"cannot run: {error}"] += 1
            continue
        finally:
            env.close()
        states = replay_in_bundle(bundle, make_record("", card, "solve", "plan", rollout)).rm_states
        stop = next((i for i, state in enumerate(states) if state in stops), len(states) - 1)
        ends["final" if states[stop] in machine.final_states else states[stop]] += 1
        steps.append(stop)
        labels += label_differences(card.env, seed, rollout.actions, labeling)
    print(
        f"   solve, free drop, on the {len(seeds)} seeds above: ends {dict(ends)}; steps median "
        f"{statistics.median(steps) if steps else None}, max {max(steps, default=None)}"
    )
    print(f"   labels, free-drop solve traces: {dict(labels)}")


def check_plans(card: Card, bundle: ArtifactBundle, labeling: tuple) -> None:
    record = check_card_plans(bundle, with_idle(card), JUDGE_SEEDS[0])
    errors = [run for run in record["runs"] if "error" in run]
    print(f"   plan checker: passed {record['passed']}, problems {record['problems'][:3]}")
    print(f"   plans that could not run: {len(errors)} {[run['error'] for run in errors[:2]]}")
    if errors:
        free_drop_solves(
            card, bundle, [run["seed"] for run in errors if run["plan"] == "solve"], labeling
        )
    idle = f"wrong-{len(card.wrong)}"  # with_idle appends it
    for name in sorted({run["plan"] for run in record["runs"]}):
        runs = [run for run in record["runs"] if run["plan"] == name and "error" not in run]
        ends = Counter(run["end"] for run in runs)
        steps = [run["steps"] for run in runs]
        print(
            f"   {'idle' if name == idle else name}: ends {dict(ends)} over {len(runs)} seeds; steps median "
            f"{statistics.median(steps)}, max {max(steps)}"
        )


def check_labels(card: Card, labeling: tuple, limit: int) -> None:
    plan_diff, walk_diff = Counter(), Counter()
    for seed in JUDGE_SEEDS:
        for _, steps, _ in plans_of(with_idle(card)):
            try:
                actions = run_plan(card.env, steps, seed).actions
            except PlanError:
                continue  # check_plans reports it
            plan_diff += label_differences(card.env, seed, actions, labeling)
        walk_diff += label_differences(card.env, seed, random_walk(seed, limit), labeling)
    print(f"   labels, plan traces: {dict(plan_diff)}")
    print(f"   labels, random walks: {dict(walk_diff)}")


def check(card: Card, folder: Path, problems: list[str]) -> None:
    bundle = ArtifactBundle.load(folder)
    env = make_environment(card.env["gym_id"], **card.env["env_kwargs"])
    u = env.unwrapped
    limit = level_step_limit(env)
    print(f"== {card.id}: room_size {u.room_size}, {u.width}x{u.height} grid, step limit {limit}")
    print(
        f"   bundle {folder}, priced for step limit {bundle.manifest.effective_settings['step_limit']}"
    )
    _check_pay_assumptions(bundle, env, Configuration(bundle=folder))  # raises when refused
    env.close()
    print(f"   pay check: accepted; card problems: {problems or 'none'}")
    labeling = (
        bundle.reward_machine,
        load_labeling_functions(bundle.labeling_source, bundle.labeling_propositions),
    )
    check_plans(card, bundle, labeling)
    check_labels(card, labeling, limit)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="+")
    args = parser.parse_args()
    card_file = load_cards(TASKS)
    cards = {card.id: card for card in card_file.cards}
    # Card keeps no `bundle_of`; read it from the file.
    raw = {card["id"]: card for card in json.loads(TASKS.read_text(encoding="utf-8"))["cards"]}
    for card_id in args.ids:
        folder = BUNDLES / (raw[card_id].get("bundle_of") or card_id)
        check(cards[card_id], folder, card_file.problems.get(card_id, []))


if __name__ == "__main__":
    main()
