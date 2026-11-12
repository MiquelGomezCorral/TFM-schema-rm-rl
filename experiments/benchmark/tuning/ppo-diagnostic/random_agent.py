"""How often a uniform random agent does each step of a procedural benchmark card by chance.

Plays ``--episodes`` episodes per card on the plain MiniGrid env (no Reward Machine, so nothing
ends an episode early), every action drawn uniformly from the action space, each episode on a
new layout seed. Counts the episodes where the agent ever carries the key, ever has a door open,
and succeeds (the env terminates with a positive reward: the box picked up in UnlockPickup, the
goal reached in DoorKey).

Usage (from the repo root):
    PYTHONPATH=app python experiments/benchmark/tuning/ppo-diagnostic/random_agent.py \
        [--episodes 2000] [--out outputs/ppo-diagnostic/random-agent]

Writes ``random_agent.csv`` (one row per card and step) and ``random_agent_lengths.csv`` (episode
lengths) to ``--out`` and prints the same tables.
"""

import argparse
import csv
import math
from pathlib import Path

import numpy as np

from src.arm_fm.environments import make_environment

CARDS = {
    "base-unlock-pickup": ("MiniGrid-UnlockPickup-v0", "box picked up"),
    "base-doorkey": ("MiniGrid-DoorKey-8x8-v0", "goal reached"),
}
STEPS = ("key", "door", "success")
LAYOUT_SEED_BASE = 2_000_000  # away from the training seeds (< 1M) and the eval seeds (1M + i)
COLUMNS = ("card", "step", "episodes", "count", "rate", "ci95_low", "ci95_high", "mean_first_step")
LENGTH_COLUMNS = ("card", "episodes", "mean_length", "median_length", "truncated_rate")


def wilson_interval(count: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """The 95% Wilson score interval of ``count`` events in ``total`` trials."""
    rate = count / total
    scale = 1 + z * z / total
    centre = (rate + z * z / (2 * total)) / scale
    half = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / scale
    return centre - half, centre + half


def play_episode(env, seed: int, rng: np.random.Generator) -> dict[str, int | bool | None]:
    """One random episode: the step each event first happened at (None if never), and its length.

    ``truncated`` says the time limit cut the episode.
    """
    base = env.unwrapped
    env.reset(seed=seed)
    play: dict[str, int | bool | None] = dict.fromkeys(STEPS)
    done = False
    while not done:
        _, reward, terminated, truncated, _ = env.step(int(rng.integers(env.action_space.n)))
        done = terminated or truncated
        events = {
            "key": base.carrying is not None and base.carrying.type == "key",
            "door": any(cell.type == "door" and cell.is_open for cell in base.grid.grid if cell),
            "success": terminated and reward > 0,
        }
        for name, happened in events.items():
            if happened and play[name] is None:
                play[name] = base.step_count
    return {**play, "length": base.step_count, "truncated": truncated}


def card_rows(card: str, episodes: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    """The table rows (one per step) and the episode-length row of ``episodes`` random episodes."""
    env = make_environment(CARDS[card][0])
    rng = np.random.default_rng(0)
    plays = [play_episode(env, LAYOUT_SEED_BASE + index, rng) for index in range(episodes)]
    env.close()
    lengths = [play["length"] for play in plays]
    length_row = {
        "card": card,
        "episodes": episodes,
        "mean_length": float(np.mean(lengths)),
        "median_length": float(np.median(lengths)),
        "truncated_rate": float(np.mean([play["truncated"] for play in plays])),
    }
    rows = []
    for name in STEPS:
        steps = [play[name] for play in plays if play[name] is not None]
        low, high = wilson_interval(len(steps), episodes)
        rows.append(
            {
                "card": card,
                "step": name,
                "episodes": episodes,
                "count": len(steps),
                "rate": len(steps) / episodes,
                "ci95_low": low,
                "ci95_high": high,
                "mean_first_step": float(np.mean(steps)) if steps else None,
            }
        )
    return rows, length_row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Uniform random agent rates per benchmark card.")
    parser.add_argument("--episodes", type=int, default=2000)
    parser.add_argument("--out", type=Path, default=Path("outputs/ppo-diagnostic/random-agent"))
    arguments = parser.parse_args()
    results = [card_rows(card, arguments.episodes) for card in CARDS]
    table = [row for rows, _ in results for row in rows]
    lengths = [length_row for _, length_row in results]

    arguments.out.mkdir(parents=True, exist_ok=True)
    for name, columns, rows in (
        ("random_agent.csv", COLUMNS, table),
        ("random_agent_lengths.csv", LENGTH_COLUMNS, lengths),
    ):
        with (arguments.out / name).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, columns)
            writer.writeheader()
            writer.writerows(rows)
    for row in lengths:
        print(
            f"{row['card']} episode length: mean {row['mean_length']:.1f}, median "
            f"{row['median_length']:.0f}, cut by the time limit {row['truncated_rate']:.3f}"
        )
    for row in table:
        first = row["mean_first_step"]
        print(
            f"{row['card']} {row['step']}: {row['count']}/{row['episodes']} episodes "
            f"({row['rate']:.4f}, 95% CI {row['ci95_low']:.4f} to {row['ci95_high']:.4f}), "
            f"first at step {'-' if first is None else f'{first:.0f}'} on average"
        )
