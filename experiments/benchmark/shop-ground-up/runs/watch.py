"""One table of the runs of a round, read from their training logs.

Usage:  [SGU_RUNS_ROOT=DIR] python watch.py <r1|r2|r3|dry|all|run name> [...] [--early] [--window N]

Columns (per run folder under the runs root):
  state    done (summary.json), running (live pid file), DEAD (folder, no summary, no live process), queued
  step     latest ``train.csv`` row / the run's total steps; ETA from the ``sps`` column
  served   mean ``env_return`` per training episode in the window (the shop pays +1 per client served, siren
           off); the policy samples its actions in training
  stages   per-episode mean count of each stage, from ``episodes.csv`` ``rm_path`` and the run's machine
           (arrived/order/picked/prep/served); "-" where the machine does not read that label; a lower bound,
           since ``rm_path`` lists state changes only and a stage that keeps the state is invisible
  eval     the latest ``eval.csv`` row: greedy / sampled mean env return over its episodes, and its step
  entropy  ``train.csv`` entropy at the first update -> mean of the last 10 updates; ev = mean explained variance
The window is the last ``--window`` steps (default 100000), or the first ones with ``--early``.
"""

import argparse
import csv
import re
from itertools import pairwise
from pathlib import Path

import yaml
from sgu import RUNS_ROOT, is_finished, pid_alive, run_folder, select

ROW = re.compile(r"^\((u\d+), (.+)\) -> (u\d+)$")
STAGES = {
    "client_arrived": "arrived",
    "order_taken": "order",
    "holding_food": "picked",
    "food_prepared": "prep",
    "order_served": "served",
}
LAST_UPDATES = 10


# ======================================================================================
#                                      MACHINE STAGES
# ======================================================================================


def read_machine(machine: Path) -> tuple[dict[tuple[str, str], set[str]], set[str]]:
    """The labels certain on each ``a -> b`` edge, and every label a guard of the machine reads.

    A label is certain on an edge when it is positive in every transition row that goes ``a -> b``.
    """
    positives: dict[tuple[str, str], list[set[str]]] = {}
    read: set[str] = set()
    for line in machine.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line.strip())
        if match:
            labels = match[2].split("&")
            read.update(label.lstrip("!") for label in labels)
            positives.setdefault((match[1], match[3]), []).append(
                {label for label in labels if not label.startswith("!")}
            )
    return {edge: set.intersection(*rows) for edge, rows in positives.items()}, read


def stage_means(rows: list[dict], certain: dict[tuple[str, str], set[str]]) -> dict[str, float]:
    """Mean per-episode count of every stage over the episodes' machine paths."""
    totals = dict.fromkeys(STAGES.values(), 0)
    for row in rows:
        states = row["rm_path"].split()
        for edge in pairwise(states):
            for label in certain.get(edge, ()):
                if label in STAGES:
                    totals[STAGES[label]] += 1
    return {stage: total / len(rows) for stage, total in totals.items()} if rows else {}


# ======================================================================================
#                                         ONE RUN
# ======================================================================================


def read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def mean(rows: list[dict], column: str) -> float | None:
    values = [float(row[column]) for row in rows if row.get(column)]
    return sum(values) / len(values) if values else None


def fmt(value: float | None, digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def state_of(name: str, folder: Path | None) -> str:
    if folder is None:
        return "queued"
    if is_finished(folder):
        return "done"
    return "running" if pid_alive(name) else "DEAD"


def stages_cell(folder: Path, rows: list[dict]) -> str:
    saved = yaml.safe_load((folder / "config.yaml").read_text(encoding="utf-8"))
    if not saved.get("bundle"):
        return "n/a (no-RM)"
    certain, read = read_machine(Path(saved["bundle"]) / "reward_machine.txt")
    means = stage_means(rows, certain)
    if not means:
        return "-"
    return "/".join(
        fmt(means[stage], 1) if label in read else "-" for label, stage in STAGES.items()
    )


def window_rows(episodes: list[dict], last_step: int, window: int, early: bool) -> list[dict]:
    if early:
        return [row for row in episodes if int(row["global_step"]) <= window]
    return [row for row in episodes if int(row["global_step"]) > last_step - window]


def progress_cells(run: dict, train: list[dict]) -> tuple[int, str, str]:
    """The latest step, its ``step/total (eta)`` cell, and the entropy cell of the run."""
    if not train:
        return 0, "-", "-"
    step = int(train[-1]["global_step"])
    sps = mean(train[-LAST_UPDATES:], "sps")
    eta = (
        f", {(run['steps'] - step) / sps / 3600:.1f} h left" if sps and step < run["steps"] else ""
    )
    first, now = fmt(float(train[0]["entropy"])), fmt(mean(train[-LAST_UPDATES:], "entropy"))
    return step, f"{step // 1000}k/{run['steps'] // 1000}k{eta}", f"{first}->{now}"


def eval_cell(rows: list[dict]) -> str:
    if not rows:
        return "-"
    last = rows[-1]
    greedy, sampled = (
        fmt(float(last["mean_env_return"]), 1),
        fmt(float(last["sampled_mean_env_return"]), 1),
    )
    return f"{greedy} / {sampled} @{int(last['global_step']) // 1000}k"


def describe(run: dict, window: int, early: bool) -> list[str]:
    name = run["name"]
    folder = run_folder(name)
    state = state_of(name, folder)
    if folder is None:
        return [f"`{name}`", state, "-", "-", "-", "-", "-", "-", "-"]

    train = read_csv(folder / "train.csv")
    step, step_cell, entropy = progress_cells(run, train)
    rows = window_rows(read_csv(folder / "episodes.csv"), step, window, early)
    return [
        f"`{name}`",
        state,
        step_cell,
        str(len(rows)),
        fmt(mean(rows, "env_return"), 2),
        stages_cell(folder, rows),
        eval_cell(read_csv(folder / "eval.csv")),
        entropy,
        fmt(mean(train[-LAST_UPDATES:], "explained_variance")),
    ]


# ======================================================================================
#                                          MAIN
# ======================================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="+", help="r1, r2, r3, dry, all or run names")
    parser.add_argument("--early", action="store_true", help="the first window instead of the last")
    parser.add_argument("--window", type=int, default=100_000, help="window length in steps")
    args = parser.parse_args()

    which = "first" if args.early else "last"
    head = [
        "run",
        "state",
        "step/total",
        f"episodes ({which} {args.window // 1000}k)",
        "served/ep",
        "stages/ep arrived/order/picked/prep/served",
        "eval env return greedy / sampled",
        "entropy first->now",
        "ev",
    ]
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for run in select(args.names):
        print("| " + " | ".join(describe(run, args.window, args.early)) + " |")
    print(
        f"\nRuns root: {RUNS_ROOT}. served/ep is training-episode env return (sampled actions); eval is greedy, 10 episodes."
    )


if __name__ == "__main__":
    main()
