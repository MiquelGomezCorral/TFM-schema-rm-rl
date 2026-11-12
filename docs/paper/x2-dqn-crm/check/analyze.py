"""X2 results: R46 numbers per run, an eval-point CSV and one learning-curve page per task.

Run from the worktree root:  PYTHONPATH=app python <this file> <out dir>
Reads every outputs/runs/bench__x2*__<card>__farm__<learner>/seed*/ folder (eval.csv, summary.json,
resources.json) and the run-config.yaml beside them. Writes into <out dir>:
  eval-points.csv   variant, task, seed, step, greedy success, RM return (one row per eval point)
  runs.csv          one row per run: R46 numbers, wall time per 500k steps, peak RAM, settings
  variants.csv      one row per variant and task: the seed means
  results.md        the variants table as Markdown
  curve-<task>.html one self-contained Plotly page per task (greedy success against steps, fixed layouts)
  curve-procedural.html the procedural-layout runs, one line per run seed
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import yaml
from plotly.subplots import make_subplots

RUNS = Path("outputs/runs")
TASKS = {"base-doorkey": "DoorKey", "base-unlock-pickup": "UnlockPickup"}
RUN_FOLDER = re.compile(r"bench__(x2[a-z0-9]*)__(base-[a-z-]+)__farm__(.+)")
SETTINGS = (
    "layout",
    "dqn_num_envs",
    "counterfactual",
    "train_frequency",
    "target_network_frequency",
    "exploration_fraction",
    "end_e",
    "learning_rate",
    "buffer_size",
    "learning_starts",
)
STEPS_REFERENCE = 500_000
SMOOTH_POINTS = (
    5  # the plotted line is the seed mean averaged over this many eval points (50k steps)
)
# Pilot references from the run-ops notes: mean fraction of eval points solved over the run.
PILOT_DQN = 0.77
PILOT_PPO = 0.413

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
""".replace("__PALETTE__", json.dumps(PALETTE))


# The procedural page has one panel per task and traces added seed-major: style panel 2 as well and give every
# trace of a seed the same theme colour in both panels (plotly's colorway goes by trace index).
PROCEDURAL_SCRIPT = (
    THEME_SCRIPT.replace('["xaxis", "yaxis"]', '["xaxis", "yaxis", "xaxis2", "yaxis2"]')
    + """
const panels = __PANELS__;
gd.data.forEach((trace, index) => {
  Plotly.restyle(gd, {"line.color": colors.series[Math.floor(index / panels)]}, [index]);
});
"""
)


def find_runs() -> list[dict]:
    """One dict per seed folder: variant, task, seed, folder, settings, finished."""
    found = []
    for suite_folder in sorted(RUNS.iterdir()):
        match = RUN_FOLDER.fullmatch(suite_folder.name)
        if not match:
            continue
        suite, card, learner = match.groups()
        settings = yaml.safe_load((suite_folder / "run-config.yaml").read_text())
        for folder in sorted(suite_folder.glob("seed*-*")):
            if not all(
                (folder / name).is_file() for name in ("eval.csv", "train.csv", "resources.json")
            ):
                continue  # a run that has only just started
            found.append(
                {
                    "variant": f"{suite}/{learner}",
                    "task": TASKS[card],
                    "seed": int(folder.name.split("-")[0][4:]),
                    "folder": folder,
                    "finished": (folder / "summary.json").is_file(),
                    **{name: settings.get(name) for name in SETTINGS},
                }
            )
    return found


def run_numbers(run: dict) -> tuple[dict, pd.DataFrame]:
    """R46 numbers of one run and its overall eval points."""
    folder = run["folder"]
    evals = pd.read_csv(folder / "eval.csv")
    overall = evals[evals["task"].isna()].reset_index(
        drop=True
    )  # task column is empty on the overall rows
    solved = overall["exit_rate"] > 0
    resources = json.loads((folder / "resources.json").read_text())
    train = pd.read_csv(folder / "train.csv")
    steps_done = int(train["global_step"].iloc[-1]) if len(train) else 0
    wall_min = resources["wall_time_s"] / 60
    numbers = {
        "variant": run["variant"],
        "task": run["task"],
        "seed": run["seed"],
        "finished": run["finished"],
        "eval_points": len(overall),
        "fraction_solved": solved.mean() if len(overall) else float("nan"),
        "first_solve_step": overall.loc[solved, "global_step"].min()
        if solved.any()
        else float("nan"),
        "final_eval_success": overall["exit_rate"].iloc[-1] if len(overall) else float("nan"),
        "mean_eval_success": overall["exit_rate"].mean() if len(overall) else float("nan"),
        "steps_done": steps_done,
        "wall_min": wall_min,
        "wall_min_per_500k": wall_min * STEPS_REFERENCE / steps_done
        if steps_done
        else float("nan"),
        "peak_rss_gb": resources["peak_rss_gb"],
        **{name: run[name] for name in SETTINGS},
    }
    points = pd.DataFrame(
        {
            "variant": run["variant"],
            "task": run["task"],
            "layout": run["layout"],
            "seed": run["seed"],
            "step": overall["global_step"],
            "greedy_success": overall["exit_rate"],
            "rm_return": overall["mean_rm_return"],
        }
    )
    return numbers, points


def variant_table(runs: pd.DataFrame) -> pd.DataFrame:
    """Seed means per variant and task; first solve is the mean over the seeds that solved."""
    rows = []
    for (variant, task), group in runs.groupby(["variant", "task"], sort=True):
        solving = group["first_solve_step"].dropna()
        rows.append(
            {
                "variant": variant,
                "task": task,
                "seeds": len(group),
                "finished": int(group["finished"].sum()),
                "fraction_solved": group["fraction_solved"].mean(),
                "first_solve_step": solving.mean() if len(solving) else float("nan"),
                "seeds_that_solved": len(solving),
                "final_eval_success": group["final_eval_success"].mean(),
                "mean_eval_success": group["mean_eval_success"].mean(),
                "wall_min_per_500k": group["wall_min_per_500k"].mean(),
                "peak_rss_gb": group["peak_rss_gb"].max(),
                **{name: group[name].iloc[0] for name in SETTINGS},
            }
        )
    return pd.DataFrame(rows)


# Legend order of the fixed-layout curves; at most 8 lines so no theme colour repeats.
CURVE_ORDER = (
    "dqn1",
    "dqn8",
    "dqn8-tf8",
    "dqn8-tf16",
    "dqn8-tf8-expl20",
    "dqn1-crm",
    "dqn8-crm",
    "dqn8-crm-buf300k",
)


def curve_figure(task: str, points: pd.DataFrame) -> go.Figure:
    """Seed-mean greedy success against steps, one line per variant, pilot levels as dashed lines.

    Fixed layouts only. The seed-3 confirmation (suite x2c) joins the line of its setting.
    """
    fig = go.Figure()
    task_points = points[(points["task"] == task) & (points["layout"] == "fixed")].copy()
    task_points["learner"] = task_points["variant"].str.split("/").str[1]
    assert set(task_points["learner"]) <= set(CURVE_ORDER), set(task_points["learner"])
    for variant in (name for name in CURVE_ORDER if name in set(task_points["learner"])):
        group = task_points[task_points["learner"] == variant]
        seeds = sorted(group["seed"].unique())
        mean = group.groupby("step")["greedy_success"].mean()
        smooth = mean.rolling(SMOOTH_POINTS, min_periods=1).mean()
        fig.add_trace(
            go.Scatter(
                x=smooth.index,
                y=smooth.values,
                name=f"{variant} (seeds {','.join(map(str, seeds))})",
                mode="lines",
                hovertemplate=f"{variant}<br>step %{{x}}<br>greedy success %{{y:.0%}}<extra></extra>",
            )
        )
    for label, level in (
        (f"pilot DQN, run mean {PILOT_DQN:.2f}", PILOT_DQN),
        (f"pilot PPO, run mean {PILOT_PPO:.2f}", PILOT_PPO),
    ):
        fig.add_hline(
            y=level,
            line={"dash": "dash", "color": "#8a8a93", "width": 1},
            annotation_text=label,
            annotation_position="bottom right",
            annotation_font={"size": 11, "color": "#8a8a93"},
        )
    fig.update_layout(
        title={
            "text": f"{task}: greedy success while training,<br>mean of seeds",
            "x": 0,
            "font": {"size": 15},
        },
        xaxis_title="Training steps",
        yaxis_title=f"Greedy success ({SMOOTH_POINTS}-point average)",
        yaxis_tickformat=".0%",
        yaxis_range=[-0.02, 1.02],
        xaxis_tickformat=".3~s",
        colorway=PALETTE["light"]["series"],
        font={"family": FONT, "color": PALETTE["light"]["text"]},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "y": -0.25},
    )
    return fig


def procedural_figure(points: pd.DataFrame) -> go.Figure:
    """Procedural training: share of the 10 held-out layouts solved, one line per run seed, per task."""
    tasks = sorted(points.loc[points["layout"] == "procedural", "task"].unique())
    fig = make_subplots(rows=1, cols=len(tasks), subplot_titles=tasks, shared_yaxes=True)
    procedural = points[points["layout"] == "procedural"]
    for seed in sorted(
        procedural["seed"].unique()
    ):  # seed-major, so a seed keeps its colour in every panel
        for column, task in enumerate(tasks, start=1):
            line = procedural[(procedural["task"] == task) & (procedural["seed"] == seed)]
            fig.add_trace(
                go.Scatter(
                    x=line["step"],
                    y=line["greedy_success"],
                    name=f"run seed {seed}",
                    mode="lines",
                    legendgroup=f"seed{seed}",
                    showlegend=column == 1,
                    hovertemplate=f"{task}, run seed {seed}<br>step %{{x}}<br>held-out layouts solved %{{y:.0%}}<extra></extra>",
                ),
                row=1,
                col=column,
            )
    for column in range(1, len(tasks) + 1):
        fig.update_xaxes(title_text="Training steps", tickformat=".3~s", row=1, col=column)
    fig.update_yaxes(
        title_text="Held-out layouts solved", tickformat=".0%", range=[-0.02, 1.02], row=1, col=1
    )
    fig.update_layout(
        title={
            "text": "Procedural training, 8 envs: share of the 10 held-out<br>layouts solved, per run seed",
            "x": 0,
            "font": {"size": 15},
        },
        colorway=PALETTE["light"]["series"],
        font={"family": FONT, "color": PALETTE["light"]["text"]},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "y": -0.25},
    )
    return fig


def markdown(table: pd.DataFrame) -> str:
    """The variants table as Markdown, one block per task."""
    out = []
    for task, group in table.groupby("task"):
        out.append(f"### {task}\n")
        out.append(
            "| variant | seeds (done) | fraction solved | mean eval success | first solve | final eval | min / 500k | peak RAM GB |"
        )
        out.append("|---|---|---|---|---|---|---|---|")
        for row in group.itertuples():
            first = (
                f"{row.first_solve_step / 1000:.0f}k ({row.seeds_that_solved}/{row.seeds})"
                if row.seeds_that_solved
                else "never"
            )
            out.append(
                f"| {row.variant} | {row.seeds} ({row.finished}) | {row.fraction_solved:.2f} | {row.mean_eval_success:.2f} | {first} | "
                f"{row.final_eval_success:.2f} | {row.wall_min_per_500k:.1f} | {row.peak_rss_gb:.2f} |"
            )
        out.append("")
    return "\n".join(out)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    numbers, frames = zip(*(run_numbers(run) for run in find_runs()), strict=True)
    runs = pd.DataFrame(numbers)
    points = pd.concat(frames, ignore_index=True)
    table = variant_table(runs)
    points.to_csv(out / "eval-points.csv", index=False)
    runs.to_csv(out / "runs.csv", index=False)
    table.to_csv(out / "variants.csv", index=False)
    (out / "results.md").write_text(markdown(table))
    pages = {
        f"curve-{task.lower()}.html": curve_figure(task, points) for task in points["task"].unique()
    }
    pages["curve-procedural.html"] = procedural_figure(points)
    panels = points.loc[points["layout"] == "procedural", "task"].nunique()
    for name, figure in pages.items():
        script = (
            PROCEDURAL_SCRIPT.replace("__PANELS__", str(panels))
            if name == "curve-procedural.html"
            else THEME_SCRIPT
        )
        figure.write_html(
            out / name,
            include_plotlyjs=True,
            config={"displayModeBar": False, "fillFrame": True},
            post_script=script,
        )
    print(markdown(table))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
