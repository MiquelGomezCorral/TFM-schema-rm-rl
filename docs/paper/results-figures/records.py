"""Numbers of the Results figures, recomputed from the records (no model call).

Every function reads the records it names and returns plain rows; ``make_figures.py`` asserts the
totals and writes the CSVs and the TeX. The learned rule is the final-results builder's (``outcome``,
``seed_learned``, ``TRAINABLE`` in ``.git/agent-memory/artifacts/final-results/build_results.py``); this file
never restates it.
"""

import contextlib
import csv
import io
import json
import statistics
from collections import Counter
from pathlib import Path

import arm_stats  # docs/paper/level-benchmark-freeze/check: the scorer behind its stats.md
from scipy.stats import t

from src.compiler import paper_to_structure, parse_paper_reward_machine

with contextlib.redirect_stdout(io.StringIO()):  # the builder prints its report on import
    import build_results as b

REPO = Path(__file__).resolve().parents[3]
LEVELS = ("none", "low", "medium", "high", "max")
LEVEL_RECORDS = REPO / "docs/paper/level-benchmark-freeze/records"
MODEL_LEVELS = REPO / "docs/paper/other-llms-by-level/data/levels.csv"
SOFT_RECORD = REPO / "docs/paper/soft-breaks-vs-idle/evidence/soft-breaks.json"
BENCH = REPO / "experiments/benchmark"
SHOP = ("shop", "shop-reward")
GROUPS = ("all", "step-by-step", "no goal", "with a goal", "shop")


# ========= Figure 1: machines built per arm =========
def built_after(attempts):
    """How a built bundle got through: copy of gen_rounds_armfm.py:built_after (reward-loops entry)."""
    statuses = {a["status"] for a in attempts}
    if "failed" in statuses and "rejected" in statuses:
        return "both"
    if "failed" in statuses:
        return "invalid"
    if "rejected" in statuses:
        return "rejected"
    return "first"


def built_counts():
    """Per arm: bundles asked, and how the built ones got through (first, rejected, invalid, both)."""
    out = {}
    for arm in ("farm", "arm-fm"):
        counts = Counter()
        for (suite, name), status in b.STATUS[arm].items():
            counts["asked"] += 1
            if status != "complete":
                counts["not built"] += 1
                continue
            attempts = json.loads((b.bundle_root(suite, arm) / name / "attempts.json").read_text())
            counts[built_after(attempts)] += 1
        out[arm] = counts
    return out


# ========= Figure 2: rows learned per arm and group =========
def kind_of(task):
    """``order`` for the step-by-step cards (hard Precedence and Existence only), else ``other``."""
    expect = task.get("expect") or []
    only_order = {pattern for pattern, _, _ in expect} <= {"Precedence", "Existence"}
    soft = any(priority == "soft" for _, _, priority in expect)
    return "order" if only_order and not soft else "other"


def groups_of(suite, task):
    """The Results chapter's sets a trained row belongs to (``all`` plus one of the other four)."""
    if suite in SHOP:
        return ("all", "shop")
    if kind_of(task) == "order":
        return ("all", "step-by-step")
    return ("all", "with a goal" if task.get("goal") else "no goal")


def learned_rows():
    """One row per trained card: its groups and the final-results outcome of each arm."""
    rows = []
    for suite, card in b.TRAINABLE:
        task = b.tasks(suite)[card]
        rows.append(
            {
                "suite": suite,
                "card": card,
                "groups": groups_of(suite, task),
                "outcome": {arm: b.outcome(suite, card, arm) for arm in b.ARMS},
            }
        )
    return rows


def learned_counts(rows):
    """{(group, arm): Counter(outcome)} over the rows."""
    counts = {(group, arm): Counter() for group in GROUPS for arm in b.ARMS}
    for row in rows:
        for group in row["groups"]:
            for arm in b.ARMS:
                counts[group, arm][row["outcome"][arm]] += 1
    return counts


# ========= Figure 3: soft breaks per judged episode =========
def seed_of(folder):
    return int(folder.name.split("-")[0].removeprefix("seed"))


def over_seeds(values):
    """Mean and 95% Student t interval over seeds; the low end is clipped at 0, a count is never below it."""
    mean = statistics.fmean(values)
    half = t.ppf(0.975, len(values) - 1) * statistics.stdev(values) / len(values) ** 0.5
    return mean, max(0.0, mean - half), mean + half


def soft_rows():
    """Return one row per soft-rule card, with its idle plan figure and per-arm seed values.

    The idle figure exists on soft-only cards. Per arm: the judge's per-seed ``mean_soft_break_count``
    (every broken step), or None where the arm has no judged run.
    """
    runs = {}
    for suite, card, arm, learner, folder in b.JUDGED:
        if learner == "ppo" and arm in b.ARMS:
            judge = json.loads((folder / "judge.json").read_text(encoding="utf-8"))
            runs.setdefault((suite, card, arm), []).append((seed_of(folder), judge))
    rows = []
    for suite, card in b.TRAINABLE:
        judges = [
            j for arm in ("farm", "no-rm", "arm-fm") for _, j in runs.get((suite, card, arm), [])
        ]
        if not b.old.soft_clauses(judges[0]):
            continue
        idle = b.IDLE_EVERY.get(f"{suite}/{card}")
        row = {
            "suite": suite,
            "card": card,
            "soft_only": bool(judges[0].get("soft_only")),
            "idle": None if idle is None else idle["soft_break_count"],
            "outcome_armfm": b.outcome(suite, card, "arm-fm"),
        }
        for arm in b.ARMS:
            seeds = sorted(runs.get((suite, card, arm), []), key=lambda run: run[0])
            row[arm] = [(seed, j["mean_soft_break_count"]) for seed, j in seeds] or None
        rows.append(row)
    return rows


def soft_record():
    """The checked record of the soft-breaks-vs-idle entry, by (suite, card)."""
    return {(r["suite"], r["card"]): r for r in json.loads(SOFT_RECORD.read_text(encoding="utf-8"))}


# ========= Figure 4: right machines per thinking level =========
def thinking_levels():
    """Per level: runs, right machines (the scorer's ``right``) and the median wall seconds per run."""
    rows = []
    for level in LEVELS:
        counts, walls, _, _ = arm_stats.arm([LEVEL_RECORDS / level])
        rows.append(
            {
                "level": level,
                "runs": counts["runs"],
                "right": counts["right"],
                "median_s": statistics.median(walls),
            }
        )
    return rows


def final_model_levels():
    """The ``final`` rows of the other-llms-by-level entry's levels.csv: one per model and level.

    Keys: model, level, runs, right, low, high (Wilson interval, shares 0 to 1) and median_s.
    """
    with MODEL_LEVELS.open(newline="", encoding="utf-8") as handle:
        return [
            {
                "model": row["model"],
                "level": row["level"],
                "runs": int(row["n"]),
                "right": int(row["right"]),
                "low": float(row["wilson_low"]),
                "high": float(row["wilson_high"]),
                "median_s": float(row["median_s_per_rm"]),
            }
            for row in csv.DictReader(handle)
            if row["final"] == "true"
        ]


# ========= Figure 5: the example machines, one arrow per pair of states =========
def merged_arrows(bundle):
    """Return the arrows of ``render-rm`` (``src/utils/visualization.py``) for one bundle.

    One arrow per state pair, with its reward or ``mixed`` and its number of transitions. Stays that
    pay nothing are left out.
    """
    paper = parse_paper_reward_machine((bundle / "reward_machine.txt").read_text(encoding="utf-8"))
    structure = paper_to_structure(paper)
    names = paper.states
    pairs = {}
    for tr in structure.transitions:
        if tr.source == tr.destination and tr.reward == 0:
            continue
        pairs.setdefault((names[tr.source], names[tr.destination]), []).append(tr.reward)
    arrows = [
        {
            "source": source,
            "target": target,
            "count": len(rewards),
            "rewards": sorted(set(rewards)),
        }
        for (source, target), rewards in pairs.items()
    ]
    return {
        "states": list(names),
        "initial": paper.initial_state,
        "final": list(paper.final_states),
        "rejecting": list(paper.rejecting_states),
        "arrows": arrows,
    }
