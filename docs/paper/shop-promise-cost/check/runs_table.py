"""Served per seed of every shop run the page cites, with its training settings. No training.

Usage, from the repository root inside RM_RL_env:
    python docs/paper/shop-promise-cost/check/runs_table.py

Reads `evidence/runs/<run>-s<seed>/seed*/{judge,test,summary}.json` and `config.yaml` (copied from
the runs' folders) and writes the table it prints to `evidence/runs.out`. Served is the judge's
`mean_served_count` over 100 test episodes (greedy policy, test reset seeds 2000000-2000099).
"""

import json
from pathlib import Path

import yaml

ENTRY = Path(__file__).resolve().parent.parent
RUNS = ENTRY / "evidence" / "runs"
# (run name without the seed, bundle copy in evidence/bundles, what it tests)
GROUPS = (
    ("r6-shop-A-base", "r6-both-off", "round 6, both off"),
    ("r6-shop-B-clip01", "r6-both-off", "round 6, both off, PPO clip 0.1"),
    ("r6-shop-C-novclip", "r6-both-off", "round 6, both off, no value clip"),
    ("r6-shop-D-promise", "r6-promise", "round 6, promise cost on"),
    ("r6-shop-E-end", "r6-end", "round 6, end judgment on"),
    ("r7-B4", "r7-b4-promise", "round 7 B4, promise cost on"),
    ("r7-B8b", "r7-b8b-promise", "round 7 B8b, promise cost on"),
    ("tp-shop-serve-pc-off", "shop-serve-both-off", "probe, today's shop-serve, both off"),
    ("rg-b8b", "r7-b8b-rebuilt", "after the fix: round 7 B8b again"),
    (
        "sw-shop-serve-pc-on",
        "shop-serve-promise-after",
        "after the fix: today's shop-serve, promise on",
    ),
)
KEYS = (
    "total_timesteps",
    "ppo_clip_coef",
    "ppo_clip_vloss",
    "gamma",
    "ppo_learning_rate",
    "time_limit_penalty",
)


def main() -> None:
    lines = []
    for run, bundle, role in GROUPS:
        served, rm_return, success, settings = [], [], [], None
        for seed in (1, 2, 3):
            (folder,) = (RUNS / f"{run}-s{seed}").glob("seed*")
            judge = json.loads((folder / "judge.json").read_text(encoding="utf-8"))
            config = yaml.safe_load((folder / "config.yaml").read_text(encoding="utf-8"))
            steps = json.loads((folder / "summary.json").read_text(encoding="utf-8"))[
                "total_env_steps"
            ]
            served.append(f"{judge['mean_served_count']:g}")
            rm_return.append(f"{judge['mean_rm_return']:g}")
            success.append(f"{judge['mean_judged_success']:g}")
            if seed == 1:
                settings = {key: config.get(key) for key in KEYS} | {"env steps": steps}
        lines += [
            f"== {run} ({role}); bundle evidence/bundles/{bundle}",
            f"   served {' / '.join(served)}; judged success {' / '.join(success)}; rm return {' / '.join(rm_return)}",
            f"   seed 1 settings: {settings}",
        ]
    text = "\n".join(lines) + "\n"
    (ENTRY / "evidence" / "runs.out").write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
