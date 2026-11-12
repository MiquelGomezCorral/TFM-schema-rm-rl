"""Episode facts of the procedural benchmark cards: time limit and solve length per layout.

For each card, builds the env the learner trains on (``make_environment``, the symbolic MiniGrid
env), reports its ``max_steps``, then runs the card's own ``solve`` plan (the benchmark's plan
runner: breadth-first navigation between the plan's steps, every move through ``env.step``) on
``--layouts`` procedural layouts. The solve length is therefore the length of that plan, an upper
bound of the true shortest solve that is tight to a few steps. The Reward Machine items are the
reference labels of the env: key carried, door open, then the last step (box picked up or goal
reached). Their step counts come from the first step each label holds.

Usage (from the repo root):
    PYTHONPATH=app python experiments/benchmark/tuning/ppo-diagnostic/episode_facts.py \
        [--layouts 200] [--out outputs/ppo-diagnostic/episode-facts]

Writes ``episode_facts.csv`` (the statistics) and ``episode_facts_layouts.csv`` (one row per
layout) to ``--out`` and prints the statistics.
"""

import argparse
import csv
from pathlib import Path

import numpy as np

from src.arm_fm.environments import make_environment
from src.benchmark.plans import PlanError, run_plan

LAYOUT_SEED_BASE = 2_000_000  # the same layouts as random_agent.py
# gym id, the solve plan of the card, and the labels of the three Reward Machine items.
CARDS = {
    "base-unlock-pickup": (
        "MiniGrid-UnlockPickup-v0",
        [
            {"do": "pickup", "obj": "key"},
            {"do": "toggle", "obj": "door"},
            {"do": "drop"},
            {"do": "pickup", "obj": "box"},
        ],
        ("has_door_key", "door_open", "target_picked_up"),
    ),
    "base-doorkey": (
        "MiniGrid-DoorKey-8x8-v0",
        [
            {"do": "pickup", "obj": "key"},
            {"do": "toggle", "obj": "door"},
            {"do": "goto", "obj": "goal"},
        ],
        ("has_key", "door_open", "at_goal"),
    ),
}
QUANTITIES = ("start_to_key", "key_to_door", "door_to_last", "solve_length")
STATISTICS = ("median", "p90", "max", "mean")
LAYOUT_COLUMNS = ("card", "seed", "start_to_key", "key_to_door", "door_to_last", "solve_length")
STATISTIC_COLUMNS = ("card", "quantity", *STATISTICS)


def solve_layout(gym_id: str, plan: list[dict], labels: tuple[str, ...], seed: int) -> list[int]:
    """Steps start to key, key to door, door to last item, and the whole solve of one layout."""
    rollout = run_plan({"gym_id": gym_id}, plan, seed)
    if not (rollout.terminated and rollout.env_rewards[-1] > 0):
        raise PlanError(f"the solve plan did not solve seed {seed}")
    first = [
        next(step for step, held in enumerate(rollout.labels, 1) if held[label]) for label in labels
    ]
    return [first[0], first[1] - first[0], first[2] - first[1], len(rollout.actions)]


def statistics(values: list[int]) -> dict[str, float]:
    return {
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
        "max": float(max(values)),
        "mean": float(np.mean(values)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Time limit and solve length per benchmark card.")
    parser.add_argument("--layouts", type=int, default=200)
    parser.add_argument("--out", type=Path, default=Path("outputs/ppo-diagnostic/episode-facts"))
    arguments = parser.parse_args()
    arguments.out.mkdir(parents=True, exist_ok=True)

    layout_rows, statistic_rows = [], []
    for card, (gym_id, plan, labels) in CARDS.items():
        env = make_environment(gym_id)
        base = env.unwrapped
        print(
            f"{card}: {gym_id}, max_steps {base.max_steps}, spec.max_episode_steps "
            f"{env.spec.max_episode_steps}, grid {base.width}x{base.height}"
        )
        env.close()
        solved = [
            (seed, solve_layout(gym_id, plan, labels, seed))
            for seed in range(LAYOUT_SEED_BASE, LAYOUT_SEED_BASE + arguments.layouts)
        ]
        layout_rows += [
            dict(zip(LAYOUT_COLUMNS, [card, seed, *steps], strict=True)) for seed, steps in solved
        ]
        for column, quantity in enumerate(QUANTITIES):
            values = [steps[column] for _, steps in solved]
            statistic_rows.append({"card": card, "quantity": quantity, **statistics(values)})

    for name, columns, rows in (
        ("episode_facts.csv", STATISTIC_COLUMNS, statistic_rows),
        ("episode_facts_layouts.csv", LAYOUT_COLUMNS, layout_rows),
    ):
        with (arguments.out / name).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, columns)
            writer.writeheader()
            writer.writerows(rows)
    for row in statistic_rows:
        print(
            f"{row['card']} {row['quantity']}: median {row['median']:.0f}, p90 {row['p90']:.0f}, "
            f"max {row['max']:.0f}, mean {row['mean']:.1f}"
        )
