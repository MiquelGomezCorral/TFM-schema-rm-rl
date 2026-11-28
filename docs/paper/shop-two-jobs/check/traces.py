"""Count rings, switch presses, fines and pay in the judged episodes of the no-RM siren runs.

Run from the repository root with any Python 3 (reads outputs/runs, writes docs/paper/shop-two-jobs/data/rings.csv):
    python -I docs/paper/shop-two-jobs/check/traces.py
For each no-RM run of the two siren tasks (T2 serve + siren, T4 full serve + siren) it reads the 100
`agent-traces/ep*.json` files the judge wrote and takes, per judged episode:
  rings      times `siren_ringing` rises (a ring still on at step 0 counts)
  answered   rings during which `switch_toggled` is true at least once
  presses    steps with `switch_toggled` true
  served     steps with `order_served` true
  unanswered 1 when the last ring is later than the last press (or there is no press): the `Response(siren_ringing,
             switch_toggled)` clause, which has no deadline, fails only then
  fine, pay  sum of the negative, and of the positive, `env_rewards` (the environment's own reward)
and writes the mean per episode of each. No model call.
"""

import csv
import json
from collections import Counter
from pathlib import Path

RUNS = Path("outputs/runs")
OUT = Path("docs/paper/shop-two-jobs/data/rings.csv")
CARDS = ("shop-two-serve-siren", "shop-two-full-siren")
SHOPS = ("3x3", "5x5", "7x7", "grow")
RUN_NUMBERS = (1, 2, 3)
EPISODES = 100
COLUMNS = ("rings", "answered", "presses", "served", "unanswered", "fine", "pay")


def episode_stats(trace: dict) -> dict[str, float]:
    """The columns of one judged episode."""
    labels = trace["labels"]
    rings = answered = 0
    open_ring = previous = False
    last_ring = last_press = -1
    for step, label in enumerate(labels):
        ringing, pressed = label["siren_ringing"], label["switch_toggled"]
        if ringing and not previous:
            rings += 1
            open_ring = True
        if pressed and open_ring:
            answered += 1
            open_ring = False
        elif not ringing:
            open_ring = False
        previous = ringing
        last_ring = step if ringing else last_ring
        last_press = step if pressed else last_press
    rewards = trace["env_rewards"]
    return {
        "rings": rings,
        "answered": answered,
        "presses": sum(label["switch_toggled"] for label in labels),
        "served": sum(label["order_served"] for label in labels),
        "unanswered": int(last_ring > last_press),
        "fine": sum(reward for reward in rewards if reward < 0),
        "pay": sum(reward for reward in rewards if reward > 0),
    }


def run_row(card: str, run: int) -> list[str]:
    """CSV row of one run: the mean per judged episode of each column."""
    experiment = RUNS / f"bench__shop-two-reward__{card}__no-rm__ppo"
    folders = sorted(experiment.glob(f"seed{run}-*/agent-traces"))
    assert len(folders) == 1, f"{card} run {run}: {len(folders)} trace folders"
    files = list(folders[0].glob("ep*.json"))
    assert len(files) == EPISODES, f"{card} run {run}: {len(files)} traces"
    totals: Counter[str] = Counter()
    for file in files:
        totals.update(episode_stats(json.loads(file.read_text(encoding="utf-8"))))
    return [f"{totals[column] / EPISODES:.3f}" for column in COLUMNS]


def main() -> None:
    with OUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["method", "card", "run", *(f"{column}_per_episode" for column in COLUMNS)])
        for task in CARDS:
            for shop in SHOPS:
                card = f"{task}-{shop}"
                for run in RUN_NUMBERS:
                    writer.writerow(["no-rm", card, run, *run_row(card, run)])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
