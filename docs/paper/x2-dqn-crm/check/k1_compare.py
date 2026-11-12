"""K1: a default-settings run on the X2 branch equals the same run on 7ae1157, byte for byte.

Usage: python k1_compare.py <baseline run folder> <branch run folder>
Wall-clock columns (sps, wall_seconds) are dropped; every other CSV cell must match, and so must
the learning-relevant summary entries.
"""

import json
import sys
from pathlib import Path

import pandas as pd

TIMING = {"train.csv": ["sps"], "episodes.csv": ["wall_seconds"], "eval.csv": []}
SUMMARY_KEYS = (
    "total_env_steps",
    "total_training_episodes",
    "gradient_updates",
    "target_syncs",
    "parameter_change_norm",
    "steps_to_success",
    "final_eval",
)


def main(base: str, branch: str) -> None:
    base, branch = Path(base), Path(branch)
    ok = True
    for name, drop in TIMING.items():
        left = pd.read_csv(base / name).drop(columns=drop)
        right = pd.read_csv(branch / name).drop(columns=drop)
        same = left.equals(right)
        ok &= same
        print(f"K1 {name}: {len(left)} rows vs {len(right)} rows, identical: {same}")
    left = json.loads((base / "summary.json").read_text())
    right = json.loads((branch / "summary.json").read_text())
    for key in SUMMARY_KEYS:
        same = left[key] == right[key]
        ok &= same
        print(f"K1 summary {key}: identical: {same}")
    weights = (base / "q_network.pt").read_bytes() == (branch / "q_network.pt").read_bytes()
    ok &= weights
    print(f"K1 q_network.pt bytes identical: {weights}")
    print("K1", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
