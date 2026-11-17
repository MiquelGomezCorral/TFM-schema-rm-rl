"""Judge finished shop-ground-up runs on their own card, then print a summary table.

Usage (through judge.sh, which sets the worktree, PYTHONPATH and the conda python):
    judge.sh <r1|r2|r3|dry|all|run name> [...] [--episodes N] [--no-sampled] [--force]

Per finished run, on its card (``cards/``, the shop card of its step), ``N`` test episodes (default 100) from
test seed 2000000, as ``test-rl --run <folder> --judge <card>`` does:
  greedy   ``test_rl`` -> ``<run>/judge.json`` and ``agent-traces/``, copied to ``judge-<card>.json``
  sampled  the same judge with ``eval_greedy = False`` -> ``<run>/sampled/<card>/``, copied to ``judge-sampled-<card>.json``
Writes only into the run folder. A run that already has the verdict file is skipped unless ``--force``.
The table gives served_count (clients served per 600-step episode), served_success and judged_success; a run
counts as learned (plan R11) when its greedy mean served_count is at least ``LEARNED_SERVED``.
"""

import argparse
import json
import shutil
from pathlib import Path

import yaml
from sgu import CARDS, fmt, is_finished, run_folder, select

from scripts.test_rl import JudgeRecorder, load_policy, run_config, test_rl
from src.arm_fm import make_run_environment
from src.config import Configuration

EVAL_SEED_BASE = 2_000_000  # the default of ``test-rl --seed-base``
LEARNED_SERVED = 7.5  # greedy served/ep; plan R11, lowered from 10 on 2026-11-17 (user)
SKIPPED = (OSError, ValueError, RuntimeError, SystemExit)  # one failed run must not stop the others


def verdict_name(card: str, label: str) -> str:
    """The verdict file of a judge (``greedy`` or ``sampled``) on a card, inside the run folder."""
    return f"judge-{card}.json" if label == "greedy" else f"judge-{label}-{card}.json"


def judge_greedy(folder: Path, card: Path, episodes: int) -> None:
    CONFIG = Configuration(
        exp_name=str(folder), final_eval_episodes=episodes, eval_seed_base=EVAL_SEED_BASE
    )
    test_rl(CONFIG, 0, card)
    shutil.copy(folder / "judge.json", folder / verdict_name(card.stem, "greedy"))


def judge_sampled(folder: Path, card: Path, episodes: int) -> None:
    saved = yaml.safe_load((folder / "config.yaml").read_text(encoding="utf-8"))
    config = run_config(saved, EVAL_SEED_BASE)
    config.eval_greedy = False
    run = make_run_environment(config)
    out = folder / "sampled" / card.stem
    try:
        policy = load_policy(config, run, folder, "final")
        out.mkdir(parents=True, exist_ok=True)
        JudgeRecorder(config, run, policy, card).write(out, episodes)
    finally:
        run.env.close()
    shutil.copy(out / "judge.json", folder / verdict_name(card.stem, "sampled"))


def judge_run(run: dict, args: argparse.Namespace) -> None:
    folder = run_folder(run["name"])
    if not is_finished(folder):
        print(f"not finished: {run['name']}", flush=True)
        return
    card = CARDS / f"{run['card']}.json"
    steps = [("greedy", judge_greedy)]
    if not args.no_sampled:
        steps.append(("sampled", judge_sampled))
    for label, judge in steps:
        if (folder / verdict_name(card.stem, label)).is_file() and not args.force:
            continue
        try:
            judge(folder, card, args.episodes)
            print(f"judged {run['name']} {label}", flush=True)
        except SKIPPED as error:
            print(f"FAILED {run['name']} {label}: {error!r}"[:300], flush=True)


# ======================================================================================
#                                         TABLE
# ======================================================================================


def read_verdict(folder: Path, name: str) -> dict:
    path = folder / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def cells(verdict: dict) -> list[str]:
    return [
        fmt(verdict.get("mean_served_count")),
        fmt(verdict.get("mean_served_success")),
        fmt(verdict.get("mean_judged_success")),
    ]


def table(runs: list[dict]) -> str:
    head = (
        "| run | machine | PPO set | encoding | steps | episodes "
        "| greedy served/ep | greedy served_success | greedy judged_success "
        f"| sampled served/ep | sampled served_success | sampled judged_success | learned (greedy served >= {LEARNED_SERVED}) |"
    )
    lines = [head, "|" + "---|" * 13]
    for run in runs:
        folder = run_folder(run["name"])
        if not is_finished(folder):
            lines.append(f"| `{run['name']}` | {run['machine']} | not finished |" + " |" * 10)
            continue
        card = run["card"]
        greedy = read_verdict(folder, verdict_name(card, "greedy"))
        sampled = read_verdict(folder, verdict_name(card, "sampled"))
        served = greedy.get("mean_served_count")
        learned = "-" if served is None else ("YES" if served >= LEARNED_SERVED else "no")
        episodes = len(greedy.get("per_episode", [])) or "-"
        lines.append(
            f"| `{run['name']}` | {run['machine']} | {run['pset']} | {run['encoding']} | {run['steps']:,} "
            f"| {episodes} | {' | '.join(cells(greedy))} | {' | '.join(cells(sampled))} | {learned} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="+", help="r1, r2, r3, dry, all or run names")
    parser.add_argument("--episodes", type=int, default=100, help="test episodes per judge")
    parser.add_argument("--no-sampled", action="store_true", help="skip the sampled judge")
    parser.add_argument("--force", action="store_true", help="judge again, replacing the verdicts")
    args = parser.parse_args()

    runs = select(args.names)
    for run in runs:
        judge_run(run, args)
    print("\n" + table(runs))


if __name__ == "__main__":
    main()
