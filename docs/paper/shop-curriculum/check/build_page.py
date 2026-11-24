"""Build ``data.json`` and the five plots of the shop-curriculum entry from ``evidence/runs.json``.

``evidence/runs.json`` is the recount of the raw run folders (``check/collect.py``). This script
reads it, the shop cards (``experiments/benchmark/shop/tasks.json``) and the committed machines
(``graphs/*.rm`` are checked against the bundles), asserts every claim the page's prose makes, and
writes the page's data. Run ``collect.py`` first.

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/shop-curriculum/check/build_page.py
"""

import io
import json
import math
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

from src.utils import ltlf_of, pretty_ltlf

ENTRY = Path(__file__).resolve().parents[1]
ROOT = ENTRY.parents[2]
SHOP = ROOT / "experiments/benchmark/shop"
BUNDLES = "experiments/benchmark/shop/bundles/farm"
Z95 = 1.96
T95 = 4.303  # two-sided 95% t quantile with 2 degrees of freedom: 3 runs
BIN = 100_000  # steps per curve point, as in collect.py
TOTAL = 5_000_000
SIZES = (3, 5, 7)
ONEHOT = (0.99, 0.1)  # gamma and clip of ppo-onehot.yaml
SHOP_PPO = (0.995, 0.2)  # ppo-shop.yaml
PRICING = ENTRY / "evidence/notes/pricing-check.json"
# the code each suite's runs trained on, as recorded in their config.yaml (git_head)
CODE_POINTS = {
    "shop-ladder-std": "93b3ea06-dirty",
    "shop-ladder": "93b3ea06-dirty",
    "shop-ladder-noslip": "ed42365f-dirty",
    "shop-curriculum": "462cfde3",
    "shop-size": "ed42365f",
    "shop-size-std": "ed42365f",
    "shop-grow": "f1f5aefd-dirty",
    "shop-size-reward": "f1f5aefd-dirty",
}
MARKS = ("o", "D")  # a run's first and second world switch: slips or 5x5, back falls or 7x7
LABEL_GAP = 0.07  # least gap between run names at the end of the grow curves, in axis heights
GROW_STAGES = [  # the world stages of the grow cards; the card's own world (7x7) follows
    {"env_kwargs": {"area": 3}, "until": {"served": 10}},
    {"env_kwargs": {"area": 5}, "until": {"served": 10}},
]
# learned runs per rung (rung 1, rung 3) at 7x7 that the grow section states; the 3x3 FARM runs are the
# reference in a smaller world
GROW_COUNTS = {"plain": (0, 0), "grow": (1, 2), "reward": (2, 3), "small": (3, 3)}
# the only judged runs that score neither 0 nor 1, keyed by suite, card and seed: the grow and the
# no-machine run 3 of rung 1
PARTIAL_SCORES = {
    ("shop-grow", "shop-ladder-deliver-grow", "seed3"): 0.21,
    ("shop-size-reward", "shop-ladder-deliver-7x7", "seed3"): 0.22,
}

RUNGS = (
    {
        "key": "deliver",
        "name": "Rung 1, deliver",
        "tick": "Rung 1\ndeliver",
        "base": "shop-ladder-deliver",
        "graph": "rung1-deliver",
    },
    {
        "key": "order-deliver",
        "name": "Rung 3, order and deliver",
        "tick": "Rung 3\norder and deliver",
        "base": "shop-ladder-order-deliver",
        "graph": "rung3-order-deliver",
    },
)
# name -> label, palette index, suite and card of the runs, and the learned count the prose states
CONDITIONS = {
    "none": ("No curriculum", 1, "shop-ladder-std", "{base}", 0),
    "curriculum": ("Curriculum", 0, "shop-curriculum", "{base}-curriculum", 3),
    "back": ("Curriculum, back falls", 2, "shop-curriculum", "{base}-curriculum-back", 0),
}

# == Palette of the artifact pages (figures skill, plotly/example.py), as in the fall-rate entry ==
PALETTE = {
    "light": {
        "text": "#1d1d1f",
        "line": "#5b5b66",
        "series": ["#2f5bd3", "#d96f00", "#1f7a4d", "#b3261e", "#b03a9a", "#1b7f8c"],
    },
    "dark": {
        "text": "#ececf0",
        "line": "#b9b9c4",
        "series": ["#8fb0ff", "#ffa24d", "#5fd394", "#ff8a80", "#e58ad2", "#5ccfdc"],
    },
}


# ======================================================================================
#                                   COUNTS AND LOOKUPS
# ======================================================================================
def wilson(successes: int, trials: int) -> tuple[float, float]:
    """95% Wilson score interval of a proportion."""
    share = successes / trials
    scale = 1 + Z95**2 / trials
    center = (share + Z95**2 / (2 * trials)) / scale
    half = Z95 / scale * math.sqrt(share * (1 - share) / trials + Z95**2 / (4 * trials**2))
    return max(0.0, center - half), min(1.0, center + half)


def group(runs: list[dict], suite: str, card: str) -> list[dict]:
    """The 3 finished runs of one card in one suite, in launch order."""
    found = sorted(
        (r for r in runs if (r["suite"], r["card"]) == (suite, card)), key=lambda r: r["run"]
    )
    assert len(found) == 3, (suite, card, len(found))
    return found


def condition_runs(runs: list[dict], rung: dict, cond: str) -> list[dict]:
    _, _, suite, card, _ = CONDITIONS[cond]
    return group(runs, suite, card.format(base=rung["base"]))


def size_group(runs: list[dict], rung: dict, size: int, suite: str = "shop-size") -> list[dict]:
    """The 3 plain runs of a rung at one floor size; the shop preset unless ``suite`` says otherwise."""
    return group(runs, suite, f"{rung['base']}-{size}x{size}")


def grow_runs(runs: list[dict], rung: dict) -> list[dict]:
    return group(runs, "shop-grow", f"{rung['base']}-grow")


def reward_runs(runs: list[dict], rung: dict) -> list[dict]:
    """The 3 runs of a rung trained on the shop's own reward, with no reward machine, at 7x7."""
    return group(runs, "shop-size-reward", f"{rung['base']}-7x7")


def both_rungs(found_per_rung: list[list[dict]]) -> list[dict]:
    return [run for found in found_per_rung for run in found]


def learned(run: dict) -> bool:
    """All 100 test episodes pass the judge; orders served do not enter."""
    return run["mean_judged_success"] == 1.0


def count(found: list[dict]) -> int:
    return sum(learned(r) for r in found)


def fraction(successes: int, trials: int) -> str:
    """``k of n [low, high]`` with the 95% Wilson interval."""
    low, high = wilson(successes, trials)
    return f"{successes} of {trials} [{low:.0%}, {high:.0%}]"


def runs_fraction(successes: int, trials: int) -> str:
    """``k of n runs [low, high]`` with the 95% Wilson interval."""
    low, high = wilson(successes, trials)
    return f"{successes} of {trials} runs [{low:.0%}, {high:.0%}]"


def result(found: list[dict]) -> str:
    return fraction(count(found), len(found))


def served(found: list[dict]) -> str:
    """Mean orders served per test episode, over the runs."""
    return f"{sum(r['mean_served'] for r in found) / len(found):.1f}"


def per_run(found: list[dict], key: str = "mean_served") -> str:
    return " / ".join(f"{r[key]:g}" for r in found)


def end_mean(found: list[dict]) -> str:
    """Mean orders served per training episode in the last 1M steps, with a 95% t interval over runs.

    The lower bound is cut at 0, because orders served cannot be negative.
    """
    values = np.array([r["ends"]["last_1m"]["mean_env_return"] for r in found])
    half = T95 * values.std(ddof=1) / math.sqrt(len(values))
    return f"{values.mean():.1f} [{max(0.0, values.mean() - half):.1f}, {values.mean() + half:.1f}]"


def millions(step: float) -> str:
    return f"{step / 1e6:.2f}M"


def pooled(runs: list[dict], cond: str) -> list[dict]:
    return [r for rung in RUNGS for r in condition_runs(runs, rung, cond)]


def number_of_states(text: str) -> int:
    line = next(x for x in text.splitlines() if x.startswith("STATES:"))
    return len(line.split(","))


# ======================================================================================
#                                          CHECKS
# ======================================================================================
def settings(run: dict) -> dict:
    """A run's learner settings, steps and machine: everything but the world."""
    return {k: v for k, v in run["config"].items() if k not in ("env_stages", "env_kwargs")}


def check_condition(runs: list[dict], cards: dict, rung: dict, cond: str) -> None:
    """One headline condition: same settings as the plain runs, its card's world, its stated count."""
    base_id = rung["base"]
    bundle = f"{BUNDLES}/{base_id}"
    _, _, _, card_pattern, expected = CONDITIONS[cond]
    card_id = card_pattern.format(base=base_id)
    card = cards[card_id]
    assert (card["task"], card["expect"]) == (cards[base_id]["task"], cards[base_id]["expect"])
    assert card_id == base_id or card["bundle_of"] == base_id, card_id
    found = condition_runs(runs, rung, cond)
    assert count(found) == expected, (card_id, count(found))
    reference = settings(condition_runs(runs, rung, "none")[0])
    assert (reference["gamma"], reference["ppo_clip_coef"]) == ONEHOT
    assert reference["bundle"] == bundle and reference["total_timesteps"] == TOTAL
    for run in found:
        assert settings(run) == reference, run["run"]
        assert run["config"]["env_kwargs"] == card["env"]["env_kwargs"], run["run"]
        assert run["config"]["env_stages"] == card["env"].get("env_stages"), run["run"]
        assert run["judge_card"] == card_id and run["judge_bundle"] == bundle, run["run"]
        assert run["steps"] >= TOTAL


def check_other_runs(runs: list[dict], cards: dict, rung: dict) -> None:
    """The other learner's plain runs and the size runs: same machine, only the learner or the room differs."""
    base_id = rung["base"]
    base = cards[base_id]
    bundle = f"{BUNDLES}/{base_id}"
    for run in group(runs, "shop-ladder", base_id):
        assert (run["config"]["gamma"], run["config"]["ppo_clip_coef"]) == SHOP_PPO, run["run"]
        assert run["config"]["bundle"] == bundle, run["run"]
    for size in SIZES:
        card = cards[f"{base_id}-{size}x{size}"]
        assert card["bundle_of"] == base_id
        assert (card["task"], card["expect"]) == (base["task"], base["expect"])
        assert card["env"]["env_kwargs"] == base["env"]["env_kwargs"] | {"area": size}
        for suite in ("shop-size", "shop-size-std"):
            for run in group(runs, suite, card["id"]):
                assert run["config"]["env_kwargs"] == card["env"]["env_kwargs"], run["run"]
                assert run["config"]["bundle"] == bundle, run["run"]


def check_stages(runs: list[dict]) -> None:
    """The world switches of the curriculum runs: how many, no breaks, serving before the first one."""
    for cond in ("curriculum", "back"):
        for run in pooled(runs, cond):
            assert len(run["stages"]) == (1 if cond == "curriculum" else 2), run["run"]
            assert run["world_stage"] == run["world_final_stage"] == len(run["stages"]), run["run"]
            assert run["hard_breaks"] == run["soft_breaks"] == 0, run["run"]
            # back runs end idle, which leaves the Response clause open
            assert (run["hard_open"] == 0) == (cond == "curriculum"), run["run"]
            # The first switch is the step where the last 100 episodes first average 10 orders, and
            # serving began before it.
            first_switch = run["stages"][0]["step"]
            assert run["first_window_mean_10_step"] == first_switch, run["run"]
            assert run["first_serve_step"] < first_switch, run["run"]


def check_code_points(runs: list[dict]) -> None:
    """Every run trained on the commit the page names for its suite; the env pays 1 per order served."""
    for run in runs:
        assert run["git_head"] == CODE_POINTS[run["suite"]], (run["suite"], run["git_head"])
        assert run["env_return_is_served"], run["run"]  # the training curves count orders served


def check_judged_scores(runs: list[dict]) -> None:
    """Every judged run scores 0 or 1 except two, so any pass bar above 0.22 gives the same counts."""
    partial = {
        (r["suite"], r["card"], r["run"].split("-")[0]): r["mean_judged_success"]
        for r in runs
        if r["mean_judged_success"] not in (0.0, 1.0)
    }
    assert partial == PARTIAL_SCORES, partial


def check_runs(runs: list[dict], cards: dict) -> None:
    """Fail unless the runs differ only in the world, as the page says, and the counts hold."""
    for rung in RUNGS:
        for cond in CONDITIONS:
            check_condition(runs, cards, rung, cond)
        check_other_runs(runs, cards, rung)
    check_judged_scores(runs)
    check_stages(runs)
    check_code_points(runs)


# ======================================================================================
#                                          PLOTS
# ======================================================================================
def series(found: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Bin centers (million steps) and one row of mean served per training episode per run."""
    starts = [[s for s, _, _ in r["curve"] if s < TOTAL] for r in found]
    assert all(s == starts[0] for s in starts), "runs have different bins"
    x = (np.array(starts[0]) + BIN / 2) / 1e6
    y = np.array([[m for s, _, m in r["curve"] if s < TOTAL] for r in found])
    return x, y


def style_axes(ax, colors: dict) -> None:
    ax.grid(color=colors["line"], alpha=0.25)
    ax.set_axisbelow(True)
    ax.set_facecolor("none")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def headline_bars(runs: list[dict]) -> list[tuple[str, int, list[list[dict]]]]:
    """Label, palette index and the runs of each rung, for each headline condition."""
    return [
        (label, color, [condition_runs(runs, r, cond) for r in RUNGS])
        for cond, (label, color, *_) in CONDITIONS.items()
    ]


def grow_bars(runs: list[dict]) -> list[tuple[str, int, list[list[dict]]]]:
    """The same for the 7x7 comparison of the grow section, and FARM in a 3x3 shop as a reference."""
    return [
        ("FARM, no curriculum, 7x7", 1, [size_group(runs, r, 7) for r in RUNGS]),
        ("FARM, world grows to 7x7", 4, [grow_runs(runs, r) for r in RUNGS]),
        ("No reward machine, 7x7", 5, [reward_runs(runs, r) for r in RUNGS]),
        ("FARM, no curriculum, 3x3 shop", 2, [size_group(runs, r, 3) for r in RUNGS]),
    ]


def draw_learned(
    bars: list[tuple[str, int, list[list[dict]]]], theme: str, step: float = 0.28
) -> Figure:
    """Learned runs per rung and condition, with Wilson intervals; ``step`` spaces the bars of a rung."""
    colors = PALETTE[theme]
    fig = Figure(figsize=(5.4, 3.9), layout="constrained")
    ax = fig.subplots()
    for j, (label, color, per_rung) in enumerate(bars):
        points = [(count(found), len(found)) for found in per_rung]
        shares = [k / n for k, n in points]
        bounds = [wilson(k, n) for k, n in points]
        xs = [i + (j - (len(bars) - 1) / 2) * step for i in range(len(RUNGS))]
        ax.bar(
            xs,
            shares,
            width=step - 0.02,
            color=colors["series"][color],
            label=label,
            yerr=[
                [max(0.0, s - low) for s, (low, _) in zip(shares, bounds, strict=True)],
                [max(0.0, high - s) for s, (_, high) in zip(shares, bounds, strict=True)],
            ],
            error_kw={"ecolor": colors["text"], "capsize": 2.5, "elinewidth": 1},
        )
        # a dot in the condition's colour, so a 0 of 3 (no bar) still shows which condition it is
        ax.plot(xs, shares, "o", color=colors["series"][color], mec=colors["text"], ms=6, zorder=4)
        for x, (k, n), (_, high) in zip(xs, points, bounds, strict=True):
            ax.text(x, high + 0.025, f"{k} of {n}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(range(len(RUNGS)), [r["tick"] for r in RUNGS])
    ax.set_ylim(0, 1.17)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_ylabel("Share of the 3 runs that learned")
    style_axes(ax, colors)
    ax.grid(axis="x", visible=False)
    fig.legend(
        *ax.get_legend_handles_labels(),
        loc="outside upper center",
        ncols=2,
        frameon=False,
        fontsize=8.5,
    )
    return fig


def draw_curves(runs: list[dict], theme: str, which: str) -> Figure:
    """Orders served per training episode against steps, one line per run, one panel per rung.

    A marker on a run's own line shows where its world changed: a circle for slips turning on, a
    diamond for back falls turning on. No mean line: the runs switch at different steps.
    """
    colors = PALETTE[theme]
    fig = Figure(figsize=(5.4, 6.6), layout="constrained")
    axes = fig.subplots(len(RUNGS), 1, sharex=True)
    for ax, rung in zip(axes, RUNGS, strict=True):
        top = 1.0
        for cond in ("none", which):
            _, color, *_ = CONDITIONS[cond]
            found = condition_runs(runs, rung, cond)
            x, y = series(found)
            ax.plot(
                x,
                y.T,
                color=colors["series"][color],
                lw=1.3,
                ls=(0, (4, 2)) if cond == "none" else "-",
                zorder=2 if cond == "none" else 3,
            )
            top = max(top, y.max())
            if cond != which:
                continue
            for run, line in zip(found, y, strict=True):
                for stage, stage_row in enumerate(run["stages"]):
                    step = stage_row["step"] / 1e6
                    ax.plot(
                        step,
                        float(np.interp(step, x, line)),
                        marker=MARKS[stage],
                        ms=7,
                        mfc=colors["series"][color],
                        mec=colors["text"],
                        mew=1,
                        ls="none",
                        zorder=5,
                    )
        ax.set_ylim(-0.04 * top, 1.06 * top)
        ax.set_xlim(0, TOTAL / 1e6)
        ax.set_title(rung["name"], loc="left", fontsize=10.5)
        ax.set_ylabel("Orders served per training episode")
        style_axes(ax, colors)
    axes[-1].set_xlabel("Training steps (millions)")
    label, color, *_ = CONDITIONS[which]
    series_color = colors["series"][color]
    handles = [
        Line2D([], [], color=colors["series"][CONDITIONS["none"][1]], lw=1.3, ls=(0, (4, 2))),
        Line2D([], [], color=series_color, lw=1.3),
        Line2D([], [], marker="o", ms=7, mfc=series_color, mec=colors["text"], ls="none"),
    ]
    names = ["No curriculum, one line per run", f"{label}, one line per run", "slips turn on"]
    if which == "back":
        handles.append(
            Line2D([], [], marker="D", ms=7, mfc=series_color, mec=colors["text"], ls="none")
        )
        names.append("back falls turn on")
    fig.legend(handles, names, loc="outside upper center", ncols=2, frameon=False, fontsize=8)
    return fig


def draw_grow_curves(runs: list[dict], theme: str) -> Figure:
    """Orders served per training episode against steps, one line per grow run, one panel per rung.

    A circle marks where a run's world grew from 3x3 to 5x5, a diamond where it grew to 7x7. Left of
    a marker the world is smaller, so levels on the two sides of it are not comparable. Each line
    is named "run 1" to "run 3" at its right end, as in the page's table.
    """
    colors = PALETTE[theme]
    color = colors["series"][4]
    fig = Figure(figsize=(5.4, 6.6), layout="constrained")
    axes = fig.subplots(len(RUNGS), 1, sharex=True)
    for ax, rung in zip(axes, RUNGS, strict=True):
        found = grow_runs(runs, rung)
        x, y = series(found)
        top = max(1.0, y.max())
        ax.axhline(10, color=colors["line"], lw=1, ls=":", zorder=1)
        ax.plot(x, y.T, color=color, lw=1.3, zorder=3)
        label_y = -np.inf
        # lines that end together get names stacked LABEL_GAP apart
        for end, number in sorted((float(line[-1]), n) for n, line in enumerate(y, start=1)):
            label_y = max(end, label_y + LABEL_GAP * top)
            ax.annotate(
                f"run {number}",
                xy=(1, label_y),
                xycoords=ax.get_yaxis_transform(),
                xytext=(3, 0),
                textcoords="offset points",
                va="center",
                fontsize=8,
                annotation_clip=False,
            )
        for run, line in zip(found, y, strict=True):
            for stage, stage_row in enumerate(run["stages"]):
                step = stage_row["step"] / 1e6
                ax.plot(
                    step,
                    float(np.interp(step, x, line)),
                    marker=MARKS[stage],
                    ms=7,
                    mfc=color,
                    mec=colors["text"],
                    mew=1,
                    ls="none",
                    zorder=5,
                )
        room = max(1.06 * top, label_y + 0.03 * top)  # also room for the stacked names
        ax.set_ylim(-0.04 * top, room)
        ax.set_xlim(0, TOTAL / 1e6)
        ax.set_title(rung["name"], loc="left", fontsize=10.5)
        ax.set_ylabel("Orders served per training episode")
        style_axes(ax, colors)
    axes[-1].set_xlabel("Training steps (millions)")
    handles = [
        Line2D([], [], color=color, lw=1.3),
        Line2D([], [], color=colors["line"], lw=1, ls=":"),
        Line2D([], [], marker="o", ms=7, mfc=color, mec=colors["text"], ls="none"),
        Line2D([], [], marker="D", ms=7, mfc=color, mec=colors["text"], ls="none"),
    ]
    names = [
        "World grows, one line per run",
        "10 orders: the grow rule",
        "grows to 5x5",
        "grows to 7x7",
    ]
    fig.legend(handles, names, loc="outside upper center", ncols=2, frameon=False, fontsize=8)
    return fig


def save_svgs(name: str, draw) -> None:
    """Write the light and the dark SVG of one plot."""
    (ENTRY / "plots").mkdir(exist_ok=True)
    for theme, suffix in (("light", ""), ("dark", "-dark")):
        colors = PALETTE[theme]
        style = {
            "svg.fonttype": "none",  # real text: small files, the page's font
            "svg.hashsalt": "shop-curriculum",  # the same ids on every build
            "font.family": "sans-serif",
            "font.size": 10,
            "text.color": colors["text"],
            "axes.edgecolor": colors["line"],
            "axes.labelcolor": colors["text"],
            "xtick.color": colors["text"],
            "ytick.color": colors["text"],
        }
        svg = io.StringIO()
        with mpl.rc_context(style):
            draw(theme).savefig(svg, format="svg", transparent=True, metadata={"Date": None})
        # matplotlib ends path lines with a space; the repo's trailing-whitespace hook would edit it
        lines = svg.getvalue().splitlines()
        (ENTRY / f"plots/{name}{suffix}.svg").write_text(
            "\n".join(line.rstrip() for line in lines) + "\n"
        )


# ======================================================================================
#                                  TASKS, LTL, MACHINES
# ======================================================================================
def machine(rung: dict) -> tuple[str, int, int, str]:
    """Machine text, number of states, number of transitions and the well, after checking the copy."""
    text = (ENTRY / f"graphs/{rung['graph']}.rm").read_text()
    assert text == (SHOP / "bundles/farm" / rung["base"] / "reward_machine.txt").read_text(), rung[
        "graph"
    ]
    body = text.split("TRANSITION_FUNCTION:")[1].split("REWARD_FUNCTION:")[0]
    well = (
        next(x for x in text.splitlines() if x.startswith("REJECTING_STATES:"))
        .split(":")[1]
        .strip()
    )
    return (
        text,
        number_of_states(text),
        sum(line.startswith("(") for line in body.splitlines()),
        well,
    )


def short(rung: dict) -> str:
    """``Rung 1`` of ``Rung 1, deliver``."""
    return rung["name"].split(",")[0]


def see_tasks() -> dict:
    return {
        "type": "text",
        "text": "Task text, LTL and machine of each rung: see [the two tasks](#task).",
    }


def task_section(cards: dict) -> dict:
    blocks: list[dict] = [
        {
            "type": "text",
            "text": "Two task cards of the shop ladder, shown once here. Every other card on this page is a copy "
            "of one of them in another world (slips that start later, back falls, a smaller floor): the same "
            "task text, the same clauses and the same machine, so no machine was generated again.",
        }
    ]
    for rung in RUNGS:
        card = cards[rung["base"]]
        text, states, transitions, well = machine(rung)
        clauses = [
            [f"{t}({', '.join(names)}) {priority}", f"`{pretty_ltlf(ltlf_of(t, list(names)))}`"]
            for t, names, priority in card["expect"]
        ]
        blocks += [
            {"type": "text", "heading": rung["name"], "text": f"**Task:** {card['task']}"},
            {"type": "table", "columns": ["Clause (the card's answer)", "LTLf"], "rows": clauses},
            {
                "type": "figure",
                "src": f"graphs/{rung['graph']}.html",
                "height": 490,
                "title": f"{rung['name']}: the FARM machine",
                "caption": f"`{rung['base']}`: {states} states, {transitions} transitions. `{well}` (red) is the "
                "well: reaching it pays -10. Drag a state, click an edge for its cases.",
            },
            {
                "type": "details",
                "items": [{"title": "RM text", "blocks": [{"type": "code", "text": text}]}],
            },
        ]
    return {"id": "task", "title": "The two tasks, their LTL and their machines", "blocks": blocks}


# ======================================================================================
#                                  EXTRA CHECKS FOR THE TEXT
# ======================================================================================
def noslip_run(runs: list[dict]) -> dict:
    return group_one(runs, "shop-ladder-noslip", RUNGS[0]["base"])


def check_noslip(runs: list[dict]) -> None:
    """The no-slip run plays the curriculum's first world: same machine, learner and world.

    Only the step budget differs (1M against 5M).
    """
    noslip = noslip_run(runs)
    reference = {k: v for k, v in settings(noslip).items() if k != "total_timesteps"}
    for run in condition_runs(runs, RUNGS[0], "curriculum"):
        assert {k: v for k, v in settings(run).items() if k != "total_timesteps"} == reference
        first_world = run["config"]["env_kwargs"] | run["config"]["env_stages"][0]["env_kwargs"]
        assert first_world == noslip["config"]["env_kwargs"], run["run"]
        assert (
            run["config"]["total_timesteps"] == TOTAL
            and noslip["config"]["total_timesteps"] == 1_000_000
        )
    assert noslip["config"]["env_stages"] is None


def size_runs(runs: list[dict]) -> tuple[list[dict], list[dict]]:
    """The size runs over both rungs and both learner presets: the 3x3 ones and the 5x5 and 7x7 ones."""
    found = [
        r
        for suite in ("shop-size", "shop-size-std")
        for rung in RUNGS
        for n in SIZES
        for r in group(runs, suite, f"{rung['base']}-{n}x{n}")
    ]
    small = [r for r in found if r["card"].endswith("-3x3")]
    large = [r for r in found if not r["card"].endswith("-3x3")]
    assert (count(small), len(small), count(large), len(large)) == (12, 12, 0, 24)
    return small, large


def check_grow(runs: list[dict], cards: dict) -> None:
    """The grow and the no-reward-machine runs differ from the plain 7x7 runs only as the page says."""
    for i, rung in enumerate(RUNGS):
        base_id = rung["base"]
        card, card7 = cards[f"{base_id}-grow"], cards[f"{base_id}-7x7"]
        assert card["bundle_of"] == base_id
        assert (card["task"], card["expect"]) == (cards[base_id]["task"], cards[base_id]["expect"])
        assert card["env"]["env_kwargs"] == card7["env"]["env_kwargs"]
        assert card["env"]["env_stages"] == GROW_STAGES
        # the plain 7x7 runs of the shop preset give the learner, machine and steps to compare with
        reference = settings(size_group(runs, rung, 7)[0])
        assert (reference["gamma"], reference["ppo_clip_coef"]) == SHOP_PPO
        for run in grow_runs(runs, rung):
            assert settings(run) == reference, run["run"]
            assert run["config"]["env_kwargs"] == card7["env"]["env_kwargs"], run["run"]
            assert run["config"]["env_stages"] == GROW_STAGES, run["run"]
            assert run["judge_card"] == card["id"], run["run"]
            assert run["judge_bundle"] == f"{BUNDLES}/{base_id}", run["run"]
            assert run["world_final_stage"] == 2 and run["world_stage"] == len(run["stages"])
            assert [s["stage"] for s in run["stages"]] == [1, 2][: len(run["stages"])], run["run"]
            assert all(s["served"] >= 10 for s in run["stages"]), run["run"]  # the switch rule
            assert (run["hard_breaks"], run["soft_breaks"]) == (0, 0) and run["steps"] >= TOTAL
        for run in reward_runs(runs, rung):
            assert run["arm"] == "no-rm" and run["config"]["bundle"] is None, run["run"]
            assert (run["config"]["gamma"], run["config"]["ppo_clip_coef"]) == ONEHOT, run["run"]
            assert run["config"]["env_kwargs"] == card7["env"]["env_kwargs"], run["run"]
            assert run["judge_card"] == card7["id"] and run["steps"] >= TOTAL, run["run"]
        found = {
            "plain": size_group(runs, rung, 7),
            "grow": grow_runs(runs, rung),
            "reward": reward_runs(runs, rung),
            "small": size_group(runs, rung, 3),
        }
        for name, expected in GROW_COUNTS.items():
            assert count(found[name]) == expected[i], (name, base_id, count(found[name]))


# ======================================================================================
#                                          PAGE
# ======================================================================================
def figure(name: str, title: str, alt: str, caption: str) -> dict:
    return {
        "type": "figure",
        "src": f"plots/{name}.svg",
        "dark": f"plots/{name}-dark.svg",
        "title": title,
        "alt": alt,
        "source": "check/build_page.py",
        "caption": caption,
    }


def fold(title: str, blocks: list[dict]) -> dict:
    """A block collapsed by default; nothing is dropped."""
    return {"type": "details", "items": [{"title": title, "blocks": blocks}]}


def setting_section() -> dict:
    return {
        "id": "setting",
        "title": "The setting in three lines",
        "blocks": [
            {
                "type": "list",
                "items": [
                    "**The shop.** A worker agent fetches food from the pantry and gives it to clients who come in. "
                    "The food can slip out of its hands, and the task says to pick it up on the very next move.",
                    "**FARM.** A language model reads the task text and writes a reward machine: a small state "
                    "machine that pays the agent as the task's clauses are kept or broken. Breaking a hard clause "
                    "sends the machine to its *well*, a dead-end state that charges -10. The agent then learns "
                    "from that pay with PPO, a standard reinforcement-learning method.",
                    "**A rung** is one task of the shop ladder, a series of tasks that grow harder. This page uses "
                    "two: rung 1, *deliver* (serve every client), and rung 3, *order and deliver* (take the "
                    "client's order first).",
                ],
            }
        ],
    }


def summary_section(runs: list[dict]) -> dict:
    rows = [
        [
            f"{rung['name']}: {CONDITIONS[cond][0].lower()}",
            result(f),
            f"{served(f)} ({per_run(f)})",
            end_mean(f),
        ]
        for rung in RUNGS
        for cond in CONDITIONS
        for f in [condition_runs(runs, rung, cond)]
    ]
    low_none, high_none = wilson(0, 6)
    low_cur, _ = wilson(6, 6)
    plain_shop = [r for rung in RUNGS for r in group(runs, "shop-ladder", rung["base"])]
    assert count(plain_shop) == 0
    noslip = noslip_run(runs)
    assert (noslip["judged_passed"], noslip["mean_served"]) == (100, 18.85)
    small, large = size_runs(runs)
    grown = both_rungs([grow_runs(runs, rung) for rung in RUNGS])
    low_grown, high_grown = wilson(count(grown), len(grown))
    plain_7x7 = both_rungs([size_group(runs, rung, 7) for rung in RUNGS])
    reward_7x7 = both_rungs([reward_runs(runs, rung) for rung in RUNGS])
    return {
        "id": "summary",
        "title": "In short",
        "blocks": [
            {
                "type": "list",
                "items": [
                    "**The plain runs never serve.** In the full 8x8 shop, 3 training runs per card learned "
                    f"nothing on either rung ({result(condition_runs(runs, RUNGS[0], 'none'))} on rung 1, "
                    f"{result(condition_runs(runs, RUNGS[1], 'none'))} on rung 3), and again 0 of 3 on both rungs "
                    "with the second learner preset. In the standard-preset runs, more than 99.8% of the training "
                    "episodes of the last million steps end in one machine state, with nothing served.",
                    "**A curriculum makes them serve.** Same machine, same learner, same 5M steps. The run starts "
                    "with no food slips and turns slips on once the last 100 training episodes average 10 orders "
                    "served per episode. "
                    f"Rung 1: {result(condition_runs(runs, RUNGS[0], 'curriculum'))}, "
                    f"{served(condition_runs(runs, RUNGS[0], 'curriculum'))} orders per test episode. Rung 3: "
                    f"{result(condition_runs(runs, RUNGS[1], 'curriculum'))}, "
                    f"{served(condition_runs(runs, RUNGS[1], 'curriculum'))} orders per test episode. Over both "
                    "rungs that is "
                    f"{count(pooled(runs, 'curriculum'))} of 6 against {count(pooled(runs, 'none'))} of 6 "
                    f"([{low_cur:.0%}, 100%] against [{low_none:.0%}, {high_none:.0%}]).",
                    "**The machine's pay makes idling the trap.** The first pickup of every episode always slips, "
                    "and a scripted server that misses one slip falls into the -10 well and scores -12 on rung 1, "
                    "while idling scores -1. Two runs back this: one 1M-step run in a world without slips serves "
                    f"{noslip['mean_served']} orders per test episode (a different world from the 18.7 above, which "
                    "has slips, and a single run), and the curriculum learns under the same pay once serving is "
                    "learned before the slips come in. It is the best-supported cause, not a proof.",
                    "**With back falls, no run serves, and the machine prefers idling.** When a quarter of the "
                    "slips land the food behind the agent, nothing can pick it up on the very next move. "
                    f"{result(condition_runs(runs, RUNGS[0], 'back'))} and "
                    f"{result(condition_runs(runs, RUNGS[1], 'back'))} learned; the machine pays idling -1.0 "
                    "against -9.3 for its scripted solving plan on rung 1 (-2.0 against -9.0 on rung 3).",
                    "**Smaller shops: only 3x3 learns.** On both rungs, with either learner preset, 3x3 learned "
                    f"in {runs_fraction(count(small), len(small))}; 5x5 and 7x7 in "
                    f"{runs_fraction(count(large), len(large))}.",
                    f"**A shop that grows inside one run: {count(grown)} of 6 learn at 7x7 "
                    f"[{low_grown:.0%}, {high_grown:.0%}].** A run starts in a "
                    "3x3 shop and grows to 5x5, then 7x7, each time the last 100 episodes average 10 orders "
                    f"served; {sum(r['world_stage'] == 2 for r in grown)} of 6 runs reached 7x7. Plain FARM at 7x7 "
                    f"with the same learner: {result(plain_7x7)}. The shop's own reward with no machine: "
                    f"{result(reward_7x7)}, so the machine's runs are not ahead of it here. See "
                    "[growing the shop](#grow).",
                ],
            },
            figure(
                "learned-runs",
                "Runs that learned to serve",
                "Bars of the share of 3 training runs that learned, per rung and condition, with 95% Wilson "
                "intervals.",
                "Only the curriculum learns: 3 of 3 runs on each rung, against 0 of 3 for plain runs and for the "
                "back-fall curriculum. Whiskers are 95% Wilson intervals (the range of shares the 3 runs "
                "allow); with 3 runs a 3 of 3 still spans 44% to 100%, and the two rungs together (6 of 6 "
                "against 0 of 6) separate cleanly.",
            ),
            see_tasks(),
            {
                "type": "table",
                "heading": "Learned runs, 8x8 shop",
                "columns": [
                    "Rung and condition",
                    "Learned runs [95% CI]",
                    "Served per test episode: mean (runs 1 / 2 / 3)",
                    "Served per training episode, last 1M steps: mean [95% interval over runs]",
                ],
                "rows": rows,
            },
        ],
    }


def group_one(runs: list[dict], suite: str, card: str) -> dict:
    found = [r for r in runs if (r["suite"], r["card"]) == (suite, card)]
    assert len(found) == 1, (suite, card)
    return found[0]


def setup_section() -> dict:
    definition = (
        "**Learned.** All 100 test episodes pass the judge; the number of orders served does not enter. "
        "Every judged run scores 0 or 1 except two: rung 1, run 3 of the "
        f"grow runs ({PARTIAL_SCORES['shop-grow', 'shop-ladder-deliver-grow', 'seed3']}) and rung 1, run 3 of the "
        f"no-machine runs ({PARTIAL_SCORES['shop-size-reward', 'shop-ladder-deliver-7x7', 'seed3']}). Any pass bar "
        f"above {max(PARTIAL_SCORES.values())} gives the same counts."
    )
    return {
        "id": "setup",
        "title": "What was run",
        "blocks": [
            {
                "type": "table",
                "columns": ["Condition", "World during training", "Learner preset and cards"],
                "rows": [
                    [
                        "No curriculum",
                        "The card's own world from step 0: food slips by the card's default chance, and the first "
                        "pickup of every episode always slips.",
                        "`shop-ladder-std` (standard preset) and `shop-ladder` (shop preset); cards "
                        "`shop-ladder-deliver`, `shop-ladder-order-deliver`",
                    ],
                    [
                        "Curriculum",
                        "No slips until the last 100 finished training episodes average 10 orders served per "
                        "episode; then the card's own world.",
                        "`shop-curriculum` (standard preset); cards `...-curriculum`",
                    ],
                    [
                        "Curriculum, back falls",
                        "Three worlds: no slips; slips with no back falls, until the last 100 episodes average 10 "
                        "orders served and 90% of falls are caught on the next move; then slips with 25% back "
                        "falls (the food lands behind the agent).",
                        "`shop-curriculum` (standard preset); cards `...-curriculum-back`",
                    ],
                    [
                        "No slips throughout",
                        "No slips for the whole run; 1 run, 1M steps. Judged in that no-slip world.",
                        "`shop-ladder-noslip` (standard preset); card `shop-ladder-deliver`",
                    ],
                    [
                        "Smaller shop",
                        "The card's own world on a 3x3, 5x5 or 7x7 floor instead of 8x8.",
                        "`shop-size` (shop preset) and `shop-size-std` (standard preset); cards `...-3x3`, "
                        "`-5x5`, `-7x7`",
                    ],
                    [
                        "World grows",
                        "A 3x3 shop until the last 100 finished training episodes average 10 orders served, then "
                        "5x5 until the same holds, then 7x7, the world the test and the judge play.",
                        "`shop-grow` (shop preset); cards `...-grow`",
                    ],
                    [
                        "No reward machine",
                        "The 7x7 shop's own reward (one per order served), no machine; judged on the same clauses.",
                        "`shop-size-reward`; cards `...-7x7`",
                    ],
                ],
            },
            {
                "type": "list",
                "items": [
                    "**Learner presets.** PPO ran with one of two presets: the *standard* preset (`ppo-onehot`: "
                    "gamma, the discount, 0.99; clip, the size limit of one update, 0.1) or the *shop* preset "
                    "(`ppo-shop`: gamma 0.995, clip 0.2). Every run lasts 5M steps (1M for the no-slip run), and "
                    "the agent sees the machine's current state as a one-hot input.",
                    "**Same machine in every condition.** Each copy card reuses its base card's machine, so the "
                    "machine, the learner preset and the 5M steps are those of the plain runs. The page's build "
                    "stops unless each curriculum, back-fall and size run has the learner settings of its plain "
                    "run; only the world differs.",
                    "**3 runs per card.** Each run is one agent trained from scratch.",
                    definition,
                    "**The judge** is the test: the trained agent plays 100 episodes in the card's own final world "
                    "(slips on, and back falls on the back cards), and the judge checks each episode against the "
                    "task's clauses.",
                    '**Left out.** The siren rung (rung 2, which adds "turn the siren off") and the other ladder '
                    "rungs: each has its own task and machine, and the curriculum was not run on them.",
                    "**Code.** Plain runs trained at commit `93b3ea06` (dirty tree), the no-slip run at `ed42365f` "
                    "(dirty tree), the size runs at `ed42365f`, and the curriculum and back-fall runs at "
                    "`462cfde3` (`merge: shop world curriculum and back falls`). The grow runs and the "
                    "no-reward-machine runs trained at `f1f5aefd` (dirty tree), which contains the size "
                    "curriculum's merge `919c166d`. The build checks each run's recorded commit. The runs file is "
                    "`experiments/benchmark/shop/runs-curriculum.yaml` (grow runs: `runs-grow.yaml`; no machine: "
                    "`runs-size-no-rm.yaml`); the stage rule is the list of world stages (`env_stages`) on each "
                    "curriculum or grow card.",
                ],
            },
        ],
    }


def nocurriculum_section(runs: list[dict]) -> dict:
    rows, early, late, shares, states = [], [], [], [], {}
    for rung in RUNGS:
        for number, run in enumerate(condition_runs(runs, rung, "none"), start=1):
            first, last = run["ends"]["first_100k"], run["ends"]["last_1m"]
            early.append(first["well_share"] * 100)
            late.append(last["well_share"] * 100)
            shares.append(last["commonest_end_share"])
            states.setdefault(rung["key"], set()).add(last["commonest_end_state"])
            rows.append(
                [
                    f"{short(rung)}, run {number}",
                    f"{first['well_share']:.1%} / {last['well_share']:.1%}",
                    f"`{last['commonest_end_state']}`, {last['commonest_end_share']:.1%}",
                    f"{run['mean_served']:g}; {run['final_eval_rm_return']:g}",
                ]
            )
    assert min(early) > 2 and max(early) < 8 and max(late) <= 0.2, (early, late)
    assert min(shares) >= 0.998
    assert states == {"deliver": {"u2"}, "order-deliver": {"u1"}}, states
    noslip = noslip_run(runs)
    rung1_switches = [
        r["first_window_mean_10_step"] for r in condition_runs(runs, RUNGS[0], "curriculum")
    ]
    return {
        "id": "plain",
        "title": "Why the plain runs never serve",
        "blocks": [
            see_tasks(),
            {
                "type": "text",
                "text": "Every plain run (no curriculum, 8x8 shop, standard preset) ends the same way. Early on, "
                f"{min(early):g}% to {max(early):g}% of training episodes end in the well, because an agent that "
                "touches food misses the first slip. By the last million steps at most "
                f"{max(late):g}% do, and more than 99.8% end in one machine state with nothing served: `u2` on "
                "rung 1 (a client arrived) and `u1` on rung 3 (the order is taken). The diagnosis note's traces "
                "of the earlier shop-preset runs on rung 1 show the agents never pick food up. The shop-preset "
                "runs on both cards serve 0 as well (see every run).",
            },
            fold(
                "Where the plain runs' training episodes end, per run",
                [
                    {
                        "type": "table",
                        "columns": [
                            "Run",
                            "Episodes ending in the well: first 100k / last 1M steps",
                            "Commonest end state, last 1M steps",
                            "Served per test episode; RM return of the final evaluation",
                        ],
                        "rows": rows,
                    }
                ],
            ),
            fold(
                "Scripted players on rung 1: what the machine pays (copied from the plan notes, not recounted)",
                [
                    {
                        "type": "table",
                        "columns": ["Player on rung 1", "Machine return", "Discounted return"],
                        "rows": [
                            ["Solving worker: catches every slip on the next move", "0", "-0.38"],
                            ["Catches a slip with chance 0.5", "-12", "-8.5"],
                            ["Catches a slip with chance 1/7 (random pickups)", "-12", "-10.4"],
                            ["Never catches a slip", "-12", "-10.8"],
                            [
                                "Uniform random play (8 of 30 episodes end in the well)",
                                "-3.9",
                                "-2.37",
                            ],
                            ["Idle", "-1", "-0.94"],
                        ],
                    }
                ],
            ),
            {
                "type": "list",
                "items": [
                    "**Fear valley.** The first pickup of every episode always slips (about 7.5 slips per episode), "
                    "and a missed catch is the -10 well. A server must catch nearly every slip before serving "
                    "beats idling; a learner that has not found the catch reflex is better off never touching "
                    "food.",
                    "**Little pay for serving.** A served order refunds the charge of the client's arrival, so the "
                    "whole gain from idling to perfect play is +1 per episode (+0.57 discounted), and about 0.04 "
                    "discounted per extra order. The diagnosis note lists a third cause, that a legal serve is "
                    "rare by chance (a difficulty of the learning itself), and rules out the training setup, the "
                    "labeling and the language-model machine.",
                    f"**No slips, one run.** With slips off for the whole run (1M steps, standard preset), the "
                    f"agent serves {noslip['mean_served']} orders per test episode and passes "
                    f"{noslip['judged_passed']} of 100, judged in its own world without slips. That is a different "
                    "world from the curriculum's final one (slips on) and a single run, so it is not comparable "
                    f"with the 18.7 of the curriculum. Its training episodes first average 10 orders at "
                    f"{millions(noslip['first_window_mean_10_step'])}; the rung 1 curriculum runs take "
                    f"{millions(min(rung1_switches))} to {millions(max(rung1_switches))} (see the curriculum "
                    "section).",
                    "Source: `evidence/notes/ladder-noserve.md`. Its numbers are copied, not recounted from the run "
                    "folders; the run tables are recounted.",
                ],
            },
        ],
    }


def curriculum_section(runs: list[dict]) -> dict:
    switches = [run["stages"][0]["step"] for run in pooled(runs, "curriculum")]
    first_serves = [run["first_serve_step"] for run in pooled(runs, "curriculum")]
    rows = []
    for rung in RUNGS:
        for number, run in enumerate(condition_runs(runs, rung, "curriculum"), start=1):
            stage = run["stages"][0]
            rows.append(
                [
                    f"{short(rung)}, run {number}",
                    millions(run["first_serve_step"]),
                    f"{millions(stage['step'])} (the last 100 episodes averaged {stage['served']:g})",
                    f"{run['judged_passed']} of 100; {run['mean_served']:g}",
                ]
            )
    noslip = noslip_run(runs)
    rung1 = condition_runs(runs, RUNGS[0], "curriculum")
    like_rows = [
        [
            "No-slip run (1 run, 1M steps)",
            millions(noslip["first_serve_step"]),
            millions(noslip["first_window_mean_10_step"]),
        ]
    ] + [
        [
            f"Curriculum, rung 1, run {n}, before its switch (5M steps)",
            millions(r["first_serve_step"]),
            millions(r["first_window_mean_10_step"]),
        ]
        for n, r in enumerate(rung1, start=1)
    ]
    serve_ratio = [r["first_serve_step"] / noslip["first_serve_step"] for r in rung1]
    mean_ratio = [
        r["first_window_mean_10_step"] / noslip["first_window_mean_10_step"] for r in rung1
    ]
    return {
        "id": "curriculum",
        "title": "The curriculum learns",
        "blocks": [
            see_tasks(),
            {
                "type": "list",
                "items": [
                    "**6 of 6 runs learned**, all with 100 of 100 test episodes passed, no broken hard or soft "
                    "clause and no hard clause left open, in the full slip world.",
                    f"**Each run switched at its own step** ({millions(min(switches))} to {millions(max(switches))}): "
                    "the rule waits until the last 100 training episodes average 10 orders served per episode. "
                    f"Serving had started earlier, from {millions(min(first_serves))} to "
                    f"{millions(max(first_serves))}.",
                    "**After the switch the agents keep serving.** Over the last 1M steps they serve "
                    f"{end_mean(rung1)} orders per training episode on rung 1 and "
                    f"{end_mean(condition_runs(runs, RUNGS[1], 'curriculum'))} on rung 3 (mean over 3 runs "
                    "[95% interval over runs]; the agent still explores in training).",
                ],
            },
            figure(
                "curves",
                "Orders served per training episode, curriculum runs",
                "Two panels, one per rung, with one line per run of the orders served per training episode "
                "against training steps, for the curriculum runs and the plain runs.",
                "Plain runs stay at 0 for all 5M steps. Each curriculum run starts serving with no slips; the "
                "marker on its line shows where its slips turn on, and it keeps serving afterwards. One line per "
                "run, because the runs switch at different steps and a mean would blur them. Left of a run's "
                "marker its world has no slips, so those points are not comparable with the ones to its right. "
                "Each point is a 100,000-step average, so a marker can sit below the 10 orders the switch rule "
                "needs.",
            ),
            {
                "type": "table",
                "columns": [
                    "Run",
                    "First order served at step",
                    "Slips turn on at step",
                    "Test episodes passed; served per test episode",
                ],
                "rows": rows,
            },
            {
                "type": "text",
                "heading": "The same world, with and without the curriculum",
                "text": "The curriculum's first stage is the world of the no-slip run: the build checks that the "
                "machine, the learner preset and the world settings match, and only the step budget differs "
                "(5M against 1M). Yet the no-slip run served its first order at "
                f"{millions(noslip['first_serve_step'])} and reached an average of 10 at "
                f"{millions(noslip['first_window_mean_10_step'])}, while the three rung 1 curriculum runs took "
                f"{min(serve_ratio):.0f} to {max(serve_ratio):.0f} times as long for the first order and "
                f"{min(mean_ratio):.0f} to {max(mean_ratio):.0f} times as long for the average. The cause is not "
                "explained. The only setting tied to the step budget is the learning-rate decay (`ppo_anneal_lr`, "
                "`app/src/arm_fm/ppo.py:774`), and it gives the 1M run a lower rate at equal steps, so it does "
                "not favour that run. With 1 no-slip run against 3 curriculum runs, run-to-run variation cannot "
                "be ruled out.",
            },
            {
                "type": "table",
                "columns": [
                    "Run",
                    "First order served at step",
                    "Last 100 episodes first average 10 at step",
                ],
                "rows": like_rows,
            },
        ],
    }


def back_after(run: dict) -> tuple[int, float]:
    """Steps from the back-fall switch until orders served per training episode stay below 0.5.

    Returns the steps to the end of the first 100,000-step stretch from which the value stays below
    0.5, and the largest value from there on.
    """
    switch = run["stages"][1]["step"]
    after = next(s for s, _, m in run["curve"] if s + BIN > switch and m < 0.5)
    later = [m for s, _, m in run["curve"] if s >= after]
    assert max(later) < 0.5, run["run"]
    return after + BIN - switch, max(later)


def price_rows(pricing: dict) -> list[list[str]]:
    rows = []
    for rung in RUNGS:
        for world, suffix in (
            ("no back falls", "-curriculum"),
            ("25% back falls", "-curriculum-back"),
        ):
            entry = pricing[f"{rung['base']}{suffix}"]
            for policy, name in (
                ("solve", "solving plan"),
                ("one", "serves one order, then stops"),
                ("idle", "idle"),
            ):
                p = entry[policy]
                rows.append(
                    [
                        f"{short(rung)}, {world}",
                        name,
                        f"{p['served']:g}",
                        f"{p['plain']:g} / {p['discounted']:g}",
                    ]
                )
    return rows


def check_pricing(pricing: dict) -> None:
    """The claims the prose makes about the copied pricing numbers."""
    for rung in RUNGS:  # with back falls, idle beats both priced plans
        entry = pricing[f"{rung['base']}-curriculum-back"]
        assert entry["idle"]["plain"] > entry["one"]["plain"] > entry["solve"]["plain"]
        assert (
            entry["idle"]["discounted"] > entry["one"]["discounted"] > entry["solve"]["discounted"]
        )
    one, three = (pricing[f"{rung['base']}-curriculum-back"] for rung in RUNGS)
    assert (one["solve"]["plain"], three["solve"]["plain"]) == (-9.3, -9.0)
    assert (one["idle"]["plain"], three["idle"]["plain"]) == (-1.0, -2.0)
    assert (
        one["solve"]["served"],
        pricing["shop-ladder-deliver-curriculum"]["solve"]["served"],
    ) == (5.5, 12.125)


def back_section(runs: list[dict]) -> dict:
    rows, gaps, largest, caught, tails = [], [], [], [], []
    for rung in RUNGS:
        for number, run in enumerate(condition_runs(runs, rung, "back"), start=1):
            first, second = run["stages"]
            late = run["ends"]["last_1m"]
            gap, top = back_after(run)
            gaps.append(gap)
            largest.append(top)
            caught.append(second["caught"])
            tails.append(late["mean_env_return"])
            assert late["commonest_end_share"] > 0.99 and run["final_eval_rm_return"] == -1.0
            rows.append(
                [
                    f"{short(rung)}, run {number}",
                    f"{millions(first['step'])} / {millions(second['step'])}",
                    f"{second['caught']:.1%}",
                    f"{run['mean_served']:g}; `{late['commonest_end_state']}`, "
                    f"{late['commonest_end_share']:.1%}; {run['final_eval_rm_return']:g}",
                ]
            )
    within = math.ceil(max(gaps) / 50_000) / 20  # in millions of steps, to the next 0.05M
    assert max(gaps) <= within * 1e6 and max(largest) < 0.5 and max(tails) < 0.01
    pricing = json.loads(PRICING.read_text())
    check_pricing(pricing)
    return {
        "id": "back",
        "title": "With back falls, no run serves",
        "blocks": [
            see_tasks(),
            {
                "type": "list",
                "items": [
                    "**0 of 3 on both rungs.** Every run first meets the stage rule twice: 10 orders per episode "
                    "with no slips, then 10 again with slips and "
                    f"{min(caught):.1%} to {max(caught):.1%} of falls caught on the next move. Once 25% of slips "
                    "land behind the agent, served orders per training episode drop below 0.5 within "
                    f"{within:.2f}M steps of the switch in all 6 runs and stay below it (at most "
                    f"{max(largest):.2f}); over the last 1M steps they average {max(tails):.3f} or less.",
                    "**The machine pays idling more.** A back fall cannot be caught on the next move. The scripted "
                    "solving plan misses about 22% of its falls, ends in the -10 well early (5.5 orders served "
                    "instead of 12.1 on rung 1) and scores -9.3 on rung 1 and -9.0 on rung 3, against -1.0 and "
                    "-2.0 for idle. The trained agents end where the machine pays best of the plans priced: on "
                    "rung 1 idle with a client waiting (-1.0), on rung 3 with the order taken and nothing served "
                    "(-1.0, better than idle's -2.0).",
                    "**So this is the pay, not a training failure.** Whether another pay would let a server beat "
                    "idling with back falls is not tested here. The two back cards' plan check fails by design "
                    "for the same reason.",
                ],
            },
            figure(
                "back-curves",
                "Orders served per training episode, back-fall runs",
                "Two panels, one per rung, with one line per run of the orders served per training episode "
                "against training steps, for the back-fall curriculum runs and the plain runs.",
                "Each run serves in the first worlds, then drops to about 0 soon after the diamond, where back falls "
                "start. Circle: slips turn on; diamond: back falls turn on. One line per run; each point is a "
                "100,000-step average.",
            ),
            {
                "type": "table",
                "columns": [
                    "Run",
                    "Slips on / back falls on at step",
                    "Falls caught on the next move before back falls",
                    "Served per test episode; commonest end state in the last 1M steps; RM return of the final "
                    "evaluation",
                ],
                "rows": rows,
            },
            fold(
                "What the machine pays scripted plans (copied from the plan notes, not recounted; 40 episodes)",
                [
                    {
                        "type": "table",
                        "columns": [
                            "Rung and world",
                            "Plan",
                            "Orders served",
                            "Machine return / discounted",
                        ],
                        "rows": price_rows(pricing),
                    },
                    {
                        "type": "text",
                        "text": "The pricing numbers are copied from `evidence/notes/pricing-check.json` "
                        "(`freeze-prep/shop-curriculum/` in the plan folder), not recomputed here. The discount "
                        "is 0.995; the runs used 0.99, which changes the discounted column, not the plain one.",
                    },
                ],
            ),
        ],
    }


def size_section(runs: list[dict]) -> dict:
    rows = []
    for rung in RUNGS:
        for size in (*SIZES, 8):
            if size == 8:
                found = {
                    "shop-size": group(runs, "shop-ladder", rung["base"]),
                    "shop-size-std": group(runs, "shop-ladder-std", rung["base"]),
                }
            else:
                found = {
                    s: group(runs, s, f"{rung['base']}-{size}x{size}")
                    for s in ("shop-size", "shop-size-std")
                }
            rows.append(
                [
                    f"{short(rung)}, {size}x{size}",
                    result(found["shop-size"]),
                    result(found["shop-size-std"]),
                    f"{per_run(found['shop-size'])}; {per_run(found['shop-size-std'])}",
                ]
            )
    small, large = size_runs(runs)
    return {
        "id": "size",
        "title": "Smaller shops",
        "blocks": [
            see_tasks(),
            {
                "type": "text",
                "text": "The same machine and instruction in a smaller room, plain runs without a curriculum. Only "
                f"the 3x3 room learns: {runs_fraction(count(small), len(small))} over both rungs and both "
                f"learner presets, against {runs_fraction(count(large), len(large))} for 5x5 and 7x7. The 8x8 rows are "
                "the plain runs of the first table.",
            },
            {
                "type": "table",
                "columns": [
                    "Rung and floor",
                    "Shop preset: learned runs [95% CI]",
                    "Standard preset: learned runs [95% CI]",
                    "Served per test episode, runs 1 / 2 / 3 (shop preset; standard preset)",
                ],
                "rows": rows,
            },
        ],
    }


def odd_grow_run(runs: list[dict]) -> dict:
    """The one grow run that reached 7x7 and still did not learn: rung 1, run 3."""
    odd = [
        run
        for rung in RUNGS
        for run in grow_runs(runs, rung)
        if run["world_stage"] == 2 and not learned(run)
    ]
    assert len(odd) == 1 and odd[0]["card"] == f"{RUNGS[0]['base']}-grow", odd
    assert odd[0]["run"].startswith("seed3-"), odd[0]["run"]
    return odd[0]


def odd_run_blocks(runs: list[dict]) -> list[dict]:
    """What the odd run did after it reached 7x7: it serves when sampling, not under greedy play."""
    odd = odd_grow_run(runs)
    after, passed = odd["after_last_switch"], odd["judged_passed"]
    # the passing episodes are exactly the serving ones; the rest serve nothing and break no clause
    assert odd["judged_no_serve"] == 100 - passed == odd["hard_open"], odd["run"]
    assert odd["hard_breaks"] == odd["soft_breaks"] == 0
    # the other grow runs play the same with sampled and with greedy actions
    others = [r for rung in RUNGS for r in grow_runs(runs, rung) if r is not odd]
    gap = max(abs(r["final_eval_served"] - r["final_eval_sampled_served"]) for r in others)
    assert gap < 1 < odd["final_eval_sampled_served"] - odd["final_eval_served"], gap
    return [
        {
            "type": "text",
            "heading": "Rung 1, run 3: it serves in training, not in the judge's test",
            "text": "**It counts as not learned.** In training the agent picks each action at random by its learned "
            "odds; the judge always plays the most likely action. This run reached 7x7 at "
            f"{millions(after['from_step'])} steps with the same machine and learner as the others, and the two "
            "ways of picking give very different results.",
        },
        {
            "type": "list",
            "items": [
                "**Training, sampled actions.** From 7x7 on: "
                f"{after['episodes']:,} training episodes, {after['mean_env_return']:.1f} orders served per "
                f"episode, {after['no_serve_share']:.1%} of the episodes serving nothing.",
                "**The run's own evaluation at the end, 100 layouts.** Sampled actions serve "
                f"{odd['final_eval_sampled_served']:g} orders per episode; the most likely action at every step "
                f"(greedy) serves {odd['final_eval_served']:g}. For the five other grow runs the two differ by "
                f"{gap:.1f} at most.",
                "**The judge, 100 test layouts, most likely action** (`app/scripts/test_rl.py:445`, "
                f"`eval_greedy`). {passed} episodes serve ({odd['mean_served'] * 100 / passed:.1f} orders on "
                f"average) and pass; {odd['judged_no_serve']} serve nothing and leave the clause *serve every "
                "client* open at the end. No clause is broken. The run's own greedy evaluation "
                f"({odd['final_eval_served']:g}) and the judge's ({odd['mean_served']:g}) are separate draws of 100 "
                "layouts.",
                "**Not shown:** why the most likely action serves nothing in those "
                f"{odd['judged_no_serve']} layouts.",
            ],
        },
    ]


def grow_section(runs: list[dict]) -> dict:
    grow = [grow_runs(runs, rung) for rung in RUNGS]
    plain = [size_group(runs, rung, 7) for rung in RUNGS]
    plain_std = [size_group(runs, rung, 7, "shop-size-std") for rung in RUNGS]
    reward = [reward_runs(runs, rung) for rung in RUNGS]
    small = [
        size_group(runs, rung, 3, suite)
        for suite in ("shop-size", "shop-size-std")
        for rung in RUNGS
    ]
    plain_5x5 = [
        size_group(runs, rung, 5, suite)
        for suite in ("shop-size", "shop-size-std")
        for rung in RUNGS
    ]
    all_grow = both_rungs(grow)
    stalled = [
        (rung, number, run)
        for rung in RUNGS
        for number, run in enumerate(grow_runs(runs, rung), start=1)
        if run["world_stage"] == 1
    ]
    assert len(all_grow) - len(stalled) == 4 and len(stalled) == 2
    # the figure caption names run 2 of each rung
    assert [number for _, number, _ in stalled] == [2, 2]
    # the page says these pairs of intervals overlap
    k_grow, k_plain, k_reward = (count(both_rungs(x)) for x in (grow, plain, reward))
    grow_low, grow_high = wilson(k_grow, 6)
    assert wilson(k_grow, 6)[0] < wilson(k_plain, 6)[1]
    assert wilson(k_grow, 6)[1] > wilson(k_reward, 6)[0]
    assert count(both_rungs(plain_std)) == k_plain  # the standard preset repeats the plain count
    stalled_text = "; ".join(
        f"{short(rung).lower()}, run {number}, from {millions(run['stages'][0]['step'])}"
        for rung, number, run in stalled
    )
    stalled_served = " and ".join(
        f"{run['after_last_switch']['mean_env_return']:.2f}" for _, _, run in stalled
    )
    # the lead quotes the first 100 training episodes of the plain size runs
    small_floor, large_floor = size_runs(runs)
    assert all(run["first_100_served"] == 0 for run in large_floor)
    early = [run["first_100_served"] for run in small_floor]
    broken = next(run for run in both_rungs(reward) if not learned(run))
    assert broken["judged_no_serve"] == 0 and broken["mean_served"] > 0  # the page says it serves
    rows = []
    for rung_number, rung in enumerate(RUNGS):
        for label, found in (
            ("FARM, no curriculum, 7x7, shop preset", plain[rung_number]),
            ("FARM, no curriculum, 7x7, standard preset", plain_std[rung_number]),
            ("FARM, world grows to 7x7", grow[rung_number]),
            ("No reward machine, 7x7", reward[rung_number]),
            ("FARM, no curriculum, 3x3 shop, shop preset", small[rung_number]),
            ("FARM, no curriculum, 3x3 shop, standard preset", small[2 + rung_number]),
        ):
            rows.append(
                [f"{short(rung)}: {label}", result(found), f"{served(found)} ({per_run(found)})"]
            )
    switches = []
    for rung in RUNGS:
        for number, run in enumerate(grow_runs(runs, rung), start=1):
            first, *second = run["stages"]
            switches.append(
                [
                    f"{short(rung)}, run {number}",
                    f"{millions(first['step'])} ({first['served']:g})",
                    f"{millions(second[0]['step'])} ({second[0]['served']:g})"
                    if second
                    else "not reached",
                    "7x7" if second else "5x5",
                    f"{run['judged_passed']} of 100; {run['mean_served']:g}",
                ]
            )
    return {
        "id": "grow",
        "title": "Growing the shop inside one run",
        "blocks": [
            {
                "type": "text",
                "text": f"Plain FARM runs learn only in the 3x3 shop: {count(large_floor)} of {len(large_floor)} "
                "above it. A new agent acts almost at random, and in a bigger shop that serves almost nothing: "
                "over the first 100 training episodes the plain 5x5 and 7x7 runs serve 0.00 orders per episode, "
                f"the 3x3 runs {min(early):.2f} to {max(early):.2f}. Less pay to learn from is the likely reason. "
                "This section asks whether a run still learns the combined task when its shop grows inside the "
                "run, from 3x3 to 5x5 to 7x7. The task is to serve every client and pick up fallen food on the "
                "very next move; rung 3 also takes the client's order first.",
            },
            see_tasks(),
            {
                "type": "list",
                "items": [
                    f"**{count(all_grow)} of 6 runs learned in the 7x7 shop [{grow_low:.0%}, {grow_high:.0%}].** "
                    f"Rung 1: {result(grow[0])}; rung 3: "
                    f"{result(grow[1])}. Plain FARM runs at 7x7 with the same learner preset: "
                    f"{result(both_rungs(plain))} ({count(both_rungs(plain_std))} of 6 again with the standard preset). The intervals "
                    "overlap: the counts point to growth helping, but six runs per condition do not settle it.",
                    f"**{len(all_grow) - len(stalled)} of 6 runs reached 7x7.** The other two stayed in 5x5 to the "
                    f"end of their 5M steps ({stalled_text}) and served on average {stalled_served} orders per "
                    f"training episode there. The plain 5x5 runs learned {result(both_rungs(plain_5x5))} too.",
                    f"**The shop's own reward, with no machine, learned {result(both_rungs(reward))} at 7x7** with "
                    f"no growth (rung 1: {count(reward[0])} of 3; rung 3: {count(reward[1])} of 3). The machine's "
                    "runs are not ahead of it here. "
                    f"The one reward run that did not learn serves {broken['mean_served']:g} per test episode but "
                    f"breaks the pick-up clause in {broken['hard_breaks']} of its 100 test episodes.",
                    "**One run serves in training and not in the judge's test** (rung 1, run 3, "
                    "details below).",
                    f"**For reference, FARM in a 3x3 shop** learns in {result(both_rungs(small))} (both rungs, "
                    "both learner presets): the machine works when the world is small.",
                ],
            },
            figure(
                "grow-learned",
                "Runs that learned: 7x7 shop and 3x3 reference",
                "Bars of the share of 3 training runs that learned, per rung and condition at 7x7, and FARM in a "
                "3x3 shop, with 95% Wilson intervals.",
                f"Growing helps only in the counts ({k_grow} of 6 against {k_plain} of 6 for plain FARM at 7x7), the "
                f"runs with no reward machine learn {k_reward} of 6, and the intervals overlap. The 3x3 bars are the "
                "same machine in a smaller shop, as a reference. Whiskers are 95% Wilson intervals, wide with 3 runs "
                "per bar.",
            ),
            {
                "type": "table",
                "heading": "Learned runs, judged in 7x7 except the 3x3 rows",
                "columns": [
                    "Rung and condition",
                    "Learned runs [95% CI]",
                    "Served per test episode: mean (runs 1 / 2 / 3)",
                ],
                "rows": rows,
            },
            figure(
                "grow-curves",
                "Orders served per training episode, growing world",
                "Two panels, one per rung, with one line per grow run of the orders served per training episode "
                "against training steps, named run 1 to run 3 at its end, with a marker where its world grows.",
                "Two runs never get past 5x5: in each panel the line of run 2 falls to about 0 after its circle "
                "and stays there. The circle is where a run's world grows from 3x3 to 5x5 and the diamond where "
                "it grows to 7x7; the dotted line is the 10 orders the rule asks for. Most markers sit below it "
                "because each point is a 100,000-step average, while the rule reads the last 100 episodes. Left "
                "of a marker the world is smaller, so levels on the two sides of a marker are not comparable.",
            ),
            {
                "type": "table",
                "columns": [
                    "Run",
                    "Switch to 5x5: step (served)",
                    "Switch to 7x7: step (served)",
                    "World at the end",
                    "Test episodes passed in 7x7; served per test episode",
                ],
                "rows": switches,
            },
            {
                "type": "text",
                "text": "Served is the mean orders served per episode over the last 100 training episodes before the "
                "switch.",
            },
            *odd_run_blocks(runs),
        ],
    }


def all_runs_section(runs: list[dict], cards: dict) -> dict:
    names = {rung["base"]: rung["name"] for rung in RUNGS}
    rows = []
    for run in sorted(runs, key=lambda r: (r["suite"], r["card"], r["run"])):
        base = cards[run["card"]].get("bundle_of", run["card"])
        rows.append(
            [
                f"`{run['suite']}`",
                f"`{run['card']}`",
                names[base],
                f"{run['config']['gamma']:g} / {run['config']['ppo_clip_coef']:g}",
                run["run"].split("-", 1)[1],
                f"{run['steps']:,}",
                f"{run['judged_passed']} of 100",
                f"{run['mean_served']:g}",
                "yes" if learned(run) else "no",
            ]
        )
    return {
        "id": "runs",
        "title": "Every run",
        "intro": f"{len(rows)} finished runs of the suites recounted in `evidence/runs.json`. The Run folder column "
        "is the time part of the folder's name under `outputs/runs/bench__<suite>__<card>__<arm>__ppo/` "
        "(arm `farm`, or `no-rm` for `shop-size-reward`).",
        "collapsed": True,
        "blocks": [
            {
                "type": "table",
                "columns": [
                    "Suite",
                    "Card",
                    "Task",
                    "Gamma / clip",
                    "Run folder",
                    "Steps",
                    "Test episodes passed",
                    "Served per test episode",
                    "Learned",
                ],
                "rows": rows,
            }
        ],
    }


def closing_sections() -> list[dict]:
    small_size = "12 of 12 at 3x3, 0 of 24 above it"
    return [
        {
            "id": "checks",
            "title": "Checks",
            "collapsed": True,
            "blocks": [
                {
                    "type": "list",
                    "items": [
                        "**Recount from raw folders.** `check/collect.py` reads every `judge.json` (100 test episodes "
                        "each) and recounts passes and served orders from the per-episode records; both match the "
                        "stored means. Folders with a dot in their name are skipped, and only the cards of the two "
                        "rungs are kept.",
                        "**Machines.** `graphs/rung1-deliver.rm` and `graphs/rung3-order-deliver.rm` equal the "
                        "committed bundles' `reward_machine.txt`; every headline run trained on, and was judged "
                        "with, that bundle.",
                        "**Runs differ only in the world.** The build asserts that curriculum, back-fall and size "
                        "runs have the plain runs' learner settings, steps and machine, that each run's world "
                        "settings equal its card's, and that the no-slip run's world equals the curriculum's "
                        "first stage.",
                        f"**Counts and code.** The build asserts every learned count the text states (3 of 3 and "
                        f"0 of 3 per rung and condition, {small_size}; at 7x7 the grow, no-machine and plain runs "
                        "per rung), that every judged run scores 0 or 1 except the two the page names, the commit "
                        "each suite trained on, and the bounds the back-fall text quotes (below 0.5 orders per "
                        "episode within the stated steps).",
                        "**Grow and no-machine runs.** The build asserts that the grow cards copy the 7x7 card's task, "
                        "clauses and world with the two stages, that each grow run has the learner settings, machine "
                        "and steps of the plain 7x7 run, that every switch happened at 10 or more orders over the "
                        "last 100 episodes, that the no-machine runs have no bundle and the 7x7 card's world, and "
                        "that the plain 5x5 and 7x7 runs served nothing in their first 100 training episodes "
                        "(`first_100_served` in `evidence/runs.json`).",
                    ],
                }
            ],
        },
        {
            "id": "limits",
            "title": "Limits",
            "collapsed": True,
            "blocks": [
                {
                    "type": "list",
                    "items": [
                        "3 runs per card, so one rung alone gives 3 of 3 [44%, 100%] against 0 of 3 [0%, 56%], "
                        "which overlap; the two rungs pooled (6 of 6 against 0 of 6) do not.",
                        "The curriculum switch rule (10 orders over 100 episodes) was set once and not tuned; the "
                        "runs show it works, not that it is the best rule.",
                        "The back-fall result says what this machine pays, not that no pay could teach a server. "
                        "The pricing and diagnosis numbers are copied from plan notes, not recomputed.",
                        "The no-slip check is 1 run of 1M steps, and why it serves earlier than the curriculum's "
                        "first stage is not explained.",
                        "The grow section has 3 runs per card, 6 per condition, so its intervals are wide: grow "
                        "(3 of 6) is not separated from plain 7x7 (0 of 6) or from no machine (5 of 6). The grow "
                        "rule (3x3, then 5x5, then 7x7, each switch at 10 orders over 100 episodes) was set once "
                        "and not tuned.",
                        "Rung 1, run 3 counts as not learned because the judge plays the most likely action; it "
                        "serves when sampling, and why its most likely action serves nothing is not shown.",
                        "The plain runs and the no-slip run trained on a dirty working tree; the commits above are "
                        "the nearest recorded code.",
                        "The plots are static SVG, not Plotly: plotly.js embedded is 4.8 MB, over the repository's "
                        "1 MB file limit. The machines are interactive.",
                    ],
                }
            ],
        },
        {
            "id": "files",
            "title": "Files and rerun",
            "blocks": [
                {
                    "type": "list",
                    "items": [
                        "This page is `index.html`, built from `data.json`. `check/` has `collect.py` (the recount) "
                        "and `build_page.py` (the page and its plots); `evidence/` the recount and copies of three "
                        "plan notes; `graphs/` the two machines; `plots/` the five figures, light and dark.",
                        "The README note in `docs/paper/README.md` holds the detail.",
                    ],
                },
                {
                    "type": "code",
                    "text": "# from the repository root, RM_RL_env active; fill.py is the agent-artifacts skill's script\n"
                    "python -I docs/paper/shop-curriculum/check/collect.py\n"
                    "PYTHONPATH=app python -W ignore docs/paper/shop-curriculum/check/build_page.py\n"
                    "python3 ~/.claude/skills/agent-artifacts/scripts/fill.py \\\n"
                    "  docs/paper/shop-curriculum/data.json docs/paper/shop-curriculum/index.html",
                },
            ],
        },
    ]


def build() -> dict:
    data = json.loads((ENTRY / "evidence/runs.json").read_text())
    runs = data["runs"]
    assert not data["skipped_without_judge"], data["skipped_without_judge"]
    cards = {card["id"]: card for card in json.loads((SHOP / "tasks.json").read_text())["cards"]}
    check_runs(runs, cards)
    check_noslip(runs)
    check_grow(runs, cards)
    save_svgs("learned-runs", lambda theme: draw_learned(headline_bars(runs), theme))
    save_svgs("curves", lambda theme: draw_curves(runs, theme, "curriculum"))
    save_svgs("back-curves", lambda theme: draw_curves(runs, theme, "back"))
    save_svgs("grow-learned", lambda theme: draw_learned(grow_bars(runs), theme, step=0.21))
    save_svgs("grow-curves", lambda theme: draw_grow_curves(runs, theme))
    return {
        "eyebrow": "Paper entry · shop ladder curriculum · 2026-11-23",
        "title": "Teaching the shop task: slips turned on later, a shop that grows",
        "subtitle": "In the full 8x8 shop, the FARM machine for serving clients never learned to serve (0 of 3 "
        "training runs per card). The same machine learned it in 3 of 3 runs when a run started with no food "
        "slips and turned them on once the last 100 training episodes averaged 10 orders served per episode. "
        "With a quarter of slips landing behind the agent, no run serves, and the machine itself pays idling "
        "more. A shop that grows from 3x3 to 7x7 inside one run learns in 3 of 6 runs, against 0 of 6 for "
        "plain FARM at 7x7 and 5 of 6 with no reward machine.",
        "sections": [
            setting_section(),
            summary_section(runs),
            task_section(cards),
            setup_section(),
            nocurriculum_section(runs),
            curriculum_section(runs),
            back_section(runs),
            size_section(runs),
            grow_section(runs),
            all_runs_section(runs, cards),
            *closing_sections(),
        ],
    }


def main() -> None:
    out = ENTRY / "data.json"
    out.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
