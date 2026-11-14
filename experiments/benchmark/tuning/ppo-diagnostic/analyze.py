"""Summarize the PPO diagnostic runs: per-run and per-variant tables, CSVs and interactive curves.

Reads every finished (or still running) run under ``outputs/runs/bench__ppo-diag-*`` (the smoke
suite is skipped) and writes, into ``--out``:

* ``runs.csv`` (one row per run) and ``variants.csv`` (one row per variant),
* ``tables.md`` (the same numbers as Markdown, plus the NL task, LTL and RM of each card),
* ``curves_eval.csv``, ``curves_training.csv`` (the data of the plots, mean over seeds),
* ``plots/*.html`` (Plotly, light and dark theme, ``plotly.min.js`` beside them),
* ``rm/<card>.html`` (the repo's interactive Reward Machine graph, from ``render-rm --html``).

Definitions. A run's success is the share of the 100 fixed evaluation layouts it solves (final
evaluation) or of the 10 layouts of a periodic evaluation point. *Greedy* picks the most likely
action, *sampled* draws from the policy. *First solve* is the first evaluation step with a success
above 0, *steps to 0.8* the first step with success of at least 0.8. A training episode is solved
when its environment return is positive. RM items are the Reward Machine states past the start
that a training episode reached: key, door, box (or goal).

Usage (from the repo root):
    PYTHONPATH=app python experiments/benchmark/tuning/ppo-diagnostic/analyze.py --out <folder>
"""

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from scripts.render_rm import render_file
from src.utils.presentation import ltlf_of, pretty_ltlf

# A median over seeds that never solved is NaN on purpose (printed as "never").
warnings.filterwarnings("ignore", message="Mean of empty slice", category=RuntimeWarning)

RUNS = Path("outputs/runs")
TASKS = Path("experiments/benchmark/tuning/ppo-diagnostic/tasks.json")
BUNDLES = Path("experiments/benchmark/pilot/bundles/farm")
TOTAL_STEPS = {"base-unlock-pickup": 1_500_000, "base-doorkey": 500_000}
GRID_STEP = 25_000  # the step grid the seeds are averaged on
BIN_STEP = 50_000  # the training-episode and entropy bins
SOLVED = 0.8
# (arm, learner) -> variant name. The no-RM arm is "env": the environment reward only.
VARIANTS = {
    ("farm", "s07"): "rm",
    ("no-rm", "s07"): "env",
    ("farm", "s07-tuned"): "rm-tuned",
    ("no-rm", "s07-tuned"): "env-tuned",
    ("farm", "s07-epsilon"): "rm-epsilon",
    ("farm", "s07-entropy"): "rm-entropy",
    ("farm", "tuned-epsilon"): "rm-tuned-epsilon",
    ("farm", "tuned-entropy"): "rm-tuned-entropy",
}
ORDER = list(VARIANTS.values())
# The plot groups: the base settings, then the two exploration variants on each base.
GROUPS = {
    "settings": ["rm", "env", "rm-tuned", "env-tuned"],
    "explore-s07": ["rm", "rm-epsilon", "rm-entropy"],
    "explore-tuned": ["rm-tuned", "rm-tuned-epsilon", "rm-tuned-entropy"],
}
# The Reward Machine states that mark progress (key, door open, last step) per card.
ITEMS = {
    "base-unlock-pickup": {"key": "u2", "door": "u3", "last": "u4"},
    "base-doorkey": {"key": "u1", "door": "u3", "last": "u4"},
}
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
            "#6b5b00",
            "#5b5b66",
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
            "#d9c35a",
            "#b9b9c4",
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
for (const axis of Object.keys(gd.layout).filter((key) => /^[xy]axis/.test(key))) {
  for (const key of ["gridcolor", "zerolinecolor", "linecolor", "tickcolor"]) {
    update[axis + "." + key] = grid;
  }
}
gd.data.forEach((trace, index) => {
  if (typeof trace.meta === "number") {
    Plotly.restyle(gd, {"line.color": colors.series[trace.meta]}, [index]);
  }
});
document.body.style.margin = 0;
document.documentElement.style.background = colors.card;
document.documentElement.style.colorScheme = dark ? "dark" : "light";
Plotly.relayout(gd, update);
""".replace("__PALETTE__", json.dumps(PALETTE))


# ======================================================================================
#                                         LOADING
# ======================================================================================


def overall_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """The overall rows of an ``eval.csv``, as ``scripts.aggregate_suite.eval_rows`` keeps them.

    A multi-task run also has per-task rows (a ``task`` value); runs from before it have no column.
    """
    return frame[frame["task"].isna()] if "task" in frame else frame


def load_runs() -> list[dict]:
    """Every run folder of the diagnostic suites, with its CSVs and its final summary."""
    runs = []
    for exp in sorted(RUNS.glob("bench__ppo-diag-*__*__*__*")):
        _, suite, card, arm, learner = exp.name.split("__")
        if suite == "ppo-diag-smoke" or (arm, learner) not in VARIANTS:
            continue
        variant = VARIANTS[arm, learner]
        for folder in sorted(exp.glob("seed*-*")):
            if "." in folder.name or not (folder / "eval.csv").is_file():
                continue
            summary = folder / "summary.json"
            final = json.loads(summary.read_text())["final_eval"] if summary.is_file() else None
            runs.append(
                {
                    "variant": variant,
                    "card": card,
                    "seed": int(folder.name.split("-")[0].removeprefix("seed")),
                    "folder": folder,
                    "final": final,
                    "eval": overall_rows(pd.read_csv(folder / "eval.csv")),
                    "train": pd.read_csv(folder / "train.csv"),
                    "episodes": pd.read_csv(folder / "episodes.csv"),
                }
            )
    return runs


def first_step(frame: pd.DataFrame, column: str, threshold: float, strict: bool) -> float:
    """The first evaluation step whose ``column`` is above (strict) or at least ``threshold``."""
    hit = frame[frame[column] > threshold] if strict else frame[frame[column] >= threshold]
    return float(hit["global_step"].iloc[0]) if len(hit) else np.nan


def training_success(run: dict) -> pd.Series:
    """Training episodes solved (positive environment return), indexed by episode end step."""
    episodes = run["episodes"]
    return pd.Series((episodes["env_return"] > 0).to_numpy(float), index=episodes["global_step"])


def step_to_rolling(run: dict, share: float, window: int = 100) -> float:
    """The first step where the last ``window`` training episodes are solved at least ``share``."""
    solved = training_success(run)
    rolling = solved.rolling(window).mean()
    hit = rolling[rolling >= share]
    return float(hit.index[0]) if len(hit) else np.nan


def reached(run: dict, last_steps: int = 200_000) -> dict[str, float]:
    """Share of the training episodes of the last ``last_steps`` that got to the key, the door, the box.

    Only Reward Machine runs record the path; the others give NaN.
    """
    episodes = run["episodes"]
    names = ITEMS[run["card"]]
    if not episodes["rm_path"].notna().any():
        return {f"reach_{name}": np.nan for name in names}
    tail = episodes[episodes["global_step"] > episodes["global_step"].max() - last_steps]
    paths = tail["rm_path"].fillna("").astype(str).str.split()
    return {
        f"reach_{name}": float(paths.map(lambda path, state=state: state in path).mean())
        for name, state in names.items()
    }


def health(run: dict, until: int = 500_000) -> dict[str, float]:
    """Mean policy drift per update, clipped share and critic fit over the first ``until`` steps."""
    early = run["train"][run["train"]["global_step"] <= until]
    return {
        "kl_early": float(early["approx_kl"].mean()),
        "clipfrac_early": float(early["clipfrac"].mean()),
        "explained_variance_early": float(early["explained_variance"].mean()),
    }


def run_row(run: dict) -> dict[str, object]:
    """The numbers of one run (see the module docstring for the definitions)."""
    evaluation, train = run["eval"], run["train"]
    final = run["final"] or {}
    last = evaluation.iloc[-1]
    jump = step_to_rolling(run, 0.5)
    before = train[train["global_step"] <= jump]["entropy"].tail(5) if jump == jump else None
    return {
        "variant": run["variant"],
        "card": run["card"],
        "seed": run["seed"],
        "status": "finished" if run["final"] else "running",
        "steps_logged": int(last["global_step"]),
        "first_solve_greedy": first_step(evaluation, "exit_rate", 0, True),
        "first_solve_sampled": first_step(evaluation, "sampled_exit_rate", 0, True),
        "to_0.8_greedy": first_step(evaluation, "exit_rate", SOLVED, False),
        "to_0.8_sampled": first_step(evaluation, "sampled_exit_rate", SOLVED, False),
        "train_to_0.5": jump,
        "final_greedy": final.get("exit_rate", float(last["exit_rate"])),
        "final_sampled": final.get("sampled_exit_rate", float(last["sampled_exit_rate"])),
        "entropy_at_jump": float(before.mean()) if before is not None and len(before) else np.nan,
        "entropy_final": float(train["entropy"].tail(10).mean()),
        "entropy_min": float(train["entropy"].min()),
        "last100_train_solved": float(training_success(run).tail(100).mean()),
        **reached(run),
        **health(run),
    }


def variant_rows(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per card and variant: seeds, solved seeds and medians over the solving seeds."""
    rows = []
    for (card, variant), group in runs.groupby(["card", "variant"], sort=False):
        solved = group[group["final_greedy"] >= SOLVED]
        rows.append(
            {
                "card": card,
                "variant": variant,
                "seeds": len(group),
                "finished": int((group["status"] == "finished").sum()),
                "solved_greedy": len(solved),
                "solved_sampled": int((group["final_sampled"] >= SOLVED).sum()),
                "median_first_solve_greedy": group["first_solve_greedy"].median(),
                "median_to_0.8_greedy": group["to_0.8_greedy"].median(),
                "median_to_0.8_sampled": group["to_0.8_sampled"].median(),
                "latest_to_0.8_greedy": group["to_0.8_greedy"].max(),
                "mean_final_greedy": group["final_greedy"].mean(),
                "mean_final_sampled": group["final_sampled"].mean(),
                "kl_early": group["kl_early"].mean(),
                "clipfrac_early": group["clipfrac_early"].mean(),
                "explained_variance_early": group["explained_variance_early"].mean(),
            }
        )
    return pd.DataFrame(rows)


# ======================================================================================
#                                         CURVES
# ======================================================================================


def hold(frame: pd.DataFrame, column: str, grid: np.ndarray) -> np.ndarray:
    """``column`` at each grid step, holding the last evaluation value; NaN past the last row."""
    steps = frame["global_step"].to_numpy()
    index = np.searchsorted(steps, grid, side="right") - 1
    values = np.where(index >= 0, frame[column].to_numpy()[np.maximum(index, 0)], 0.0)
    return np.where(grid <= steps[-1] + GRID_STEP, values, np.nan)


def eval_curves(runs: list[dict]) -> pd.DataFrame:
    """Greedy and sampled success on the step grid, per run (long format)."""
    rows = []
    for run in runs:
        grid = np.arange(0, TOTAL_STEPS[run["card"]] + 1, GRID_STEP)
        frame = pd.DataFrame(
            {
                "card": run["card"],
                "variant": run["variant"],
                "seed": run["seed"],
                "step": grid,
                "greedy": hold(run["eval"], "exit_rate", grid),
                "sampled": hold(run["eval"], "sampled_exit_rate", grid),
            }
        )
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def training_curves(runs: list[dict]) -> pd.DataFrame:
    """Per run and 50k-step bin: training solved share, RM items, entropy (long format)."""
    rows = []
    for run in runs:
        episodes, train = run["episodes"].copy(), run["train"].copy()
        items = ITEMS[run["card"]]
        if "rm_path" in episodes and episodes["rm_path"].notna().any():
            paths = episodes["rm_path"].fillna("").astype(str).str.split()
            for name, state in items.items():
                episodes[name] = paths.map(lambda path, state=state: float(state in path))
            episodes["items"] = episodes[list(items)].sum(axis=1)
        episodes["solved"] = (episodes["env_return"] > 0).astype(float)
        episodes["bin"] = (episodes["global_step"] // BIN_STEP + 1) * BIN_STEP
        train["bin"] = (train["global_step"] // BIN_STEP + 1) * BIN_STEP
        columns = [c for c in ("solved", "items", *items) if c in episodes]
        binned = episodes.groupby("bin")[columns].mean()
        binned["entropy"] = train.groupby("bin")["entropy"].mean()
        binned = binned.reset_index().rename(columns={"bin": "step"})
        binned.insert(0, "seed", run["seed"])
        binned.insert(0, "variant", run["variant"])
        binned.insert(0, "card", run["card"])
        rows.append(binned)
    return pd.concat(rows, ignore_index=True)


# ======================================================================================
#                                          PLOTS
# ======================================================================================


def trace(x, y, name: str, variant: str, **style) -> go.Scatter:
    """One line in the colour of ``variant``; ``meta`` lets the theme script recolour it."""
    width, dash, opacity, legend = (
        style.get("width", 3),
        style.get("dash", "solid"),
        style.get("opacity", 1),
        style.get("legend", True),
    )
    index = ORDER.index(variant)
    return go.Scatter(
        x=x / 1000,
        y=y,
        mode="lines",
        name=name,
        meta=index,
        legendgroup=name,
        showlegend=legend,
        opacity=opacity,
        line={"color": PALETTE["light"]["series"][index], "width": width, "dash": dash},
        hovertemplate=f"{name}<br>step %{{x:.0f}}k<br>%{{y}}<extra></extra>",
    )


def layout(fig: go.Figure, title: str, height: int) -> go.Figure:
    """Common layout: claim title, transparent background, bottom legend."""
    fig.update_layout(
        title={"text": title, "x": 0, "font": {"size": 15}},
        colorway=PALETTE["light"]["series"],
        font={"family": FONT, "color": PALETTE["light"]["text"]},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "y": -0.1},
        hovermode="closest",
        height=height,
    )
    return fig


def success_figure(curves: pd.DataFrame, variants: list[str], title: str) -> go.Figure:
    """One panel per variant: greedy success per seed (thin), its mean (solid), sampled mean (dashed)."""
    variants = [v for v in variants if v in set(curves["variant"])]
    fig = make_subplots(
        rows=len(variants),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=variants,
    )
    for position, variant in enumerate(variants, 1):
        group = curves[curves["variant"] == variant]
        per_seed = group.pivot(index="step", columns="seed", values="greedy")
        mean = group.groupby("step")[["greedy", "sampled"]].mean()
        for seed in per_seed.columns:
            thin = trace(
                per_seed.index.to_numpy(), per_seed[seed], f"{variant} seed {seed} greedy", variant,
                width=1, opacity=0.3, legend=False,
            )  # fmt: skip
            fig.add_trace(thin, row=position, col=1)
        for column, dash in (("greedy", "solid"), ("sampled", "dash")):
            line = trace(
                mean.index.to_numpy(), mean[column], f"{variant} {column}, mean of seeds", variant,
                dash=dash, legend=False, width=2.5,
            )  # fmt: skip
            fig.add_trace(line, row=position, col=1)
    fig.update_yaxes(tickformat=".0%", hoverformat=".0%", range=[0, 1.02])
    fig.update_xaxes(title_text="Training steps (thousands)", row=len(variants), col=1)
    return layout(fig, title, 190 * len(variants) + 110)


def training_figure(train: pd.DataFrame, variants: list[str], title: str) -> go.Figure:
    """Three rows by variant (mean of seeds, per 50k steps): solved share, RM items, entropy."""
    variants = [v for v in variants if v in set(train["variant"])]
    rows = (
        ("solved", "Solved", ".0%"),
        ("items", "RM items", ".1f"),
        ("entropy", "Entropy", ".2f"),
    )
    fig = make_subplots(rows=len(rows), cols=1, shared_xaxes=True, vertical_spacing=0.07)
    for position, (column, label, fmt) in enumerate(rows, 1):
        for variant in variants:
            group = train[train["variant"] == variant]
            if group[column].notna().any():
                mean = group.groupby("step")[column].mean()
                line = trace(mean.index.to_numpy(), mean, variant, variant, legend=position == 1)
                fig.add_trace(line, row=position, col=1)
        fig.update_yaxes(title_text=label, tickformat=fmt, hoverformat=fmt, row=position, col=1)
    fig.update_xaxes(title_text="Training steps (thousands)", row=len(rows), col=1)
    return layout(fig, title, 640)


def save(fig: go.Figure, out: Path, name: str) -> None:
    """Write one themed plot to ``<out>/plots/<name>.html`` (shared ``plotly.min.js``)."""
    path = out / "plots" / f"{name}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        path,
        include_plotlyjs="directory",
        config={"displayModeBar": False, "fillFrame": True},
        post_script=THEME_SCRIPT,
    )


def last_values(curves: pd.DataFrame, column: str, variants: list[str]) -> str:
    """``variant 63%, ...``: the seed mean of ``column`` at the last step every variant reached."""
    done = curves[curves["variant"].isin(variants)].dropna(subset=[column])
    last = done.groupby("variant")["step"].max().min()
    at_last = done[done["step"] == last].groupby("variant")[column].mean()
    values = ", ".join(f"{v} {at_last[v]:.0%}" for v in variants if v in at_last)
    return f"{last // 1000}k steps, mean of seeds: {values}"


def make_plots(eval_data: pd.DataFrame, train_data: pd.DataFrame, out: Path) -> list[str]:
    """Write every plot; return the plot names. Titles quote numbers computed from the data."""
    figures: dict[str, go.Figure] = {}
    unlock = eval_data[eval_data["card"] == "base-unlock-pickup"]
    train_unlock = train_data[train_data["card"] == "base-unlock-pickup"]
    for group, variants in GROUPS.items():
        figures[f"success-{group}"] = success_figure(
            unlock,
            variants,
            "Greedy success per seed (thin) and mean (solid); sampled mean (dashed)<br>"
            + last_values(unlock, "greedy", variants).replace("mean of seeds", "greedy"),
        )
        figures[f"training-{group}"] = training_figure(
            train_unlock,
            variants,
            "Training episodes, mean of seeds per 50k steps: solved, Reward Machine items "
            "reached (key, door, box; 3 = solved), policy entropy (maximum 1.95)",
        )
    doorkey_eval = eval_data[eval_data["card"] == "base-doorkey"]
    if len(doorkey_eval):
        figures["success-doorkey-env"] = success_figure(
            doorkey_eval,
            ["env"],
            "DoorKey without the Reward Machine: greedy (solid), sampled (dashed)",
        )
    for name, fig in figures.items():
        save(fig, out, name)
    return list(figures)


# ======================================================================================
#                                    TABLES AND CARDS
# ======================================================================================


def k(value: float) -> str:
    """Steps in thousands, or ``never``."""
    return "never" if value != value else f"{value / 1000:.0f}k"


def pct(value: float) -> str:
    return f"{value:.0%}"


def runs_table(runs: pd.DataFrame) -> str:
    """The per-run Markdown table."""
    lines_ = [
        "| card | variant | seed | status | first solve greedy / sampled | steps to 0.8 greedy / sampled "
        "| final greedy / sampled (100 layouts) | entropy at jump / final "
        "| training reached key / door / box (last 200k steps) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in runs.iterrows():
        entropy = (
            "-" if r["entropy_at_jump"] != r["entropy_at_jump"] else f"{r['entropy_at_jump']:.2f}"
        )
        steps = [r["reach_key"], r["reach_door"], r["reach_last"]]
        reach = "-" if steps[0] != steps[0] else " / ".join(pct(step) for step in steps)
        lines_.append(
            f"| {r['card']} | {r['variant']} | {r['seed']} | {r['status']} "
            f"| {k(r['first_solve_greedy'])} / {k(r['first_solve_sampled'])} "
            f"| {k(r['to_0.8_greedy'])} / {k(r['to_0.8_sampled'])} "
            f"| {pct(r['final_greedy'])} / {pct(r['final_sampled'])} "
            f"| {entropy} / {r['entropy_final']:.2f} | {reach} |"
        )
    return "\n".join(lines_)


def variants_table(variants: pd.DataFrame) -> str:
    """The per-variant Markdown table."""
    lines_ = [
        "Medians and the latest are over the seeds that reach the number; `never` means no seed does.",
        "",
        "| card | variant | seeds | solved greedy | solved sampled | median first solve (greedy) "
        "| median steps to 0.8 greedy / sampled | latest steps to 0.8 (greedy) "
        "| mean final greedy / sampled |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in variants.iterrows():
        lines_.append(
            f"| {r['card']} | {r['variant']} | {r['seeds']} ({r['finished']} finished) "
            f"| {r['solved_greedy']} of {r['seeds']} | {r['solved_sampled']} of {r['seeds']} "
            f"| {k(r['median_first_solve_greedy'])} "
            f"| {k(r['median_to_0.8_greedy'])} / {k(r['median_to_0.8_sampled'])} "
            f"| {k(r['latest_to_0.8_greedy'])} "
            f"| {pct(r['mean_final_greedy'])} / {pct(r['mean_final_sampled'])} |"
        )
    lines_ += [
        "",
        "Optimizer health, mean over the first 500k steps (policy drift per update, share of "
        "samples at the clip, critic fit):",
        "",
        "| card | variant | approx_kl | clipfrac | explained variance |",
        "|---|---|---|---|---|",
    ]
    for _, r in variants.iterrows():
        lines_.append(
            f"| {r['card']} | {r['variant']} | {r['kl_early']:.3f} | {r['clipfrac_early']:.2f} "
            f"| {r['explained_variance_early']:.2f} |"
        )
    return "\n".join(lines_)


def card_info(card_id: str, out: Path) -> dict:
    """NL task, LTL (the card's reference clauses) and RM text of a card; writes ``rm/<card>.html``."""
    card = next(c for c in json.loads(TASKS.read_text())["cards"] if c["id"] == card_id)
    rm_file = BUNDLES / card_id / "reward_machine.txt"
    render_file(rm_file, out / "rm" / f"{card_id}.svg", html=True)
    return {
        "task": card["task"],
        "clauses": [
            f"`{pattern}({', '.join(props)})` [{hardness}]: `{pretty_ltlf(ltlf_of(pattern, props))}`"
            for pattern, props, hardness in card["expect"]
        ],
        "rm": rm_file.read_text().strip(),
    }


def card_markdown(card_id: str, info: dict) -> str:
    """The Markdown block of one card for ``tables.md``."""
    clauses = "\n".join(f"- {clause}" for clause in info["clauses"])
    return (
        f"### {card_id}\n\n**Task:** {info['task']}\n\n**LTL** (the card's reference clauses, the "
        f"expected specification; the Reward Machine below is the compiled bundle that trains):\n"
        f"{clauses}\n\n**Reward Machine** (interactive graph: `rm/{card_id}.html`):\n\n```\n"
        f"{info['rm']}\n```\n"
    )


def main(out: Path) -> None:
    """Load the runs, write the CSVs, tables and plots into ``out``."""
    out.mkdir(parents=True, exist_ok=True)
    runs = load_runs()
    table = pd.DataFrame([run_row(run) for run in runs])
    table["variant"] = pd.Categorical(table["variant"], ORDER, ordered=True)
    table = table.sort_values(["card", "variant", "seed"]).reset_index(drop=True)
    table["variant"] = table["variant"].astype(str)
    variants = variant_rows(table)
    eval_data, train_data = eval_curves(runs), training_curves(runs)

    table.to_csv(out / "runs.csv", index=False)
    variants.to_csv(out / "variants.csv", index=False)
    eval_data.to_csv(out / "eval_points.csv", index=False)
    eval_data.groupby(["card", "variant", "step"], sort=False)[["greedy", "sampled"]].mean().to_csv(
        out / "curves_eval.csv"
    )
    train_data.groupby(["card", "variant", "step"], sort=False).mean(numeric_only=True).drop(
        columns="seed"
    ).to_csv(out / "curves_training.csv")
    plots = make_plots(eval_data, train_data, out)
    infos = {card: card_info(card, out) for card in TOTAL_STEPS}
    (out / "cards.json").write_text(json.dumps(infos, indent=2) + "\n", encoding="utf-8")
    cards = "\n".join(card_markdown(card, info) for card, info in infos.items())
    (out / "tables.md").write_text(
        f"## Variants\n\n{variants_table(variants)}\n\n## Runs\n\n{runs_table(table)}\n\n"
        f"## Cards\n\n{cards}\n",
        encoding="utf-8",
    )
    print(
        f"{len(runs)} runs ({int((table['status'] == 'finished').sum())} finished); plots: {plots}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize the PPO diagnostic runs.")
    parser.add_argument("--out", type=Path, required=True, help="artifact folder to write")
    main(parser.parse_args().out)
