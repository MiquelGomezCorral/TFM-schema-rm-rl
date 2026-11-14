"""Summarize the X1 procedural-layout step: the restarted runs beside the runs the memory reaper stopped.

Usage (from the repo root):
    PYTHONPATH=app python experiments/benchmark/tuning/ppo/summarize_procedural.py \
        --suites experiments/benchmark/tuning/ppo/procedural/runs.yaml \
        --stopped <runs.yaml of the first launch> --out <evidence folder>

Procedural evaluation is 10 greedy episodes per point, so ``exit_rate`` is a fraction of 10 and the
last row of a finished run is the 100-episode final evaluation. The stopped runs have no final
row, so the table also gives each run's fraction up to the step where its stopped twin ended.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

import plotly.graph_objects as go
from summarize import FONT, PALETTE, SMOOTH, STEP_LIMIT, TASKS, theme_script, write_csv

from scripts.aggregate_suite import eval_rows, number
from scripts.run_suite import expand_runs, load_suite, run_state

SEED_COLORS = {"seed 1": 0, "seed 21": 1, "seed 41": 2}


def read_runs(suite: Path, launch: str) -> list[dict]:
    """The runs of a suite that have eval rows, with their status and rows."""
    found = []
    for run in expand_runs(load_suite(suite)):
        status, folder, _ = run_state(run)
        rows = eval_rows(folder) if folder else []
        if rows:
            found.append(
                {"launch": launch, "task": run.card["id"], "seed": run.seed, "status": status}
                | {"rows": rows, "folder": folder}
            )
    return found


def fraction_to(rows: list[dict], horizon: int) -> float:
    """Share of the eval points up to ``horizon`` steps with any greedy success."""
    values = [number(row["exit_rate"]) for row in rows if int(row["global_step"]) <= horizon]
    return mean(value > 0 for value in values)


def numbers(run: dict, horizons: dict[str, int]) -> dict:
    """R46 numbers of one run, over the points it has."""
    rows = run["rows"]
    steps = [int(row["global_step"]) for row in rows]
    values = [number(row["exit_rate"]) for row in rows]
    solved = [step for step, value in zip(steps, values, strict=True) if value > 0]
    resources = run["folder"] / "resources.json"
    wall = (
        json.loads(resources.read_text(encoding="utf-8")).get("wall_time_s")
        if resources.is_file()
        else None
    )
    return {
        "launch": run["launch"],
        "task": run["task"],
        "seed": run["seed"],
        "status": run["status"],
        "last_step": steps[-1],
        "points": len(rows),
        "fraction": fraction_to(rows, STEP_LIMIT),
        "mean_success": mean(values),
        "fraction_to_stopped_horizon": fraction_to(rows, horizons[run["task"]]),
        "first_solve": solved[0] if solved else None,
        "final": values[-1],
        "final_episodes": int(rows[-1]["episodes"]),
        "wall_min": round(wall / 60, 2) if wall else None,
    }


def table(summaries: list[dict], horizons: dict[str, int]) -> str:
    lines = [
        "| card | seed | launch | status | last step (k) | points | fraction solved | mean success | "
        "fraction to the stopped horizon | first solve (k) | last eval | wall min |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for task, label in TASKS.items():
        for run in (r for r in summaries if r["task"] == task):
            first = f"{run['first_solve'] / 1000:.0f}" if run["first_solve"] else "never"
            wall = f"{run['wall_min']:.1f}" if run["wall_min"] else "-"
            lines.append(
                f"| {label} | {run['seed']} | {run['launch']} | {run['status']} | "
                f"{run['last_step'] / 1000:.0f} | {run['points']} | {run['fraction']:.2f} | "
                f"{run['mean_success']:.2f} | {run['fraction_to_stopped_horizon']:.2f} "
                f"(to {horizons[task] / 1000:.0f}k) | {first} | "
                f"{run['final']:.2f} ({run['final_episodes']} episodes) | {wall} |"
            )
    return "\n".join(lines)


def trailing(values: list[float]) -> list[float]:
    return [mean(values[max(0, i - SMOOTH + 1) : i + 1]) for i in range(len(values))]


def curves(runs: list[dict], task: str) -> go.Figure:
    """One line per run: trailing mean of its greedy success; stopped runs dotted."""
    fig = go.Figure()
    for run in sorted(runs, key=lambda r: (r["seed"], r["launch"])):
        if run["task"] != task:
            continue
        steps = [int(row["global_step"]) for row in run["rows"]]
        values = trailing([number(row["exit_rate"]) for row in run["rows"]])
        stopped = run["launch"] == "stopped"
        reason = f"stopped at {steps[-1] // 1000}k by the memory reaper"
        note = f", {run['status']} at {steps[-1] // 1000}k" if run["status"] != "finished" else ""
        fig.add_trace(
            go.Scatter(
                x=steps,
                y=values,
                name=f"seed {run['seed']}, " + (reason if stopped else f"restart{note}"),
                legendgroup=f"seed {run['seed']}",
                mode="lines",
                line={"width": 2.5, "dash": "dot" if stopped else "solid"},
            )
        )
    fig.update_layout(
        title={
            "text": f"{TASKS[task]}, procedural layout: greedy success<br>"
            f"<sup>10 episodes per point; {SMOOTH}-point trailing mean</sup>",
            "x": 0,
            "font": {"size": 14},
        },
        xaxis_title="Training steps",
        yaxis_title="Greedy eval success",
        yaxis_tickformat=".0%",
        font={"family": FONT, "color": PALETTE["light"]["text"]},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 55, "r": 12, "t": 70, "b": 60},
        legend={"orientation": "h", "y": -0.25},
    )
    return fig


def main(suites: list[Path], stopped: list[Path], out: Path) -> None:
    runs = [run for suite in suites for run in read_runs(suite, "restart")]
    runs += [run for suite in stopped for run in read_runs(suite, "stopped")]
    last_steps = defaultdict(list)
    for run in runs:
        if run["launch"] == "stopped":
            last_steps[run["task"]].append(int(run["rows"][-1]["global_step"]))
    horizons = {task: min(steps) for task, steps in last_steps.items()}
    summaries = [numbers(run, horizons) for run in runs]
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "r46_runs.csv", summaries)
    write_csv(
        out / "eval_points.csv",
        [
            {
                "launch": run["launch"],
                "task": run["task"],
                "seed": run["seed"],
                "step": int(row["global_step"]),
                "greedy_success": number(row["exit_rate"]),
                "rm_return": number(row["mean_rm_return"]),
            }
            for run in runs
            for row in run["rows"]
        ],
    )
    text = table(summaries, horizons)
    (out / "summary.md").write_text(text + "\n", encoding="utf-8")
    print(text)
    for task in TASKS:
        curves(runs, task).write_html(
            out / f"curves-{task}.html",
            include_plotlyjs=True,
            config={"displayModeBar": False, "fillFrame": True, "responsive": True},
            post_script=theme_script(SEED_COLORS),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize the X1 procedural-layout step.")
    parser.add_argument("--suites", type=Path, nargs="+", required=True)
    parser.add_argument("--stopped", type=Path, nargs="*", default=[])
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    main(arguments.suites, arguments.stopped, arguments.out)
