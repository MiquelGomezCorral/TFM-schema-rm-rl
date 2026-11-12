"""Summarize the X1 PPO tuning suites: R46 numbers per run, every eval point, learning curves.

Usage (from the repo root):
    PYTHONPATH=app python experiments/benchmark/tuning/ppo/summarize.py \
        --suites experiments/benchmark/tuning/ppo/base/runs.yaml \
                 experiments/benchmark/tuning/ppo/round1/runs.yaml --out <evidence folder>

Runs are found and read the way ``aggregate-suite`` does it (``run_state``, ``eval_rows``). A
learner named ``ppo`` is the pilot setting and is shown as ``base``. Greedy evaluation on a fixed
layout is one episode, so an eval point is solved (``exit_rate`` 1) or not (0). R46 numbers:
fraction of eval points solved (steps up to 500k), first greedy solve, final eval success.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

import plotly.graph_objects as go
import yaml

from scripts.aggregate_suite import eval_rows, number
from scripts.run_suite import ROOT, expand_runs, load_suite, run_state

STEP_LIMIT = 500_000
TASKS = {"base-doorkey": "DoorKey", "base-unlock-pickup": "UnlockPickup"}
SHORT = {
    "ppo_learning_rate": "lr",
    "ppo_num_envs": "envs",
    "ppo_num_steps": "steps",
    "ppo_num_minibatches": "mb",
    "ppo_update_epochs": "ep",
    "ppo_clip_coef": "clip",
    "ppo_ent_coef": "ent",
    "ppo_gae_lambda": "gae",
    "gamma": "gamma",
}
SMOOTH = 5  # eval points in the trailing mean of the plotted curves
# Curve groups: (index in the palette series or None for the muted line colour, dash, width). The
# pilot setting and the pilot's own runs are single lines; tuned settings fall into three groups.
GROUP_STYLE = {
    "unsolved": (None, "solid", 1.2),
    "solved": (2, "solid", 1.6),
    "best": (0, "solid", 4),
    "base": (4, "dot", 3.5),
    "pilot DQN": (1, "dash", 3),
    "pilot PPO": (3, "dashdot", 3),
}
REFERENCES = ("base", "pilot DQN", "pilot PPO")

PALETTE = {
    "light": {
        "card": "#ffffff",
        "text": "#1d1d1f",
        "line": "#5b5b66",
        "series": [
            "#2f5bd3",
            "#d96f00",
            "#1f7a4d",
            "#b3261e",
            "#b03a9a",
            "#1b7f8c",
            "#6b52c0",
            "#8a6d3b",
        ],
    },
    "dark": {
        "card": "#1d1d21",
        "text": "#ececf0",
        "line": "#b9b9c4",
        "series": [
            "#8fb0ff",
            "#ffa24d",
            "#5fd394",
            "#ff8a80",
            "#e58ad2",
            "#5ccfdc",
            "#b9a2ff",
            "#d8b56b",
        ],
    },
}
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
THEME_SCRIPT = """
const gd = document.getElementById("{plot_id}");
const asked = new URLSearchParams(location.search).get("theme");
const dark = asked ? asked === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
const colors = __PALETTE__[dark ? "dark" : "light"];
const grid = colors.line + "40";
const update = {"font.color": colors.text, colorway: colors.series};
for (const axis of ["xaxis", "yaxis"]) {
  for (const key of ["gridcolor", "zerolinecolor", "linecolor", "tickcolor"]) {
    update[axis + "." + key] = grid;
  }
}
document.body.style.margin = 0;
document.documentElement.style.background = colors.card;
document.documentElement.style.colorScheme = dark ? "dark" : "light";
Plotly.relayout(gd, update);
const style = __GROUPS__;
const lineColors = gd.data.map((trace) => {
  const index = style[trace.legendgroup];
  return index === null ? colors.line + "88" : colors.series[index];
});
Plotly.restyle(gd, {"line.color": lineColors});
""".replace("__PALETTE__", json.dumps(PALETTE))


def theme_script(colors_of: dict[str, int | None]) -> str:
    """Page script that follows the light/dark theme; ``colors_of`` maps each legend group to its series colour."""
    return THEME_SCRIPT.replace("__GROUPS__", json.dumps(colors_of))


# ======================================================================================
#                                        COLLECT
# ======================================================================================


def setting_name(learner: str) -> str:
    return "base" if learner == "ppo" else learner


def describe(overrides: dict) -> str:
    return (
        ", ".join(f"{SHORT[key]} {value:g}" for key, value in overrides.items()) or "pilot setting"
    )


def run_numbers(rows: list[dict]) -> dict:
    """R46 numbers of one run from its eval rows (all rows kept, the fraction uses steps <= 500k)."""
    common = [(int(row["global_step"]), number(row["exit_rate"])) for row in rows]
    common = [(step, value) for step, value in common if step <= STEP_LIMIT]
    solved = [step for step, value in common if value > 0]
    last3 = [number(row["exit_rate"]) for row in rows[-3:]]
    return {
        "points": len(common),
        "fraction": mean(value > 0 for _, value in common),
        "mean_success": mean(value for _, value in common),  # equals fraction on one-episode evals
        "first_solve": solved[0] if solved else None,
        "final": number(rows[-1]["exit_rate"]),
        "last3_all": all(value > 0 for value in last3),
        "rm_return": number(rows[-1]["mean_rm_return"]),
    }


def collect(suite_paths: list[Path]) -> tuple[list[dict], list[dict], dict]:
    """Eval points, one row per finished run, and the description of each setting."""
    points, runs, descriptions = [], [], {}
    for path in suite_paths:
        spec = load_suite(path)
        for run in expand_runs(spec):
            setting = setting_name(run.learner)
            overrides = spec["learners"][run.learner].get("overrides", {})
            descriptions[setting] = describe(overrides)
            status, folder, _ = run_state(run)
            rows = eval_rows(folder) if folder else []
            if status != "finished" or not rows:
                continue
            task = run.card["id"]
            points += [
                {
                    "setting": setting,
                    "task": task,
                    "seed": run.seed,
                    "step": int(row["global_step"]),
                    "greedy_success": number(row["exit_rate"]),
                    "rm_return": number(row["mean_rm_return"]),
                }
                for row in rows
            ]
            resources = json.loads((folder / "resources.json").read_text(encoding="utf-8"))
            runs.append(
                {
                    "setting": setting,
                    "task": task,
                    "seed": run.seed,
                    **run_numbers(rows),
                    "wall_min": round(resources["wall_time_s"] / 60, 2),
                    "peak_gb": resources["peak_rss_gb"],
                }
            )
    return points, runs, descriptions


# ======================================================================================
#                                         OUTPUT
# ======================================================================================


def write_settings(suite_paths: list[Path], out: Path) -> None:
    """One ``settings/<setting>.yaml`` per setting: the learner config with its overrides applied."""
    (out / "settings").mkdir(exist_ok=True)
    for path in suite_paths:
        for learner, learner_spec in load_suite(path)["learners"].items():
            config = yaml.safe_load((ROOT / learner_spec["config"]).read_text(encoding="utf-8"))
            config.update(learner_spec.get("overrides", {}))
            text = yaml.safe_dump(config, sort_keys=False)
            (out / "settings" / f"{setting_name(learner)}.yaml").write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summary_table(runs: list[dict], descriptions: dict) -> str:
    """One row per setting and task, seeds side by side, plus the R46 fraction over all its runs."""
    by_setting = defaultdict(list)
    for run in runs:
        by_setting[run["setting"]].append(run)

    def seeds(group: list[dict], key: str, fmt: str) -> str:
        return " / ".join(
            format(run[key], fmt) if run[key] is not None else "never" for run in group
        )

    lines = [
        "| setting | knobs | task | seeds | fraction solved | mean success | first solve (k steps) | "
        "final | solved at end | wall min | peak GB |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for setting, group in by_setting.items():
        overall = mean(run["fraction"] for run in group)
        for task, label in TASKS.items():
            rows = sorted((r for r in group if r["task"] == task), key=lambda r: r["seed"])
            if not rows:
                continue
            first = " / ".join(
                f"{r['first_solve'] / 1000:.0f}" if r["first_solve"] else "never" for r in rows
            )
            ends = " / ".join("yes" if r["last3_all"] else "no" for r in rows)
            lines.append(
                f"| {setting} | {descriptions[setting]} | {label} | "
                f"{'/'.join(str(r['seed']) for r in rows)} | {seeds(rows, 'fraction', '.2f')} | "
                f"{seeds(rows, 'mean_success', '.2f')} | "
                f"{first} | {seeds(rows, 'final', '.2f')} | {ends} | "
                f"{seeds(rows, 'wall_min', '.1f')} | {max(r['peak_gb'] for r in rows):.1f} |"
            )
        # a setting without a DoorKey run (skipped after failing UnlockPickup) has no all-run mean
        scope = (
            "all runs" if len({run["task"] for run in group}) == len(TASKS) else "UnlockPickup only"
        )
        lines.append(f"| {setting} | | **{scope}** | | **{overall:.3f}** | | | | | | |")
    return "\n".join(lines)


def curves(points: list[dict], task: str, descriptions: dict, best: str | None) -> go.Figure:
    """Greedy success against steps for one task: seed mean per setting, trailing mean of 5 points."""
    series = defaultdict(lambda: defaultdict(list))
    for point in points:
        if point["task"] == task:
            series[point["setting"]][point["step"]].append(point["greedy_success"])
    curve_of, group_of = {}, {}
    for setting, by_step in series.items():
        steps = sorted(by_step)
        raw = [mean(by_step[step]) for step in steps]
        smooth = [mean(raw[max(0, i - SMOOTH + 1) : i + 1]) for i in range(len(raw))]
        curve_of[setting] = (steps, smooth)
        if setting in REFERENCES:
            group_of[setting] = setting
        elif setting == best:
            group_of[setting] = "best"
        else:
            group_of[setting] = "solved" if raw[-1] == 1 else "unsolved"
    sizes = {group: list(group_of.values()).count(group) for group in GROUP_STYLE}
    labels = {
        "unsolved": f"settings that do not solve it ({sizes['unsolved']})",
        "solved": f"other settings that solve it ({sizes['solved']})",
        "best": f"{best} (best)",
        "base": "base (the pilot PPO setting, rerun)",
    }
    fig = go.Figure()
    for group, (_, dash, width) in GROUP_STYLE.items():  # drawing order: references and best on top
        members = [name for name, kind in group_of.items() if kind == group]
        for position, setting in enumerate(members):
            steps, smooth = curve_of[setting]
            fig.add_trace(
                go.Scatter(
                    x=steps,
                    y=smooth,
                    name=labels.get(group, group),
                    legendgroup=group,
                    showlegend=position == 0,
                    mode="lines",
                    line={"width": width, "dash": dash},
                    hovertemplate=f"{setting}: {descriptions[setting]}<br>step %{{x}}<br>%{{y:.0%}}<extra></extra>",
                )
            )
    tuned = sum(group_of[setting] in ("solved", "best") for setting in group_of)
    total = sum(group_of[setting] in ("unsolved", "solved", "best") for setting in group_of)
    fig.update_layout(
        title={
            "text": f"{TASKS[task]}: {tuned} of {total} PPO settings solve it on every seed<br>"
            f"<sup>last eval; {SMOOTH}-point trailing mean of the seed mean</sup>",
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


def load_reference(directory: Path) -> tuple[list[dict], dict]:
    """The pilot's own eval.csv copies (``<learner>-<card id>-seed<N>.csv``) as extra points."""
    points = []
    for path in sorted(directory.glob("*.csv")):
        learner, _, rest = path.stem.partition("-")
        task, _, seed = rest.rpartition("-seed")
        with path.open(newline="", encoding="utf-8") as file:
            rows = [row for row in csv.DictReader(file) if not row["task"]]
        points += [
            {
                "setting": f"pilot {learner.upper()}",
                "task": task,
                "seed": int(seed),
                "step": int(row["global_step"]),
                "greedy_success": number(row["exit_rate"]),
                "rm_return": number(row["mean_rm_return"]),
            }
            for row in rows
        ]
    return points, {
        f"pilot {name}": "the pilot's own runs, seeds 1 and 2" for name in ("DQN", "PPO")
    }


def main(suites: list[Path], out: Path, reference: Path | None, best: str | None) -> None:
    points, runs, descriptions = collect(suites)
    if reference:
        reference_points, reference_descriptions = load_reference(reference)
        points += reference_points
        descriptions |= reference_descriptions
    out.mkdir(parents=True, exist_ok=True)
    write_settings(suites, out)
    write_csv(out / "eval_points.csv", points)
    write_csv(out / "r46_runs.csv", runs)
    table = summary_table(runs, descriptions)
    (out / "summary.md").write_text(table + "\n", encoding="utf-8")
    print(table)
    for task in TASKS:
        curves(points, task, descriptions, best).write_html(
            out / f"curves-{task}.html",
            include_plotlyjs=True,
            config={"displayModeBar": False, "fillFrame": True, "responsive": True},
            post_script=theme_script({group: style[0] for group, style in GROUP_STYLE.items()}),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize X1 PPO tuning suites.")
    parser.add_argument("--suites", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reference", type=Path, help="folder of the pilot's eval.csv copies")
    parser.add_argument("--best", help="setting drawn as the bold line of the learning curves")
    arguments = parser.parse_args()
    main(arguments.suites, arguments.out, arguments.reference, arguments.best)
