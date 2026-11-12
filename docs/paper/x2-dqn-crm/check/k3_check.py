"""K3: 8 environments give sensible rows and episode counts, and the same gradient steps per env step.

Run from the worktree root:  python <this file>
Reads the newest folder of x2-k3-envs1, x2-k3-envs8 and x2-k3-envs8-crm under outputs/runs/.
"""

import json
from pathlib import Path

import pandas as pd

RUNS = Path("outputs/runs")
NAMES = ("x2-k3-envs1", "x2-k3-envs8", "x2-k3-envs8-crm")
ENVS = {"x2-k3-envs1": 1, "x2-k3-envs8": 8, "x2-k3-envs8-crm": 8}


def newest(name: str) -> Path:
    return max((RUNS / name).iterdir(), key=lambda folder: folder.name)


def main() -> None:
    ok = True
    summaries = {}
    for name in NAMES:
        folder = newest(name)
        summary = json.loads((folder / "summary.json").read_text())
        episodes = pd.read_csv(folder / "episodes.csv")
        evals = pd.read_csv(folder / "eval.csv")
        train = pd.read_csv(folder / "train.csv")
        summaries[name] = summary
        envs = ENVS[name]
        aligned = bool((episodes.global_step % envs == 0).all())
        eval_steps = evals.global_step.tolist()
        print(
            f"{name}: envs {envs}, total_env_steps {summary['total_env_steps']}, "
            f"episodes {summary['total_training_episodes']} ({len(episodes)} rows, "
            f"lengths {sorted(set(episodes.length))}), gradient_updates {summary['gradient_updates']}, "
            f"target_syncs {summary['target_syncs']}, eval steps {eval_steps}, "
            f"train rows {len(train)}, last sps {int(train.sps.iloc[-1])}, "
            f"wall {summary['wall_seconds']:.1f} s"
        )
        ok &= aligned and eval_steps == [2000, 4000, 6000] and summary["total_env_steps"] == 6000
        ok &= len(episodes) == summary["total_training_episodes"]
    updates = {summaries[name]["gradient_updates"] for name in NAMES}
    syncs = {summaries[name]["target_syncs"] for name in NAMES}
    print(
        f"gradient updates per run {sorted(updates)}; same count for any env number: {len(updates) == 1}"
    )
    print(f"target syncs per run {sorted(syncs)}; same count: {len(syncs) == 1}")
    ok &= len(updates) == 1 and len(syncs) == 1
    print("K3", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
