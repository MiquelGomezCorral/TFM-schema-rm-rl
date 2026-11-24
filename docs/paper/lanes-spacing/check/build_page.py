"""Build ``data.json``, the figure and the machine graphs of the lanes-spacing entry.

``evidence/runs.json`` is the recount of the raw run folders (``check/collect.py``; run it first).
This script reads it and the cards, asserts every claim the page's prose makes, copies the two
committed machines (and the kill-two machines of FARM and ARM-FM, and the absence card's) to
``graphs/`` and draws them with the repository renderer, draws the figure (static SVG, light and
dark) and writes the page's data. Three groups of runs are compared on the two cards: FARM, FARM
with the world's kill reward added, and no reward machine; ARM-FM appears on the kill-two card only.

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/lanes-spacing/check/build_page.py
"""

import io
import json
import math
import re
import textwrap
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import NamedTuple

import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

from scripts.render_rm import render_file
from src.utils import ltlf_of, pretty_ltlf

ENTRY = Path(__file__).resolve().parents[1]
ROOT = ENTRY.parents[2]
BENCH = ROOT / "experiments/benchmark"
BUNDLES = "experiments/benchmark/forcing/bundles/farm"
ARM_FM_FORCING = "experiments/benchmark/forcing/bundles/arm-fm"  # the two main cards: no machine
TEMPLATES = "experiments/benchmark/templates/bundles"
ARM_FM_KILL_TWO = f"{TEMPLATES}/arm-fm/tpl-existence-two-5-nogoal"
PLAN_CHECK_REASON = "plan-check-failed: solve-s1: ends the episode before the agent acts"
T95 = 4.303  # two-sided 95% t quantile with 2 degrees of freedom: 3 runs
EPISODES = 100
MAX_STEPS = 300  # the episode length of the world
SPACINGS = (4, 2, 1)  # lane spacing; 4 is the counted card
SPACING_TICK = {4: "spacing 4\ncounted card", 2: "spacing 2", 1: "spacing 1\ntouching"}
LEFT_OUT = ("tpl-absence-soft-1-nogoal", "tpl-existence-two-5-nogoal")
# card id -> short name and the one line each figure panel carries
CARDS = {
    "lanes-guard": ("Guard", "keep zombies out of the top lane"),
    "lanes-rules": ("Rules", "the same, plus two soft rules"),
}
FIG_WIDTH = 3.7  # inches: 355 px, so the SVG shows at 1:1 on a 390 px phone
FONT_PT = 8.25  # 11 px at that 1:1 size
# arm -> label, palette index, reward source recorded in every run's config.yaml; the order is the
# bar order in the figure
ARMS = {
    "farm": ("FARM", 0, "rm"),
    "farm-both": ("FARM + kill reward", 2, "both"),
    "no-rm": ("No reward machine", 1, "env"),
}
MACHINE_ARMS = ("farm", "farm-both")  # the arms that train on the card's committed machine
# the methods of the left-out cards' table: ARM-FM ran there only
LEFT_OUT_ARMS = {"farm": "FARM", "arm-fm": "ARM-FM", "no-rm": "No reward machine"}
# the code each group of runs trained on, as recorded in their config.yaml (git_head)
CODE_POINTS = {
    ("farm", 4, "lanes-guard"): "809dfe3f-dirty",
    ("farm", 4, "lanes-rules"): "809dfe3f-dirty",
    ("farm", 2, "lanes-guard"): "ed42365f-dirty",
    ("farm", 2, "lanes-rules"): "ed42365f-dirty",
    ("farm", 1, "lanes-guard"): "462cfde3-dirty",
    ("farm", 1, "lanes-rules"): "919c166d-dirty",
    ("no-rm", 4, "lanes-guard"): "68b904da-dirty",
    ("no-rm", 4, "lanes-rules"): "68b904da-dirty",
    ("no-rm", 2, "lanes-guard"): "5f9674ea-dirty",
    ("no-rm", 2, "lanes-rules"): "5f9674ea-dirty",
    ("no-rm", 1, "lanes-guard"): "5f9674ea-dirty",
    ("no-rm", 1, "lanes-rules"): "5f9674ea-dirty",
    **{("farm-both", s, c): "f1f5aefd-dirty" for s in SPACINGS for c in CARDS},
}
# the code the ARM-FM runs of the kill-two card trained on, per spacing
ARM_FM_CODE = {4: "e6c3acba-dirty", 2: "f1f5aefd-dirty"}
# the pay of a top-lane breach in each committed machine, read back from its text in machine()
TOP_PAY = {"lanes-guard": "-10", "lanes-rules": "-96.0959"}
# the comparisons the text states: every FARM run above every no-RM run in all but one (the same
# holds with the kill reward added); the t-intervals of FARM leave a gap of a point or more in two
# and meet at whole percents in one; those of FARM + kill reward against no reward machine leave
# a gap in two (asserted in check_claims)
NOT_ALL_ABOVE = {("lanes-rules", 4)}
INTERVALS_APART = {("lanes-guard", 2), ("lanes-guard", 1)}
INTERVALS_MEET = {("lanes-rules", 2)}
BOTH_INTERVALS_APART = {("lanes-guard", 2), ("lanes-rules", 1)}

# == Palette of the artifact pages (figures skill, plotly/example.py), as in the shop entry ==
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
class Cell(NamedTuple):
    """The judged success of the 3 runs of one card, spacing and method."""

    runs: list[dict]
    values: list[float]
    mean: float
    low: float  # lower end of the 95% t-interval, cut at 0
    high: float  # upper end, cut at 1


def group(runs: list[dict], card: str, spacing: int, arm: str) -> list[dict]:
    """The 3 finished runs of one card, spacing and method, in run order."""
    found = sorted(
        (r for r in runs if (r["card"], r["spacing"], r["arm"]) == (card, spacing, arm)),
        key=lambda r: r["index"],
    )
    assert [r["index"] for r in found] == [1, 2, 3], (card, spacing, arm)
    return found


def cell(found: list[dict]) -> Cell:
    """Mean judged success over the runs with its 95% t-interval, cut to 0 and 1."""
    values = [r["mean_judged_success"] for r in found]
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
    half = T95 * sd / math.sqrt(len(values))
    return Cell(found, values, mean, max(0.0, mean - half), min(1.0, mean + half))


def fixed(value: float, digits: int = 1) -> str:
    """``value`` to ``digits`` decimals, half up: 8.95 shows as 9.0, as 1.35 shows as 1.4.

    Python's ``format`` rounds the binary float, which sits below 8.95 and above 1.35. The values
    here are counts over 100 episodes, so their shortest decimal form is exact.
    """
    return str(Decimal(repr(value)).quantize(Decimal(1).scaleb(-digits), ROUND_HALF_UP))


def pct(share: float) -> str:
    return fixed(100 * share, 0) + "%"


def runs_pct(c: Cell) -> str:
    return " / ".join(pct(v) for v in c.values)


def mean_pct(c: Cell) -> str:
    return f"{pct(c.mean)} [{pct(c.low)}, {pct(c.high)}]"


def per_episode(found: list[dict], event: str) -> list[float]:
    """Events per test episode of each run, counted from the saved step labels."""
    return [r["events_total"][event] / EPISODES for r in found]


def run_values(values: list[float], digits: int = 1) -> str:
    return " / ".join(fixed(v, digits) for v in values)


def span(values: list[float]) -> str:
    """``low to high`` of per-episode values, one decimal; one number when they round alike."""
    low, high = fixed(min(values)), fixed(max(values))
    return low if low == high else f"{low} to {high}"


def all_cells(runs: list[dict]) -> dict[tuple[str, int, str], Cell]:
    return {
        (card, spacing, arm): cell(group(runs, card, spacing, arm))
        for card in CARDS
        for spacing in SPACINGS
        for arm in ARMS
    }


def above_all(cells: dict, card: str, spacing: int, arm: str = "farm") -> bool:
    """Every run of a machine arm scores above every no-reward-machine run."""
    return min(cells[card, spacing, arm].values) > max(cells[card, spacing, "no-rm"].values)


def apart(cells: dict, card: str, spacing: int, arm: str = "farm") -> float:
    """Points between the arm's interval low end and the no-RM interval's high end (positive: apart)."""
    return 100 * (cells[card, spacing, arm].low - cells[card, spacing, "no-rm"].high)


def lower(values: list[float], than: list[float]) -> bool:
    """Every value is below every value of the other group."""
    return all(v < w for v in values for w in than)


# ======================================================================================
#                                          CHECKS
# ======================================================================================
def check_cards() -> dict:
    """The spacing cards copy the counted cards; return the counted ones by id."""
    forcing = {c["id"]: c for c in json.loads((BENCH / "forcing/tasks.json").read_text())["cards"]}
    copies = {
        c["id"]: c for c in json.loads((BENCH / "lanes-spacing/tasks.json").read_text())["cards"]
    }
    for card_id in CARDS:
        counted = forcing[card_id]
        assert counted["env"]["env_kwargs"] == {} and counted["train"], card_id
        for spacing in SPACINGS[1:]:
            copy = copies[f"{card_id}-spacing{spacing}"]
            assert copy["bundle_of"] == f"forcing/{card_id}", copy["id"]
            assert (copy["task"], copy["expect"]) == (counted["task"], counted["expect"]), copy[
                "id"
            ]
            assert copy["env"]["env_kwargs"] == {"lane_spacing": spacing}, copy["id"]
    return {card_id: forcing[card_id] for card_id in CARDS}


def check_run(run: dict, settings: dict) -> None:
    """One run: its method's reward source, machine, world, steps and code point."""
    card, spacing, arm = run["card"], run["spacing"], run["arm"]
    machine_arm = arm in MACHINE_ARMS
    assert run["reward_source"] == ARMS[arm][2], run["run"]
    assert run["bundle"] == (f"{BUNDLES}/{card}" if machine_arm else None), run["run"]
    assert run["judge_bundle"] == (f"{BUNDLES}/{card}" if machine_arm else None), run["run"]
    assert run["judge_card"] == run["card_id"], run["run"]
    # a time-limit pay exists only inside a machine: FARM sets 0, the default -5 is idle without one
    assert run["time_limit_penalty"] == (0.0 if machine_arm else -5.0), run["run"]
    assert run["env_kwargs"] == ({} if spacing == 4 else {"lane_spacing": spacing}), run["run"]
    assert run["git_head"] == CODE_POINTS[arm, spacing, card], run["run"]
    assert run["device"] == ("cpu" if arm == "farm" and spacing == 4 else "cuda"), run["run"]
    assert run["steps"] >= settings["total_timesteps"], run["run"]


def check_pairs(runs: list[dict]) -> None:
    """A FARM + kill reward run differs from the FARM run of the same index only in its reward source.

    Same card, world, machine, time-limit pay and number of steps; the other learner settings are
    equal in all runs of the entry (``collect.py`` stops otherwise). The code point and the device
    are listed on the page, not here.
    """
    for card in CARDS:
        for spacing in SPACINGS:
            for a, b in zip(
                group(runs, card, spacing, "farm"),
                group(runs, card, spacing, "farm-both"),
                strict=True,
            ):
                keys = ("index", "card_id", "env_kwargs", "bundle", "time_limit_penalty", "steps")
                assert [a[k] for k in keys] == [b[k] for k in keys], (a["run"], b["run"])
                assert (a["reward_source"], b["reward_source"]) == ("rm", "both"), b["run"]


def check_events(runs: list[dict]) -> None:
    """The judge's verdicts equal the trace counts, and a FARM episode ends at its first breach."""
    for run in runs:
        top = run["episodes_with_event"]["top_breach"]
        assert EPISODES - run["judged_passed"] == top, run["run"]
        if run["arm"] in MACHINE_ARMS:
            assert run["episodes_ending_on_top_breach"] == top, run["run"]
        else:  # a no-reward-machine episode has no machine to end it early
            assert run["mean_length"] == MAX_STEPS, run["run"]
        if run["arm"] == "farm":
            assert run["episodes_with_event"]["side_breach"] == EPISODES, run["run"]
    # a no-reward-machine agent ignores the task text: both cards judge the same three agents
    for spacing in SPACINGS:
        guard = group(runs, "lanes-guard", spacing, "no-rm")
        rules = group(runs, "lanes-rules", spacing, "no-rm")
        for a, b in zip(guard, rules, strict=True):
            assert (a["run"], a["trained_in"]) == (b["run"], b["trained_in"])
            assert (a["judged_passed"], a["events_total"]) == (
                b["judged_passed"],
                b["events_total"],
            )
            assert a["episodes_with_event"] == b["episodes_with_event"]


def check_claims(runs: list[dict], cells: dict) -> None:
    """Every comparison and count the page's prose states."""
    for card in CARDS:
        for spacing in SPACINGS:
            farm, plain = cells[card, spacing, "farm"], cells[card, spacing, "no-rm"]
            assert farm.mean > plain.mean, (card, spacing)
            assert above_all(cells, card, spacing) == ((card, spacing) not in NOT_ALL_ABOVE)
            gap = apart(
                cells, card, spacing
            )  # under a point it shows as touching in whole percents
            assert (gap >= 1) == ((card, spacing) in INTERVALS_APART), (card, spacing)
            assert (0 <= gap < 1) == ((card, spacing) in INTERVALS_MEET), (card, spacing)
            if (card, spacing) in INTERVALS_MEET:
                assert pct(farm.low) == pct(plain.high) == "83%"
    farm_runs = [r for r in runs if r["arm"] == "farm"]
    assert len(farm_runs) == 18
    good = [r for r in farm_runs if r["mean_judged_success"] >= 0.85]
    assert len(good) == 17 and [r["mean_judged_success"] for r in farm_runs if r not in good] == [
        0.36
    ]
    assert min(cells["lanes-rules", 4, "farm"].values) == 0.36  # the one weak run is on this cell
    assert len({r["steps"] for r in runs}) == 1


def side_and_kills(runs: list[dict], card: str, spacing: int, arm: str) -> tuple[list, list]:
    """Side-lane breaches and kills per episode of the 3 runs of one cell."""
    found = group(runs, card, spacing, arm)
    return per_episode(found, "side_breach"), per_episode(found, "zombie_killed")


def kill_reward_bound(cells: dict) -> int:
    """Whole points that bound FARM + kill reward's distance from FARM's mean, rules at 4 apart."""
    _, rules = CARDS
    gaps = [
        100 * abs(cells[card, spacing, "farm-both"].mean - cells[card, spacing, "farm"].mean)
        for card in CARDS
        for spacing in SPACINGS
        if (card, spacing) != (rules, 4)
    ]
    return math.ceil(round(max(gaps), 6))


def check_kill_reward_claims(runs: list[dict], cells: dict) -> None:
    """Every comparison of the list "What adding the world's kill reward to FARM changes"."""
    guard, rules = CARDS
    bound = kill_reward_bound(cells)
    for card in CARDS:
        for spacing in SPACINGS:
            both, farm = cells[card, spacing, "farm-both"], cells[card, spacing, "farm"]
            # same ordering against no reward machine as FARM, apart from the rules card at spacing 4
            assert above_all(cells, card, spacing, "farm-both") == (
                (card, spacing) not in NOT_ALL_ABOVE
            )
            gap = apart(cells, card, spacing, "farm-both")
            assert (gap >= 1) == ((card, spacing) in BOTH_INTERVALS_APART), (card, spacing)
            assert both.low <= farm.high and farm.low <= both.high, (card, spacing)
            # the means (unrounded): within the bound everywhere but the rules card at spacing 4
            distance = 100 * abs(both.mean - farm.mean)
            assert (distance <= bound) == ((card, spacing) != (rules, 4)), (card, spacing, distance)
    # the rules card at spacing 4: two of the 3 runs fail every test episode and end early
    low = [r for r in group(runs, rules, 4, "farm-both") if r["mean_judged_success"] == 0.0]
    assert len(low) == 2 and all(r["episodes_with_event"]["top_breach"] == EPISODES for r in low)
    assert all(r["mean_length"] < 130 and r["events_total"]["zombie_killed"] < 150 for r in low)
    assert sorted(round(r["mean_length"]) for r in low) == [80, 129]  # the Limits bullet
    # the Limits bullet: with the kill reward, runs still breach the side lanes in 52 to 100 episodes
    breached = [r["episodes_with_event"]["side_breach"] for r in runs if r["arm"] == "farm-both"]
    assert (min(breached), max(breached)) == (52, 100)
    # the Limits bullet: the guard card's kill-reward episodes average at least this many steps
    assert (
        min(r["mean_length"] for r in runs if r["arm"] == "farm-both" and r["card"] == guard) > 285
    )
    # the guard card: fewer side-lane breaches and more kills than FARM at every spacing, still
    # more breaches and fewer kills than no reward machine
    for spacing in SPACINGS:
        side_b, kills_b = side_and_kills(runs, guard, spacing, "farm-both")
        side_f, kills_f = side_and_kills(runs, guard, spacing, "farm")
        side_n, kills_n = side_and_kills(runs, guard, spacing, "no-rm")
        assert lower(side_b, side_f) and lower(kills_f, kills_b), spacing
        assert lower(side_n, side_b) and lower(kills_b, kills_n), spacing
    # the rules card: no change at spacing 2; two of the 3 runs fewer at spacing 1, the third not
    side_b, kills_b = side_and_kills(runs, rules, 2, "farm-both")
    side_f, kills_f = side_and_kills(runs, rules, 2, "farm")
    assert not lower(side_b, side_f) and not lower(side_f, side_b), "rules, spacing 2"
    assert not lower(kills_f, kills_b) and not lower(kills_b, kills_f), "rules, spacing 2"
    side_b, _ = side_and_kills(runs, rules, 1, "farm-both")
    side_f, _ = side_and_kills(runs, rules, 1, "farm")
    assert sorted(lower([v], side_f) for v in side_b) == [False, True, True]
    assert max(side_b) > max(side_f)
    # spacing 4: the run that did not collapse breaches the side lanes as often as FARM does
    kept = [r for r in group(runs, rules, 4, "farm-both") if r["mean_judged_success"] > 0.0]
    assert len(kept) == 1
    side_f, _ = side_and_kills(runs, rules, 4, "farm")
    assert kept[0]["events_total"]["side_breach"] / EPISODES > max(side_f)
    # the two collapsed runs show fewer side-lane breaches, on episodes cut short
    assert max(per_episode(low, "side_breach")) < min(side_f)


def check_machines(text: dict[str, str]) -> None:
    """The pays the text states, read from each machine."""
    for card, body in text.items():
        # one live state: every transition leaves u0, and u1 (the failure state) ends the episode
        assert set(re.findall(r"^\((u\d), ", body, re.M)) == {"u0"}, card
        assert "STATES: u0, u1" in body and "REJECTING_STATES: u1" in body, card
        reward = body.split("REWARD_FUNCTION:")[1]
        pays = {
            m["cond"]: m["pay"]
            for m in re.finditer(r"^\(u\d, (?P<cond>.+), u\d\) -> (?P<pay>-?[\d.]+)$", reward, re.M)
        }
        top = {pay for cond, pay in pays.items() if re.search(r"(?<!!)top_breach", cond)}
        assert top == {TOP_PAY[card]}, (card, top)
        soft = {pay for cond, pay in pays.items() if not re.search(r"(?<!!)top_breach", cond)}
        assert soft == ({"-1", "-2"} if card == "lanes-rules" else set()), (card, soft)
    assert text["lanes-guard"].count("->") == 2 and text["lanes-rules"].count("->") == 14


# ======================================================================================
#                                          PLOT
# ======================================================================================
def style_axes(ax, colors: dict) -> None:
    ax.grid(color=colors["line"], alpha=0.25)
    ax.set_axisbelow(True)
    ax.set_facecolor("none")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x", visible=False)


def draw_arm(ax, theme: str, x: float, c: Cell, arm: str) -> None:
    """One bar with its run dots, 95% t-interval whisker and mean label."""
    colors = PALETTE[theme]
    color = colors["series"][ARMS[arm][1]]
    ax.bar(
        x,
        c.mean,
        width=0.26,
        color=color,
        alpha=0.55,
        yerr=[[c.mean - c.low], [c.high - c.mean]],
        error_kw={"ecolor": colors["text"], "capsize": 3, "elinewidth": 1},
    )
    # a dot per run, side by side, so no run hides behind another; a 0% dot stays whole
    ax.plot(
        [x + 0.07 * (i - 1) for i in range(len(c.values))],
        c.values,
        "o",
        color=color,
        mec=colors["text"],
        ms=4,
        zorder=4,
        clip_on=False,
    )
    ax.text(x, c.high + 0.025, pct(c.mean), ha="center", va="bottom")


def draw_success(cells: dict, theme: str) -> Figure:
    """Judged success per spacing and method, one panel per card.

    Narrow and tall: the SVG is 3.7 inches wide, so a 390 px phone shows it at its own size and
    the text stays 11 px; a wider figure shrinks to about 7 px there.
    """
    colors = PALETTE[theme]
    fig = Figure(figsize=(FIG_WIDTH, 7.2), layout="constrained")
    axes = fig.subplots(len(CARDS), 1, sharex=True, sharey=True)
    for ax, (card, (name, line)) in zip(axes, CARDS.items(), strict=True):
        for j, arm in enumerate(ARMS):
            for i, spacing in enumerate(SPACINGS):
                draw_arm(ax, theme, i + (j - 1) * 0.34, cells[card, spacing, arm], arm)
        ax.set_title(textwrap.fill(f"{name} card: {line}", 46), loc="left")
        ax.set_ylim(-0.04, 1.2)
        ax.set_xlim(-0.55, len(SPACINGS) - 0.45)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        style_axes(ax, colors)
    fig.supylabel("Top lane held, of 100 test episodes")
    axes[-1].set_xticks(range(len(SPACINGS)), [SPACING_TICK[s] for s in SPACINGS])
    axes[-1].set_xlabel("Lane spacing: rows from one lane to the next")
    fig.legend(
        [Patch(color=colors["series"][idx], alpha=0.55) for _, idx, _ in ARMS.values()],
        [label for label, _, _ in ARMS.values()],
        loc="outside upper center",
        ncols=1,
        frameon=False,
    )
    return fig


def save_svgs(name: str, draw) -> None:
    """Write the light and the dark SVG of one plot."""
    (ENTRY / "plots").mkdir(exist_ok=True)
    for theme, suffix in (("light", ""), ("dark", "-dark")):
        colors = PALETTE[theme]
        style = {
            "svg.fonttype": "none",  # real text: small files, the page's font
            "svg.hashsalt": "lanes-spacing",  # the same ids on every build
            "font.family": "sans-serif",
            "font.size": FONT_PT,
            "axes.titlesize": FONT_PT,
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
def machine(name: str, source: Path) -> str:
    """Copy one committed machine to ``graphs/<name>`` and draw it; return its text."""
    text = source.read_text()
    rm = ENTRY / f"graphs/{name}.rm"
    rm.parent.mkdir(exist_ok=True)
    rm.write_text(text)
    render_file(rm, rm.with_suffix(".svg"), html=True)
    return text


def machine_facts(text: str) -> tuple[int, int, str]:
    """Number of states, number of transitions and the failure state (rejecting) of a machine."""
    states = next(x for x in text.splitlines() if x.startswith("STATES:")).split(":")[1]
    failure = next(x for x in text.splitlines() if x.startswith("REJECTING_STATES:")).split(":")[1]
    body = text.split("TRANSITION_FUNCTION:")[1].split("REWARD_FUNCTION:")[0]
    return (
        len(states.split(",")),
        sum(line.startswith("(") for line in body.splitlines()),
        failure.strip(),
    )


def machine_note(card_id: str, texts: dict[str, str]) -> str:
    states, transitions, failure = machine_facts(texts[card_id])
    note = (
        f"`{card_id}`: {states} states, {transitions} transition{'s' * (transitions != 1)}. "
        f"`{failure}` (red) is the failure state: a "
        f"top-lane breach sends the machine there, pays {TOP_PAY[card_id]} and ends the episode."
    )
    if card_id == "lanes-rules":
        note += (
            " The other transitions stay in `u0` and pay -1 for a side-lane breach or a trampled "
            "plant, -2 for both on one step."
        )
    return note + " Drag a state, click an edge for its cases."


def clause_table(card: dict) -> dict:
    """A card's LTL clauses (the card's answer) with their LTLf."""
    clauses = [
        [f"{t}({', '.join(names)}) {priority}", f"`{pretty_ltlf(ltlf_of(t, list(names)))}`"]
        for t, names, priority in card["expect"]
    ]
    return {"type": "table", "columns": ["Clause (the card's answer)", "LTLf"], "rows": clauses}


def task_section(cards: dict, texts: dict[str, str]) -> dict:
    blocks: list[dict] = [
        {
            "type": "text",
            "text": "The two cards, shown once here; open a fold for its LTL clauses and its machine. The "
            "cards at spacing 2 and 1 copy them with only the lane spacing changed: the same task text, "
            "the same clauses and the same machine, so no machine was generated again. The two cards "
            "left out are shown under ARM-FM (kill-two) and Limits (absence).",
        }
    ]
    for card_id, (name, _) in CARDS.items():
        card = cards[card_id]
        blocks += [
            {"type": "text", "heading": f"{name} card", "text": f"**Task:** {card['task']}"},
            fold(
                f"{name} card: LTL clauses and machine",
                [
                    clause_table(card),
                    {
                        "type": "figure",
                        "src": f"graphs/{card_id}.html",
                        "height": 340,
                        "title": f"{name} card: the FARM machine",
                        "caption": machine_note(card_id, texts),
                        "details": {"title": "RM text", "code": texts[card_id]},
                    },
                ],
            ),
        ]
    return {"id": "task", "title": "The two tasks, their LTL and their machines", "blocks": blocks}


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
                    "**The world.** Zombies walk down three lanes of a field; the agent kills one by "
                    "stepping onto it, and a zombie that leaves the top lane is a breach.",
                    "**The three groups.** FARM: a language model reads the task and writes a reward "
                    "machine, a small state machine that pays for keeping or breaking the rules, and the "
                    "agent learns from that pay alone. FARM + kill reward: the same machine, and the agent "
                    "is also paid the world's +1 per kill. No reward machine: the same agent, paid +1 per "
                    "kill only, never reading the task.",
                    "**The test.** We moved the lanes closer, from 4 rows apart to 2 and then 1, trained 3 "
                    "runs per group and checked each on 100 test episodes. The kill reward was added later, "
                    "to see whether paying for kills also makes FARM defend the side lanes.",
                ],
            },
            {
                "type": "list",
                "heading": "Words used on this page",
                "items": [
                    "**Card:** one task with its text, its rules and its world. **Guard** and **rules** "
                    "are the two cards here: guard has one rule, keep zombies out of the top lane; rules "
                    "adds two soft rules (keep the other lanes, keep the plants) that the judge does not "
                    "count.",
                    "**Spacing 4, the counted card:** the lanes 4 rows apart, as in the earlier results. "
                    "At spacing 2 and 1 they are 2 and 1 rows apart (at 1, no plant can sprout).",
                    '**Hard and soft rule:** breaking a hard "never" rule ends the episode with a penalty; '
                    "breaking a soft one costs a penalty and play goes on.",
                    "**Judged success:** the share of 100 test episodes (300 steps each) in which no "
                    "zombie gets through the top lane, as a program (the judge) reads it off the saved "
                    "episode.",
                    "**LTL, LTLf:** a formal notation for a rule over an episode; `~(F top_breach)` reads "
                    '"a top-lane breach never happens".',
                    "**95% t-interval:** the usual error bar for a mean of a few runs; with 3 runs it is "
                    "wide.",
                    "**PPO:** the standard reinforcement-learning method all groups use.",
                    "**Kill reward:** the world's own +1 for each zombie the agent kills; FARM + kill "
                    "reward adds it to the machine's pay.",
                    "**Plan check:** our check, before training, that a machine lets a sensible plan "
                    "through.",
                    "**ARM-FM:** the pipeline of the ARM-FM paper, which also has a language model write a "
                    "reward machine from the task text. It has its own section.",
                ],
            },
        ],
    }


def results_table(cells: dict) -> dict:
    rows = [
        [
            name,
            str(spacing),
            label,
            runs_pct(cells[card, spacing, arm]),
            mean_pct(cells[card, spacing, arm]),
        ]
        for card, (name, _) in CARDS.items()
        for spacing in SPACINGS
        for arm, (label, _, _) in ARMS.items()
    ]
    return {
        "type": "table",
        "heading": "Judged success: share of the 100 test episodes with the top lane held",
        "columns": ["Card", "Spacing", "Method", "Runs 1 / 2 / 3", "Mean [95% t-interval]"],
        "rows": rows,
    }


def left_out_values(runs_all: list[dict], card: str, spacing: int, arm: str) -> list[float]:
    """Judged success of the 3 runs of a left-out card, in run order (empty if none ran)."""
    found = sorted(
        (r for r in runs_all if (r["card"], r["spacing"], r["arm"]) == (card, spacing, arm)),
        key=lambda r: r["index"],
    )
    return [r["mean_judged_success"] for r in found]


def new_section(bound: int) -> dict:
    """What this version adds, in at most five lines, first on the page."""
    return {
        "id": "new",
        "title": "What this version adds",
        "blocks": [
            {
                "type": "list",
                "items": [
                    "**FARM + kill reward** is a third group: the machine's pay plus the world's +1 per "
                    "kill (18 runs).",
                    f"**Top lane:** within {bound} points of FARM, except on the rules card at spacing 4, "
                    "where 2 of its 3 runs fail every test episode.",
                    "**Side lanes:** fewer breaches on the guard card, not reliably on the rules card.",
                    "**ARM-FM:** no usable machine for guard and rules; it trained only on 'Kill at "
                    "least two zombies'.",
                    "**Every card** now shows its task, its LTL and its machine.",
                ],
            }
        ],
    }


def two_cards_left_out(runs_all: list[dict]) -> str:
    """The line of "In short" on the two left-out cards; Limits holds their numbers."""
    absence, existence = LEFT_OUT

    def values(card: str, spacing: int, arm: str) -> list[float]:
        return left_out_values(runs_all, card, spacing, arm)

    assert values(absence, 4, "farm") == values(absence, 4, "no-rm") == [1.0] * 3
    assert values(existence, 4, "no-rm") == values(existence, 2, "no-rm") == [1.0] * 3
    assert all(sum(values(existence, s, "farm")) / 3 < 1.0 for s in (4, 2))
    return (
        "**Two cards left out.** FARM is not better on them: on the absence card every method scores "
        "100%, on 'Kill at least two zombies' no reward machine does best. Neither tests learning "
        "(Limits)."
    )


def kill_reward_items(runs: list[dict], cells: dict) -> list[str]:
    """The list "What adding the world's kill reward to FARM changes"; the numbers sit in the tables."""
    _, rules = CARDS
    bound = kill_reward_bound(cells)
    (kept,) = (r for r in group(runs, rules, 4, "farm-both") if r["mean_judged_success"] > 0.0)
    return [
        f"**Top lane: about FARM's.** Apart from the rules card at spacing 4, the means are within {bound} "
        "points of FARM's, and the 95% t-intervals overlap in all 6 cases. Against no reward machine the "
        "order is FARM's: all 3 runs beat all 3 in 5 of the 6 cases, and the intervals are apart in 2.",
        "**Rules card at spacing 4: 2 of the 3 runs collapse.** They let a zombie through the top lane "
        f"in all {EPISODES} test episodes (0%); the third scores {pct(kept['mean_judged_success'])}. FARM "
        f"alone has one weak run there ({pct(min(cells[rules, 4, 'farm'].values))}), not two.",
        "**Guard card, side lanes: fewer breaches at every spacing.** Each kill-reward run is below each "
        "FARM run, and kills more zombies. They still let through more than no reward machine and kill "
        "fewer.",
        "**Rules card, side lanes: not reliably fewer.** No change at spacing 2; at spacing 1 two of the "
        "3 runs drop and the third does not; at spacing 4 only the two collapsed runs show fewer, on "
        "episodes cut short. The machine's -1 per side-lane breach does not make the kill reward defend "
        "them.",
    ]


def side_lane_finding(runs: list[dict]) -> str:
    """FARM's side-lane line of "In short", every claim recounted."""
    guard, rules = CARDS
    side = {
        (arm, card, spacing): per_episode(group(runs, card, spacing, arm), "side_breach")
        for arm in ("farm", "no-rm")
        for card in CARDS
        for spacing in SPACINGS
    }
    kills = {
        arm: per_episode([r for r in runs if r["arm"] == arm], "zombie_killed")
        for arm in ("farm", "no-rm")
    }
    farm = [v for (arm, *_), values in side.items() if arm == "farm" for v in values]
    plain = [v for (arm, *_), values in side.items() if arm == "no-rm" for v in values]
    assert max(plain) < min(farm) and min(kills["no-rm"]) > max(kills["farm"])
    rules1, guard1 = side["farm", rules, 1], side["farm", guard, 1]
    assert lower(rules1, guard1)
    fewer = 1 - (sum(rules1) / 3) / (sum(guard1) / 3)
    return (
        "**FARM does not keep the side lanes.** Its runs let zombies through a side lane in every test "
        f"episode; the rules machine, which pays -1 per such breach, lets through only {pct(fewer)} fewer "
        "than guard at spacing 1. No reward machine kills more and lets fewer through, yet holds the top "
        "lane less often."
    )


def summary_section(runs: list[dict], runs_all: list[dict], cells: dict) -> dict:
    guard, rules = CARDS

    def mean(card: str, spacing: int, arm: str) -> str:
        return pct(cells[card, spacing, arm].mean)

    farm_rules4 = cells[rules, 4, "farm"].values
    items = [
        "**FARM holds the top lane.** 17 of its 18 runs pass at least 85 of the 100 test episodes; the "
        f"one weak run ({pct(min(farm_rules4))}) is on the rules card at spacing 4.",
        "**With the lanes closer, FARM beats no reward machine every time.** At spacing 2 and 1, on both "
        "cards, all 3 FARM runs hold the top lane in more test episodes than all 3 runs with no reward "
        "machine.",
        "**At the counted spacing 4: yes on the guard card, no on the rules card.** Guard: every FARM run "
        f"above every no-reward-machine run ({mean(guard, 4, 'farm')} against "
        f"{mean(guard, 4, 'no-rm')}). Rules: {mean(rules, 4, 'farm')} against "
        f"{mean(rules, 4, 'no-rm')}, so FARM is not shown to be better.",
        "**Three runs per group is few.** Still, in 5 of the 6 comparisons all 3 FARM runs beat all 3 "
        "no-reward-machine runs, which two equal methods would do 1 time in 20. The 95% t-intervals are "
        "apart in 2, touch in 1 and overlap in 3; the two cards share their no-reward-machine runs.",
        side_lane_finding(runs),
        two_cards_left_out(runs_all),
    ]
    return {
        "id": "summary",
        "title": "In short",
        "blocks": [
            figure(
                "success",
                "Top lane held: FARM, FARM + kill reward and no reward machine",
                "Two panels, guard card and rules card. For lane spacing 4, 2 and 1, a blue bar for FARM, "
                "a green bar for FARM + kill reward and an orange bar for no reward machine show the share "
                "of the 100 test episodes with the top lane held, with a dot per training run and a 95% "
                "t-interval whisker.",
                "FARM's bar is above the no-reward-machine bar in every pair. The green bars sit close to "
                "the blue ones, except on the rules card at spacing 4, where 2 of the 3 FARM + kill "
                "reward runs scored 0%. Bars are the mean of 3 training runs, dots are the runs, whiskers "
                "are 95% t-intervals over the 3 runs, cut at 0 and 100%.",
            ),
            fold("Judged success of every group, 18 rows", [results_table(cells)]),
            {"type": "list", "items": items},
            {
                "type": "list",
                "heading": "What adding the world's kill reward to FARM changes",
                "items": kill_reward_items(runs, cells),
            },
            {
                "type": "text",
                "text": "Counts per run: [Side lanes and kills, per run](#lanes). Task text, LTL and "
                "machine of each card: [the two tasks](#task).",
            },
        ],
    }


def lanes_section(runs: list[dict]) -> dict:
    rows = []
    for card, (name, _) in CARDS.items():
        for spacing in SPACINGS:
            for arm, (label, _, _) in ARMS.items():
                found = group(runs, card, spacing, arm)
                rows.append(
                    [
                        name,
                        str(spacing),
                        label,
                        " / ".join(str(r["episodes_with_event"]["side_breach"]) for r in found),
                        run_values(per_episode(found, "side_breach")),
                        run_values(per_episode(found, "zombie_killed")),
                        run_values([r["mean_length"] for r in found], 0),
                    ]
                )
    return {
        "id": "lanes",
        "title": "Side lanes and kills, per run",
        "intro": "The judge counts the top lane only. This table counts what it leaves out, side-lane "
        "breaches and zombies killed per test episode, for each run (cells read run 1 / run 2 / run 3).",
        "blocks": [
            {
                "type": "text",
                "text": "The counts come from the saved step-by-step test episodes; nothing was replayed. "
                "Top-lane breaches are not listed: the failed test episodes are exactly those with a "
                "top-lane breach, so they equal 100 minus the judged success.",
            },
            {
                "type": "text",
                "text": f"A FARM episode ends at its first top-lane breach, so it can be shorter than "
                f"{MAX_STEPS} steps and its counts cover fewer steps (last column; see Limits). A "
                f"no-reward-machine episode always runs all {MAX_STEPS}. The two cards share their "
                "no-reward-machine runs, so those rows repeat.",
            },
            {
                "type": "table",
                "columns": [
                    "Card",
                    "Spacing",
                    "Method",
                    "Test episodes with a side-lane breach, of 100",
                    "Side-lane breaches per episode",
                    "Zombies killed per episode",
                    f"Mean steps per episode, of {MAX_STEPS}",
                ],
                "rows": rows,
            },
        ],
    }


def arm_fm_attempts() -> tuple[int, list[list[str]]]:
    """Recount of ARM-FM's attempts on the two main cards, from their status files.

    Each card has its main attempt and the paraphrases ``<card>~p1..p3``. Stops unless every
    attempt is the plan-check failure "ends the episode before the agent acts", every machine's
    start state is final and no ARM-FM run of either card exists. Returns the attempts per card
    and the rows of the page's table (card, attempt, calls, wall time).
    """
    assert not list((ROOT / "outputs/runs").glob("bench__*__lanes-*__arm-fm__ppo")), "ARM-FM ran"
    base = ROOT / ARM_FM_FORCING
    rows: list[list[str]] = []
    per_card = set()
    for card, (name, _) in CARDS.items():
        paraphrases = sorted(p.name for p in base.glob(f"{card}~p*.status.json"))
        assert paraphrases == [f"{card}~p{i}.status.json" for i in (1, 2, 3)], card
        attempts = [card, *(p.removesuffix(".status.json") for p in paraphrases)]
        per_card.add(len(attempts))
        for attempt in attempts:
            status = json.loads((base / f"{attempt}.status.json").read_text())
            assert status["status"] == "pipeline-failed", attempt
            assert status["reason"] == PLAN_CHECK_REASON, attempt
            text = (base / attempt / "reward_machine.txt").read_text()
            initial = re.search(r"^INITIAL_STATE: (\S+)$", text, re.M)[1]
            finals = re.search(r"^FINAL_STATES: (.+)$", text, re.M)[1]
            assert initial in finals.split(", "), attempt
            kind = "main" if attempt == card else f"paraphrase {attempt[-1]}"
            rows.append([name, kind, str(status["calls"]), fixed(status["wall_time_s"])])
    (count,) = per_card
    return count, rows


def rejected_note(text: str) -> str:
    """The figure note of a machine ARM-FM wrote for a main card, read back from its text."""
    states = next(x for x in text.splitlines() if x.startswith("STATES:")).split(":")[1]
    initial = re.search(r"^INITIAL_STATE: (\S+)$", text, re.M)[1]
    finals = re.search(r"^FINAL_STATES: (.+)$", text, re.M)[1]
    assert initial in finals.split(", ")
    body = text.split("TRANSITION_FUNCTION:")[1].split("REWARD_FUNCTION:")[0]
    transitions = sum(line.startswith("(") for line in body.splitlines())
    return (
        f"ARM-FM's machine: {len(states.split(','))} states, {transitions} transitions. The start state "
        f"`{initial}` is also final, so an episode would end before the agent acts."
    )


def kill_two_note(who: str, text: str) -> str:
    """The figure note of a kill-two machine (FARM's or ARM-FM's), read back from its text."""
    states = next(x for x in text.splitlines() if x.startswith("STATES:")).split(":")[1]
    assert "FINAL_STATES: u2" in text and "REJECTING_STATES" not in text
    body = text.split("TRANSITION_FUNCTION:")[1].split("REWARD_FUNCTION:")[0]
    reward = text.split("REWARD_FUNCTION:")[1]
    pays = re.findall(r"^\(u\d, zombie_killed, u\d\) -> (-?[\d.]+)$", reward, re.M)
    assert len(pays) == 2 and len(states.split(",")) == 3, text
    assert re.findall(r"^\(u1, zombie_killed\) -> (u\d)$", body, re.M) == ["u2"]
    transitions = sum(line.startswith("(") for line in body.splitlines())
    return (
        f"{who}'s machine for the card: 3 states, {transitions} transitions. `u2` is final: the "
        f"second kill reaches it, pays {pays[1]} and ends the episode; the first kill pays {pays[0]}. "
        "Drag a state, click an edge for its cases."
    )


def absence_note(text: str) -> str:
    """The figure note of FARM's machine for the absence card, read back from its text."""
    assert "STATES: u0\n" in text and "REJECTING_STATES" not in text
    body = text.split("TRANSITION_FUNCTION:")[1].split("REWARD_FUNCTION:")[0]
    pays = re.findall(r"-> (-?[\d.]+)$", text.split("REWARD_FUNCTION:")[1], re.M)
    assert pays == ["-1", "-1", "-2"] and body.count("-> u0") == 3
    return (
        "FARM's machine for the card: 1 state, 3 transitions, all staying in `u0`. A top-lane breach "
        "alone pays -1, a side-lane breach alone -1, both on one step -2; nothing ends the episode. "
        "Drag a state, click an edge for its cases."
    )


def machine_item(name: str, title: str, caption: str, text: str) -> dict:
    """One interactive machine as a gallery item, with its text in a fold."""
    return {
        "src": f"graphs/{name}.html",
        "height": 340,
        "alt": title,
        "caption": f"**{title}**\n{caption}",
        "details": {"title": "RM text", "code": text},
    }


def arm_fm_section(
    runs_all: list[dict],
    card: dict,
    kill_two: dict[str, str],
    rejected: dict[str, str],
    counted: tuple[int, list[list[str]]],
) -> dict:
    """ARM-FM: no machine for the two main cards, one trained card with its numbers and machines.

    ``counted`` is the result of ``arm_fm_attempts``.
    """
    existence = LEFT_OUT[1]
    attempts, attempt_rows = counted
    rows = []
    for spacing in (4, 2):
        for arm, label in LEFT_OUT_ARMS.items():
            c = cell(group(runs_all, existence, spacing, arm))
            rows.append([str(spacing), label, runs_pct(c), mean_pct(c)])
    fm4, farm4 = (cell(group(runs_all, existence, 4, a)) for a in ("arm-fm", "farm"))
    fm2, farm2 = (cell(group(runs_all, existence, 2, a)) for a in ("arm-fm", "farm"))
    for fm, farm in ((fm4, farm4), (fm2, farm2)):
        assert fm.low <= farm.high and farm.low <= fm.high  # the intervals overlap
        assert abs(round(100 * fm.mean) - round(100 * farm.mean)) <= 5
    plain = [cell(group(runs_all, existence, s, "no-rm")).mean for s in (4, 2)]
    assert plain == [1.0, 1.0] and max(fm4.mean, fm2.mean, farm4.mean, farm2.mean) < 1.0
    assert not [
        r for r in runs_all if r["card"] == existence and r["spacing"] == 1 and r["arm"] == "arm-fm"
    ]
    task = card["task"].rstrip(".")
    guard_name, rules_name = (name.lower() for name, _ in CARDS.values())
    return {
        "id": "armfm",
        "title": f"ARM-FM: no usable machine for guard and rules; trained only on '{task}'",
        "blocks": [
            {
                "type": "text",
                "text": "ARM-FM is the method of the ARM-FM paper, which also has a language model write a "
                "reward machine from the task text. It needs a task that ends on a goal: every mission in "
                f"its authors' prompts ends on a +1 goal. '{task}' ends at the second kill. The "
                f"{guard_name} and {rules_name} cards never end on a goal, and for each ARM-FM wrote a "
                "machine whose start state is already final: an episode would end before the agent acts.",
            },
            {
                "type": "text",
                "text": f"Our plan check rejected both machines. Each card had {attempts} ARM-FM attempts, "
                f"the main one and {attempts - 1} paraphrases of the task, and all {2 * attempts} failed "
                f"the same way: `pipeline-failed`, `{PLAN_CHECK_REASON}`. Both cards count as not learned "
                "and no ARM-FM agent was trained on them (user decision, 2026-11-23, recorded at the end of "
                "`docs/decisions/benchmark/thesis-benchmark.md`).",
            },
            fold(
                f"The {2 * attempts} attempts: calls and wall time",
                [
                    {
                        "type": "table",
                        "columns": ["Card", "Attempt", "Calls", "Wall time (s)"],
                        "rows": attempt_rows,
                    }
                ],
            ),
            fold(
                "The two rejected machines, in full",
                [
                    {
                        "type": "gallery",
                        "width": 480,
                        "items": [
                            machine_item(
                                f"{card_id}-arm-fm",
                                f"{CARDS[card_id][0]} card: the ARM-FM machine",
                                rejected_note(text),
                                text,
                            )
                            for card_id, text in rejected.items()
                        ],
                    }
                ],
            ),
            {
                "type": "text",
                "text": f"**One card did train: '{task}'.** The second kill ends the task, so ARM-FM's "
                "machine has a final state that is not the start. It trained 3 runs at spacing 4 and 3 "
                "at spacing 2 (none at spacing 1), next to FARM and no reward machine on the same card.",
            },
            {
                "type": "table",
                "heading": "Judged success on the kill-two card, by method",
                "columns": ["Spacing", "Method", "Runs 1 / 2 / 3", "Mean [95% t-interval]"],
                "rows": rows,
            },
            {
                "type": "text",
                "text": f"ARM-FM scores {pct(fm4.mean)} and {pct(fm2.mean)}, FARM {pct(farm4.mean)} and "
                f"{pct(farm2.mean)}: within 5 points of each other, with overlapping intervals, and both "
                "below no reward machine, whose +1 per kill already pays for this task. The card is not a "
                "fair test of learning (Limits).",
            },
            fold(
                "Kill-two card: task, LTL clause and both machines",
                [
                    {"type": "text", "text": f"**Task:** {card['task']}"},
                    clause_table(card),
                    {
                        "type": "gallery",
                        "width": 480,
                        "items": [
                            machine_item(
                                f"{existence}-{key}",
                                f"Kill-two card: the {who} machine",
                                kill_two_note(who, kill_two[who]),
                                kill_two[who],
                            )
                            for key, who in (("farm", "FARM"), ("arm-fm", "ARM-FM"))
                        ],
                    },
                ],
            ),
        ],
    }


def where_from(runs: list[dict]) -> list[list[str]]:
    """Per spacing, the run folders the no-reward-machine numbers come from."""
    rows = []
    for spacing in SPACINGS:
        found = group(runs, "lanes-guard", spacing, "no-rm")
        owners = {r["trained_in"].split("/")[0] for r in found}
        assert len(owners) == 1, owners
        rows.append(
            [
                str(spacing),
                f"`outputs/runs/{owners.pop()}/<run folder>`",
                found[0]["git_head"],
                "Trained under the left-out card `tpl-existence-two-5-nogoal`, which does not matter "
                "for a run that ignores the task text. The folders `bench__forcing__lanes-guard__no-rm__ppo` "
                "and `bench__forcing__lanes-rules__no-rm__ppo` link to them and hold their own judge files."
                if spacing == 4
                else f"`bench__lanes-spacing__lanes-rules-spacing{spacing}__no-rm__ppo` links to them and "
                "holds its own judge file.",
            ]
        )
    return rows


def setup_section(runs: list[dict]) -> dict:
    return {
        "id": "setup",
        "title": "What was run",
        "blocks": [
            {
                "type": "table",
                "columns": ["Method", "Trains on", "Pay and runs"],
                "rows": [
                    [
                        "FARM",
                        "The machine's reward only (`reward_source: rm`), written by the language model "
                        "from the task text.",
                        "Guard machine: -10 for a top-lane breach, which ends the episode, 0 otherwise. "
                        "Rules machine: -96.1 for it (ends the episode), -1 for a side-lane breach or a "
                        "trampled plant, -2 for both on one step, 0 otherwise. Nothing for kills. "
                        "3 runs per card and spacing: 18 runs.",
                    ],
                    [
                        "FARM + kill reward",
                        "The machine's reward plus the world's +1 per zombie killed (`reward_source: "
                        "both`).",
                        "The same two machines and pays as FARM, and +1 for each kill on top. The suite is "
                        "`lanes-both` (`experiments/benchmark/lanes-spacing/runs-farm-both.yaml`). 3 runs "
                        "per card and spacing: 18 runs.",
                    ],
                    [
                        "No reward machine",
                        "The world's reward only (`reward_source: env`): +1 per zombie killed.",
                        "No machine, and the agent never reads the task text, so one set of 3 runs per "
                        "spacing serves both cards; each card judges it with its own clauses. 9 runs "
                        "trained, 18 judged.",
                    ],
                ],
            },
            fold(
                "Where the no-reward-machine numbers come from",
                [
                    {
                        "type": "table",
                        "columns": [
                            "Spacing",
                            "Run folders of the 3 runs",
                            "Code point",
                            "Shared with",
                        ],
                        "rows": where_from(runs),
                    }
                ],
            ),
        ],
    }


def left_out_blocks(runs_all: list[dict], absence_card: dict, absence_text: str) -> list[dict]:
    """The two cards left out of the comparison, as blocks of the Limits section."""

    def values(card: str, spacing: int, arm: str) -> list[float]:
        return left_out_values(runs_all, card, spacing, arm)

    absence, existence = LEFT_OUT
    absence_runs = [r for r in runs_all if r["card"] == absence]
    assert len(absence_runs) == 18 and {r["mean_judged_success"] for r in absence_runs} == {1.0}
    exist_farm = {s: values(existence, s, "farm") for s in (4, 2)}
    exist_arm_fm = {s: values(existence, s, "arm-fm") for s in (4, 2)}
    assert all(values(existence, s, "no-rm") == [1.0] * 3 for s in (4, 2))
    assert not [r for r in runs_all if r["card"] == existence and r["spacing"] == 1]
    assert not [r for r in absence_runs if r["arm"] == "arm-fm"]
    rows = [
        [card, str(spacing), arm_label, runs_pct_values(values(card, spacing, arm))]
        for card in LEFT_OUT
        for spacing in SPACINGS
        for arm, arm_label in LEFT_OUT_ARMS.items()
        if values(card, spacing, arm)
    ]
    return [
        {
            "type": "list",
            "heading": "Two cards left out of the comparison",
            "items": [
                f"**Absence card** (`{absence}`, '{absence_card['task'].rstrip('.')}': two soft rules). "
                "All 18 runs, FARM and no reward machine at all three spacings, pass every test "
                "episode, so judged success cannot tell the methods apart. At spacing 4 FARM breaks "
                "the soft rules 18.7 times per episode against 26.2 for an idle agent and 10.5 for no "
                "reward machine (from the `soft-breaks-vs-idle/` entry, not recounted here).",
                f"**Kill-two card** (`{existence}`, 'Kill at least two zombies': a hard rule). A random "
                "agent passes this world in 68 of 100 episodes at spacing 1 (a note in "
                "`experiments/benchmark/lanes-spacing/runs-farm.yaml`, not recounted), so spacing 1 "
                "was dropped and the card is not a fair test. At spacing 4 and 2 FARM passes "
                f"{pct(sum(exist_farm[4]) / 3)} and {pct(sum(exist_farm[2]) / 3)} of the test "
                f"episodes on average, ARM-FM {pct(sum(exist_arm_fm[4]) / 3)} and "
                f"{pct(sum(exist_arm_fm[2]) / 3)} (3 runs each), and no reward machine all of them: "
                "the world's +1 per kill already pays for exactly this task. Its task, LTL and both "
                "machines are under ARM-FM.",
            ],
        },
        fold(
            "Absence card: task, LTL clauses and FARM machine",
            [
                {"type": "text", "text": f"**Task:** {absence_card['task']}"},
                clause_table(absence_card),
                {
                    "type": "gallery",
                    "width": 480,
                    "items": [
                        machine_item(
                            f"{absence}-farm",
                            "Absence card: the FARM machine",
                            absence_note(absence_text),
                            absence_text,
                        )
                    ],
                },
            ],
        ),
        fold(
            "Judged success of the left-out runs",
            [
                {
                    "type": "table",
                    "columns": ["Card", "Spacing", "Method", "Runs 1 / 2 / 3"],
                    "rows": rows,
                }
            ],
        ),
    ]


def runs_pct_values(values: list[float]) -> str:
    return " / ".join(pct(v) for v in values)


def all_runs_section(runs: list[dict]) -> dict:
    rows = []
    for card in CARDS:
        for spacing in SPACINGS:
            for arm in ARMS:
                for r in group(runs, card, spacing, arm):
                    rows.append(
                        [
                            CARDS[card][0],
                            str(spacing),
                            ARMS[arm][0],
                            str(r["index"]),
                            r["run"].split("-", 1)[1],
                            f"{r['judged_passed']} of 100",
                            fixed(r["events_total"]["side_breach"] / EPISODES),
                            fixed(r["events_total"]["zombie_killed"] / EPISODES),
                            r["git_head"],
                            f"`{r['trained_in'].split('/')[0].removeprefix('bench__')}`",
                        ]
                    )
    steps = f"{runs[0]['steps']:,}"
    return {
        "id": "runs",
        "title": "Every run",
        "intro": f"The {len(rows)} finished runs of the two cards, recounted in `evidence/runs.json`; every "
        f"one trained {steps} steps. The Run folder column is the time part of the folder's name under "
        "`outputs/runs/bench__<suite>__<card>__<method>__ppo/`; the last column names the folder that "
        "trained the agent, which is the owner folder for a shared no-reward-machine run.",
        "collapsed": True,
        "blocks": [
            {
                "type": "table",
                "columns": [
                    "Card",
                    "Spacing",
                    "Method",
                    "Run",
                    "Run folder",
                    "Test episodes passed",
                    "Side-lane breaches per episode",
                    "Kills per episode",
                    "Code point",
                    "Trained in",
                ],
                "rows": rows,
            }
        ],
    }


def config_table(runs_all: list[dict]) -> dict:
    """The config keys that differ between groups of runs and their values, read from the runs."""
    kill_two = LEFT_OUT[1]

    def group_name(run: dict) -> str | None:
        if run["card"] in CARDS:
            return ARMS[run["arm"]][0]
        if run["card"] == kill_two and run["arm"] in ("farm", "arm-fm"):
            return f"{LEFT_OUT_ARMS[run['arm']]}, kill-two card"
        return None

    names = [label for label, _, _ in ARMS.values()] + [
        "FARM, kill-two card",
        "ARM-FM, kill-two card",
    ]
    rows = []
    for name in names:
        for spacing in SPACINGS:
            found = [r for r in runs_all if group_name(r) == name and r["spacing"] == spacing]
            if found:
                values = [
                    " / ".join(sorted({str(r[key]) for r in found}))
                    for key in ("reward_source", "time_limit_penalty", "device", "git_head")
                ]
                rows.append([name, str(spacing), *values])
    return {
        "type": "table",
        "columns": [
            "Group",
            "Spacing",
            "`reward_source`",
            "`time_limit_penalty`",
            "`device`",
            "Code point (`git_head`)",
        ],
        "rows": rows,
    }


def closing_sections(
    runs_all: list[dict], absence_card: dict, absence_text: str, attempts: int, bound: int
) -> list[dict]:
    return [
        {
            "id": "checks",
            "title": "Checks",
            "collapsed": True,
            "blocks": [
                {
                    "type": "list",
                    "items": [
                        "**Recount from raw folders.** `check/collect.py` reads every `judge.json` (100 test "
                        "episodes each) of the two cards and of the two left-out cards, 90 runs (54 on "
                        "the two cards, 36 on the left-out ones, 6 of them ARM-FM), and recounts the "
                        "passes from the per-episode records; every count equals the stored mean. "
                        "Folders with a dot in their name are skipped; none lacked a judge file.",
                        "**Breaches per lane.** The events are counted from the saved per-step labels of "
                        "the 54 runs of the two cards (5,400 episodes). Every judge verdict equals the "
                        "first top-lane breach found in the labels, and each run's failed episodes equal "
                        "its episodes with a top-lane breach. Each FARM episode, with or without the "
                        "kill reward, that has a breach ends at its first one.",
                        "**Rewards.** Every `config.yaml` says `reward_source: rm` for FARM, `both` for "
                        "FARM + kill reward and `env` for no reward machine; FARM and FARM + kill reward "
                        "runs trained on, and were judged with, the same committed machine; "
                        "no-reward-machine runs have no bundle. A FARM + kill reward run and the FARM "
                        "run with the same number have the same card, world, machine and steps.",
                        "**Machines.** The `.rm` files in `graphs/` are copies of the committed bundles' "
                        "`reward_machine.txt`: FARM's machines of the two cards, of the kill-two card and "
                        "of the absence card, and ARM-FM's machines of the kill-two card and of the guard "
                        "and rules cards. The pays the text quotes are read back from them.",
                        f"**ARM-FM on the two cards.** Each card had {attempts} attempts, the main one and "
                        f"{attempts - 1} paraphrases (`<card>~p1..p{attempts - 1}.status.json`). All "
                        f"{2 * attempts} say `pipeline-failed` with the plan-check reason, each machine ARM-FM "
                        "wrote has its start state among its final states, and no ARM-FM run folder exists "
                        "for either card.",
                        "**Cards.** The spacing cards have the counted cards' task text and clauses and "
                        "differ only in `env_kwargs`; spacing 4 is the default value of `lane_spacing`.",
                        "**Statements.** The build asserts every comparison and count the text states "
                        f"(the 5 of 6 orderings for FARM and for FARM + kill reward, the {bound}-point "
                        "bound, the intervals that do and do not overlap, the 17 of 18 FARM runs, the two "
                        "collapsed runs, the side-lane and kill comparisons of the kill-reward list).",
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
                        "3 runs per group, card and spacing. The best an exact order test can say for "
                        "3 against 3 is 1 in 20 per comparison, and the two cards at one spacing share "
                        "their no-reward-machine runs. The comparison of FARM + kill reward with FARM "
                        "rests on the same 3 runs, so a difference of a few points between them is not "
                        "evidence of an effect.",
                        "FARM's win is on the hard top-lane rule only. Soft rules do not enter judged "
                        "success, and FARM breaks the side-lane rule in every test episode, with or "
                        "without the soft rule in its machine. With the kill reward added, runs still "
                        "break it in 52 to 100 of the 100 test episodes. The rules card at spacing 4 does "
                        "not show FARM better, and with the kill reward 2 of its 3 runs fail every test "
                        "episode.",
                        "A FARM episode, with or without the kill reward, ends at the first top-lane "
                        "breach, so the per-episode side-lane and kill counts of runs that breached cover "
                        "fewer steps than 300. This matters most for the two collapsed runs of the rules "
                        "card at spacing 4 (80 and 129 steps); the kill-reward episodes of the guard card "
                        "average more than 285 steps.",
                        "ARM-FM has no usable machine for the guard and rules cards, so it has no runs on "
                        "them (section ARM-FM), and on the kill-two card none at spacing 1; its two "
                        "spacings there have 3 runs each.",
                        "The figure is static SVG, not Plotly: plotly.js embedded is 4.8 MB, over the "
                        "repository's 1 MB file limit. The machines are interactive.",
                    ],
                },
                *left_out_blocks(runs_all, absence_card, absence_text),
            ],
        },
        {
            "id": "files",
            "title": "Files and rerun",
            "blocks": [
                {
                    "type": "list",
                    "items": [
                        "This page is `index.html`, built from `data.json`. `check/` has `collect.py` (the "
                        "recount) and `build_page.py` (the page, the figure and the machine graphs); "
                        "`evidence/runs.json` is the recount; `graphs/` has the machines (`.rm`, `.svg`, "
                        "interactive `.html`); `plots/` has the figure, light and dark.",
                        "The README note in `docs/paper/README.md` holds the detail.",
                    ],
                },
                fold(
                    "Config keys that differ between groups of runs",
                    [
                        {
                            "type": "text",
                            "text": "In `config.yaml` the keys `exp_name`, `yaml_config_name`, `seed`, "
                            "`layout_seed`, `env_kwargs` (the lane spacing) and `bundle` (the machine) "
                            "name each run; the four below differ between groups; every other key is "
                            "equal in all 90 runs.",
                        },
                        config_table(runs_all),
                    ],
                ),
                {
                    "type": "code",
                    "text": "# from the repository root, RM_RL_env active; fill.py is the agent-artifacts skill's script\n"
                    "python -I docs/paper/lanes-spacing/check/collect.py\n"
                    "PYTHONPATH=app python -W ignore docs/paper/lanes-spacing/check/build_page.py\n"
                    "python3 ~/.claude/skills/agent-artifacts/scripts/fill.py \\\n"
                    "  docs/paper/lanes-spacing/data.json docs/paper/lanes-spacing/index.html",
                },
            ],
        },
    ]


def check_left_out(runs_all: list[dict]) -> None:
    """The left-out cards: the method's reward source and world; ARM-FM's machine and code point."""
    for run in runs_all:
        arm = run["arm"]
        assert run["reward_source"] == (ARMS[arm][2] if arm in ARMS else "rm"), run["run"]
        assert run["env_kwargs"] == (
            {} if run["spacing"] == 4 else {"lane_spacing": run["spacing"]}
        )
        if arm == "arm-fm":
            assert run["card"] == LEFT_OUT[1] and run["spacing"] in ARM_FM_CODE, run["run"]
            assert run["bundle"] == run["judge_bundle"] == ARM_FM_KILL_TWO, run["run"]
            assert run["time_limit_penalty"] == 0.0, run["run"]
            assert run["git_head"] == ARM_FM_CODE[run["spacing"]], run["run"]
            assert run["device"] == ("cpu" if run["spacing"] == 4 else "cuda"), run["run"]
        elif run["card"] == LEFT_OUT[1] and arm == "farm":  # FARM on the same card, same code
            assert run["git_head"] == {4: "809dfe3f-dirty", 2: "462cfde3-dirty"}[run["spacing"]]


def build() -> dict:
    data = json.loads((ENTRY / "evidence/runs.json").read_text())
    assert not data["skipped_without_judge"], data["skipped_without_judge"]
    runs_all = data["runs"]
    runs = [r for r in runs_all if r["card"] in CARDS]
    assert len(runs) == 54 and len(runs_all) == 90
    # the options the code-point facts call off: no staged worlds, no multi-task entries
    settings = data["settings"]
    assert "env_stages" not in settings and settings["task_bundles"] == []
    assert settings["rm_state_encoding"] == "embedding"
    cards = check_cards()
    for run in runs:
        check_run(run, data["settings"])
    check_pairs(runs)
    check_left_out(runs_all)
    check_events(runs)
    cells = all_cells(runs)
    check_claims(runs, cells)
    check_kill_reward_claims(runs, cells)
    texts = {
        card_id: machine(card_id, ROOT / BUNDLES / card_id / "reward_machine.txt")
        for card_id in CARDS
    }
    check_machines(texts)
    absence, kill_two = LEFT_OUT
    left_out_cards = {
        c["id"]: c for c in json.loads((BENCH / "templates/tasks.json").read_text())["cards"]
    }
    farm_templates = ROOT / TEMPLATES / "farm"
    kill_two_texts = {
        "FARM": machine(f"{kill_two}-farm", farm_templates / kill_two / "reward_machine.txt"),
        "ARM-FM": machine(f"{kill_two}-arm-fm", ROOT / ARM_FM_KILL_TWO / "reward_machine.txt"),
    }
    absence_text = machine(f"{absence}-farm", farm_templates / absence / "reward_machine.txt")
    rejected = {
        card_id: machine(
            f"{card_id}-arm-fm", ROOT / ARM_FM_FORCING / card_id / "reward_machine.txt"
        )
        for card_id in CARDS
    }
    counted = arm_fm_attempts()
    arm_fm = arm_fm_section(runs_all, left_out_cards[kill_two], kill_two_texts, rejected, counted)
    bound = kill_reward_bound(cells)
    save_svgs("success", lambda theme: draw_success(cells, theme))
    return {
        "eyebrow": "Paper entry · zombie lanes · 2026-11-23",
        "title": "FARM in the zombie lanes, with the lanes moved closer",
        "subtitle": "With the lanes 2 or 1 rows apart, an agent paid by a reward machine holds the top lane "
        "better than one paid by the game's own reward. A third group adds the game's kill reward to "
        "the machine's pay: it does about as well on the top lane, except that on the rules card at "
        "spacing 4 two of its 3 runs fail every test episode. ARM-FM wrote no usable machine for the "
        "two cards.",
        "sections": [
            new_section(bound),
            setting_section(),
            summary_section(runs, runs_all, cells),
            task_section(cards, texts),
            setup_section(runs),
            lanes_section(runs),
            arm_fm,
            all_runs_section(runs),
            *closing_sections(runs_all, left_out_cards[absence], absence_text, counted[0], bound),
        ],
    }


def main() -> None:
    out = ENTRY / "data.json"
    out.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
