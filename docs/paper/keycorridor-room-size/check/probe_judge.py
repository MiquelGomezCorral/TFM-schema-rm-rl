"""Judge the probe runs of a queue: test-rl --judge on each finished run, then one table per machine.

Adapted from tp-chain-progress/outputs/chain-reg/chain_judge.py. Every run: 100 greedy test episodes on test seeds
from 2,000,000, judged on the card copy's `expect` (cards/<copy>.json: the card with the probe's level).
Measures, by kind:
- goal (KeyCorridor): judged success (every hard clause holds; the suite's result test), learned at >= 0.8; steps
  to learn = the first eval row with greedy exit_rate >= 0.8 (eval.csv, every 50k steps).
- shop: mean_served_count, learned at >= 7.5 clients per episode; steps to learn: the first eval row whose greedy
  shop return is >= 7.5 (the shop return is served minus late fines, so served >= return: an upper bound).
- rule (KeyGift): judged success (the hard Response holds at the cut: no key held with the door not opened since),
  learned at >= 0.8; no eval column measures it, so no steps to learn.
Scripted references on the same seeds (goal and rule cards): an idle agent and the card's solve plan.

Run from the worktree root (probe_run.py calls it when the queue ends):
    PYTHONPATH=app python outputs/probes/probe_judge.py queue-<round>.json [more queues] [--episodes 100]
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean

from src.arm_fm.environments import gym_step_limit
from src.benchmark import judge_trace, load_card
from src.benchmark.plans import run_plan

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
FIRST_TEST_SEED = 2_000_000
JUDGES_AT_ONCE = 4
LEARNED = {
    "goal": ("mean_judged_success", 0.8),
    "shop": ("mean_served_count", 7.5),
    "rule": ("mean_judged_success", 0.8),
}
EVAL_LEVEL = {"goal": ("exit_rate", 0.8), "shop": ("mean_env_return", 7.5)}
CURVE_STEPS = {
    "goal": (250_000, 500_000, 1_000_000, 1_500_000),
    "shop": (1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000),
}


def run_folder(name: str) -> Path | None:
    folders = sorted((WORKTREE / "outputs/runs" / name).glob("seed*-*/summary.json"))
    return folders[-1].parent if folders else None


def judge(run: dict, folder: Path, episodes: int) -> None:
    if (folder / "judge.json").is_file():
        return
    command = [sys.executable, "app/main.py", "test-rl", "--run", str(folder), "--model", "final"]
    command += ["--judge", str(HERE / "cards" / f"{run['card']}.json"), "--episodes", str(episodes)]
    command += ["--seed-base", str(FIRST_TEST_SEED)]
    env = {**os.environ, "OMP_NUM_THREADS": "2", "PYTHONPATH": "app"}
    result = subprocess.run(  # noqa: S603  fixed argv, no shell
        command, cwd=WORKTREE, env=env, capture_output=True, text=True, check=False
    )
    (folder / "judge.log").write_text(result.stdout + result.stderr, encoding="utf-8")


def eval_rows(folder: Path) -> dict[int, dict]:
    with (folder / "eval.csv").open(encoding="utf-8") as handle:
        return {int(row["global_step"]): row for row in csv.DictReader(handle)}


def first_step(rows: dict[int, dict], column: str, level: float) -> int | None:
    return next((step for step in sorted(rows) if float(rows[step][column]) >= level), None)


def curve(rows: dict[int, dict], column: str, steps: tuple[int, ...]) -> str:
    cells = []
    for step in steps:
        near = min(rows, key=lambda s: abs(s - step))
        cells.append(f"{float(rows[near][column]):.2f}" if abs(near - step) <= 50_000 else "-")
    return " ".join(cells)


def figures_of(run: dict, folder: Path) -> dict | None:
    if not (folder / "judge.json").is_file():
        return None
    judged = json.loads((folder / "judge.json").read_text(encoding="utf-8"))
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    kind = run["kind"]
    key, level = LEARNED[kind]
    figures = {
        "run": run["name"],
        "machine": run["machine"],
        "seed": run["seed"],
        "folder": str(folder),
        "score_name": key,
        "score": judged[key],
        "learned": judged[key] >= level,
        "judged_success": judged["mean_judged_success"],
        "env_success": judged["mean_env_success"],
        "hard_breaks": judged["mean_hard_breaks"],
        "hard_open": judged.get("mean_hard_open"),
        "rm_return": judged.get("mean_rm_return"),
        "length": judged["mean_length"],
        "wall_minutes": round(summary["wall_seconds"] / 60, 1),
        "steps": summary["total_env_steps"],
    }
    if kind in EVAL_LEVEL:
        rows = eval_rows(folder)
        column, eval_level = EVAL_LEVEL[kind]
        figures["steps_to_learn"] = first_step(rows, column, eval_level)
        figures["curve"] = (
            f"greedy {column} at {'/'.join(f'{s // 1000}k' for s in CURVE_STEPS[kind])}: "
            + curve(rows, column, CURVE_STEPS[kind])
        )
    else:
        figures["steps_to_learn"] = None
        figures["curve"] = ""
    if kind == "shop":
        figures["served_success"] = judged.get("mean_served_success")
    return figures


def run_line(run: dict, figures: dict | None) -> str:
    if figures is None:
        folder = run_folder(run["name"])
        return f"- {run['name']}: no result ({'not finished' if folder is None else 'judge failed, see judge.log'})"
    learned = "LEARNED" if figures["learned"] else "not learned"
    to_learn = figures["steps_to_learn"] if figures["steps_to_learn"] is not None else "never"
    return (
        f"- {run['name']}: {figures['score_name']} {figures['score']:.2f} {learned}; judged success "
        f"{figures['judged_success']:.2f}, env success {figures['env_success']:.2f}, hard breaks "
        f"{figures['hard_breaks']:.2f}/ep, hard open at the end {figures['hard_open']}, rm return "
        f"{figures['rm_return']}, length {figures['length']:.0f}; steps to learn {to_learn}; {figures['curve']}; "
        f"wall {figures['wall_minutes']:.0f} min"
    )


def scripted(card_name: str, episodes: int) -> list[str]:
    _, card = load_card(HERE / "cards" / f"{card_name}.json")
    limit = gym_step_limit(card.env["gym_id"], **(card.env.get("env_kwargs") or {}))
    lines = []
    for label, steps in (("idle", [{"do": "wait", "n": limit}]), ("solve-plan", list(card.solve))):
        rollouts = []
        for k in range(episodes):
            try:
                rollouts.append(run_plan(card.env, steps, FIRST_TEST_SEED + k))
            except Exception as error:
                lines.append(
                    f"- {label}: seed {FIRST_TEST_SEED + k} cannot run ({str(error)[:80]})"
                )
        if rollouts:
            judged = [judge_trace(card.expect, r.labels) for r in rollouts]
            lines.append(
                f"- {label}: judged success {mean(j.success for j in judged):.2f} over {len(rollouts)} episodes, "
                f"length {mean(len(r.labels) for r in rollouts):.0f}"
            )
    return lines


def report(queue: list[dict], episodes: int) -> tuple[str, list[dict]]:
    out = [
        f"Probe judge, {time.strftime('%Y-%m-%d %H:%M:%S')}: {episodes} greedy episodes per run, test seeds from "
        f"{FIRST_TEST_SEED}. Learned: KeyCorridor and KeyGift judged success >= 0.8; shop >= 7.5 served/episode.",
        "",
    ]
    for card_name in sorted({run["card"] for run in queue if run["kind"] != "shop"}):
        out += [
            f"Scripted agents on {card_name}, same seeds",
            "",
            *scripted(card_name, episodes),
            "",
        ]
    out += ["Per run", ""]
    per_machine, rows = defaultdict(list), []
    for run in queue:
        folder = run_folder(run["name"])
        figures = figures_of(run, folder) if folder else None
        out.append(run_line(run, figures))
        if figures:
            per_machine[run["machine"]].append(figures)
            rows.append(figures)
    out += ["", "Per machine", ""]
    for machine, items in per_machine.items():
        learned = sum(f["learned"] for f in items)
        reached = sorted(f["steps_to_learn"] for f in items if f["steps_to_learn"] is not None)
        out.append(
            f"- {machine} ({len(items)} seeds): {items[0]['score_name']} "
            f"{' / '.join(f'{f["score"]:.2f}' for f in items)} (mean {mean(f['score'] for f in items):.2f}); "
            f"learned {learned} of {len(items)}; steps to learn {reached}; "
            f"wall {' / '.join(f'{f["wall_minutes"]:.0f}' for f in items)} min"
        )
    return "\n".join(out) + "\n", rows


def judge_all(queue_path: Path, episodes: int, out_path: Path) -> None:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    jobs = [(run, folder) for run in queue if (folder := run_folder(run["name"])) is not None]
    with ThreadPoolExecutor(JUDGES_AT_ONCE) as pool:
        list(pool.map(lambda job: judge(*job, episodes), jobs))
    text, rows = report(queue, episodes)
    out_path.write_text(text, encoding="utf-8")
    out_path.with_suffix(".json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("queues", nargs="+")
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    for name in args.queues:
        path = HERE / name
        out = args.out or HERE / f"judge-{path.stem.removeprefix('queue-')}.out"
        judge_all(path, args.episodes, out)


if __name__ == "__main__":
    main()
