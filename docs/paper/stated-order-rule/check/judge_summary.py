"""Print one Markdown row per judged seed of each run name (judge.json written by `test-rl --judge`).

Learned = judged success >= 0.8, the line tp-kc-room/outputs/kc-room/probe_judge.py used for KeyCorridor.
Usage: python judge_summary.py <runs root> <exp_name>...
"""

import json
import sys
from pathlib import Path

LEARNED = 0.8

root, *names = sys.argv[1:]
print(
    "| run | seed | judged success | env success | hard breaks/ep | hard open at end | rm return | length | learned |"
)
print("|---|---|---|---|---|---|---|---|---|")
for name in names:
    for judge in sorted((Path(root) / name).glob("seed*-*/judge.json")):
        record = json.loads(judge.read_text(encoding="utf-8"))
        seed = judge.parent.name.split("-")[0].removeprefix("seed")
        success = record["mean_judged_success"]
        rm_return = record["mean_rm_return"]
        print(
            f"| {name} | {seed} | {success:.2f} | {record['mean_env_success']:.2f} | {record['mean_hard_breaks']:.2f} "
            f"| {record['mean_hard_open']:.2f} | {'-' if rm_return is None else f'{rm_return:.2f}'} "
            f"| {record['mean_length']:.0f} | {'yes' if success >= LEARNED else 'no'} |"
        )
