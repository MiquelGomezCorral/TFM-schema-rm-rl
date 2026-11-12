"""Build the results page (``data.json``) of the PPO diagnostic from the CSVs ``analyze.py`` wrote.

Every number in the grids and tables comes from ``runs.csv`` and ``variants.csv``. The prose
(answers, captions, recommendation) is read from ``page-text.json`` in the same folder, written
by hand after reading the tables. Render and publish the page with the ``agent-artifacts``
skill (``fill.py data.json index.html``, then ``hub.py publish``).

Usage (from the repo root):
    python experiments/benchmark/tuning/ppo-diagnostic/build_page.py <artifact folder>
"""

import argparse
import json
from pathlib import Path

import pandas as pd

SEEDS = [1, 2, 3, 4, 21]
SOLVED = 0.8  # a seed counts as solved when its final greedy success is at least this
PLANNED = 45  # 20 main + 10 exploration on s07-tuned + 10 on s07 + 5 DoorKey
NO_RUN = {"icon": "circle-dashed", "text": "-", "tone": "muted", "title": "not run, or not started"}
# (group title, [(card, variant, row label, row note)]) in the order the matrix shows them.
GRID = [
    (
        "Base settings, UnlockPickup",
        [
            ("base-unlock-pickup", "rm", "rm", "s07, Reward Machine reward"),
            ("base-unlock-pickup", "env", "env", "s07, environment reward only"),
            ("base-unlock-pickup", "rm-tuned", "rm-tuned", "s07-tuned, Reward Machine"),
            ("base-unlock-pickup", "env-tuned", "env-tuned", "s07-tuned, environment only"),
        ],
    ),
    (
        "Exploration on s07",
        [
            ("base-unlock-pickup", "rm", "rm", "reference, no exploration change"),
            ("base-unlock-pickup", "rm-epsilon", "rm-epsilon", "C: forced random start"),
            ("base-unlock-pickup", "rm-entropy", "rm-entropy", "A: entropy 0.05 to 0.01"),
        ],
    ),
    (
        "Exploration on s07-tuned",
        [
            ("base-unlock-pickup", "rm-tuned", "rm-tuned", "reference, no exploration change"),
            (
                "base-unlock-pickup",
                "rm-tuned-epsilon",
                "rm-tuned-epsilon",
                "C: forced random start",
            ),
            (
                "base-unlock-pickup",
                "rm-tuned-entropy",
                "rm-tuned-entropy",
                "A: entropy 0.05 to 0.01",
            ),
        ],
    ),
    (
        "DoorKey 8x8, 500k steps",
        [("base-doorkey", "env", "env", "s07, environment reward only")],
    ),
]
FIGURES = [
    ("success-settings", 880),
    ("training-settings", 660),
    ("success-explore-s07", 760),
    ("training-explore-s07", 660),
    ("success-explore-tuned", 760),
    ("training-explore-tuned", 660),
    ("success-doorkey-env", 360),
]


def k(value: float) -> str:
    """Steps in thousands, or ``never`` for a missing step."""
    return "never" if value != value else f"{value / 1000:.0f}k"


def run_chip(run: pd.Series) -> dict:
    """The grid chip of one run: final greedy / sampled success, details on hover."""
    finished = run["status"] == "finished"
    solved = run["final_greedy"] >= SOLVED
    if not finished:
        icon, tone = "loader-circle", "info"
    else:
        icon, tone = ("circle-check", "ok") if solved else ("circle-x", "bad")
    title = (
        f"first solve: greedy {k(run['first_solve_greedy'])}, sampled {k(run['first_solve_sampled'])}; "
        f"success 0.8: greedy {k(run['to_0.8_greedy'])}, sampled {k(run['to_0.8_sampled'])}"
    )
    if run["reach_key"] == run["reach_key"]:
        title += (
            f"; training reached key {run['reach_key']:.0%}, door {run['reach_door']:.0%}, "
            f"box {run['reach_last']:.0%} (last 200k steps)"
        )
    if not finished:
        title = f"running, {run['steps_logged'] // 1000}k steps so far; " + title
    return {
        "icon": icon,
        "text": f"{run['final_greedy']:.0%} / {run['final_sampled']:.0%}",
        "tone": tone,
        "title": title,
    }


def matrix_block(runs: pd.DataFrame) -> dict:
    """The seed grid: one row per variant, one column per seed, one chip per run."""
    groups = []
    for title, rows in GRID:
        group_rows = []
        for card, variant, label, note in rows:
            cells = []
            for seed in SEEDS:
                hit = runs[
                    (runs["card"] == card) & (runs["variant"] == variant) & (runs["seed"] == seed)
                ]
                cells.append([run_chip(hit.iloc[0])] if len(hit) else [NO_RUN])
            group_rows.append({"label": label, "note": note, "cells": cells})
        groups.append({"title": title, "rows": group_rows})
    return {
        "type": "matrix",
        "heading": "Final success per seed: greedy / sampled, 100 fixed layouts",
        "legend": [
            {"icon": "circle-check", "text": "greedy success 80% or more", "tone": "ok"},
            {"icon": "circle-x", "text": "below 80%", "tone": "bad"},
            {"icon": "loader-circle", "text": "still training", "tone": "info"},
            {"icon": "circle-dashed", "text": "not run", "tone": "muted"},
        ],
        "columns": [f"seed {seed}" for seed in SEEDS],
        "groups": groups,
    }


def variants_block(variants: pd.DataFrame) -> dict:
    """The per-variant table: solved seeds and medians over the seeds that have the number."""
    rows = []
    for _, r in variants.iterrows():
        rows.append(
            [
                "DoorKey" if r["card"] == "base-doorkey" else "UnlockPickup",
                r["variant"],
                f"{r['finished']} of {r['seeds']} done",
                f"{r['solved_greedy']} of {r['seeds']}",
                f"{r['solved_sampled']} of {r['seeds']}",
                k(r["median_first_solve_greedy"]),
                f"{k(r['median_to_0.8_greedy'])} / {k(r['median_to_0.8_sampled'])}",
                k(r["latest_to_0.8_greedy"]),
                f"{r['mean_final_greedy']:.0%} / {r['mean_final_sampled']:.0%}",
            ]
        )
    return {
        "type": "table",
        "heading": "Per variant (medians and the latest are over the seeds that get there)",
        "columns": [
            "Card",
            "Variant",
            "Seeds",
            "Solved (greedy)",
            "Solved (sampled)",
            "Median first greedy solve",
            "Median steps to 0.8, greedy / sampled",
            "Latest steps to 0.8, greedy",
            "Mean final, greedy / sampled",
        ],
        "rows": rows,
    }


def health_block(variants: pd.DataFrame) -> dict:
    """Policy drift, clipped share and critic fit per variant, first 500k steps."""
    rows = [
        [
            r["variant"] + (" (DoorKey)" if r["card"] == "base-doorkey" else ""),
            f"{r['kl_early']:.3f}",
            f"{r['clipfrac_early']:.2f}",
            f"{r['explained_variance_early']:.2f}",
        ]
        for _, r in variants.iterrows()
    ]
    return {
        "type": "table",
        "heading": "Optimizer health, mean over the first 500k steps",
        "columns": [
            "Variant",
            "Policy drift per update (approx KL)",
            "Samples at the clip",
            "Critic fit (explained variance; 1 is perfect, 0 is no better than the mean)",
        ],
        "rows": rows,
    }


def runs_block(runs: pd.DataFrame) -> dict:
    """One line per run: first solve and steps to 80% (sampled and greedy), final score, reach."""
    rows = []
    for _, r in runs.iterrows():
        icon, tone = (
            ("loader-circle", "info")
            if r["status"] != "finished"
            else ("circle-check", "ok")
            if r["final_greedy"] >= SOLVED
            else ("circle-x", "bad")
        )
        reach = (
            "-"
            if r["reach_key"] != r["reach_key"]
            else f"{r['reach_key']:.0%} / {r['reach_door']:.0%} / {r['reach_last']:.0%}"
        )
        rows.append(
            [
                "DoorKey" if r["card"] == "base-doorkey" else "UnlockPickup",
                r["variant"],
                str(r["seed"]),
                {"icon": icon, "text": r["status"], "tone": tone},
                k(r["first_solve_sampled"]),
                k(r["first_solve_greedy"]),
                f"{k(r['to_0.8_sampled'])} / {k(r['to_0.8_greedy'])}",
                f"{r['final_greedy']:.0%} / {r['final_sampled']:.0%}",
                f"{r['entropy_final']:.2f}",
                reach,
            ]
        )
    return {
        "type": "table",
        "heading": "All runs",
        "columns": [
            "Card",
            "Variant",
            "Seed",
            "Status",
            "First sampled solve",
            "First greedy solve",
            "Steps to 80%: sampled / greedy",
            "Final greedy / sampled",
            "Final entropy",
            "Training reached key / door / box (last 200k)",
        ],
        "rows": rows,
    }


def random_block(data: Path) -> dict:
    """The random-agent chance rates, with the shape of the two cards."""
    chance = pd.read_csv(data / "random_agent.csv")
    lengths = pd.read_csv(data / "random_agent_lengths.csv").set_index("card")
    by_card = {card: group.set_index("step") for card, group in chance.groupby("card")}
    rows = []
    for card, label in (("base-unlock-pickup", "UnlockPickup"), ("base-doorkey", "DoorKey 8x8")):
        steps = by_card[card]
        cells = [
            f"{steps.loc[step, 'rate']:.1%} ({steps.loc[step, 'ci95_low']:.1%} to {steps.loc[step, 'ci95_high']:.1%})"
            for step in ("key", "door", "success")
        ]
        rows.append([label, *cells, f"{lengths.loc[card, 'mean_length']:.0f}"])
    return {
        "type": "table",
        "heading": "A random agent, 2000 episodes per card",
        "columns": ["Card", "Gets the key", "Opens the door", "Solves it", "Mean episode length"],
        "rows": rows,
    }


def cards_section(folder: Path) -> dict:
    """The section that shows, per card, the NL task, the LTL, and the interactive RM graph."""
    infos = json.loads((folder / "cards.json").read_text(encoding="utf-8"))
    cards = [{"card": card, **info} for card, info in infos.items()]
    names = {"base-unlock-pickup": "UnlockPickup", "base-doorkey": "DoorKey 8x8"}
    return {
        "id": "tasks",
        "title": "The tasks, as language, logic and Reward Machine",
        "intro": "Every result above is for one of these two tasks. The language task is what the user wrote; "
        "the logic lines are the card's reference clauses (the specification the compiled machine should satisfy); "
        "the Reward Machine is the compiled bundle that gives the training reward.",
        "blocks": [
            {
                "type": "cards",
                "items": [
                    {
                        "title": names[c["card"]],
                        "icon": "target",
                        "text": f"**Language task:** {c['task']}",
                        "inset": "**Reference LTL clauses:**\n"
                        + "\n".join(f"- {clause}" for clause in c["clauses"]),
                    }
                    for c in cards
                ],
            },
            {
                "type": "gallery",
                "heading": "Reward Machine graphs (hover and drag; the text folds out below each)",
                "width": 490,
                "items": [
                    {
                        "src": f"rm/{c['card']}.html",
                        "height": 380,
                        "caption": f"{names[c['card']]} Reward Machine",
                        "details": {"title": "RM text", "code": c["rm"]},
                    }
                    for c in cards
                ],
            },
        ],
    }


def build(folder: Path) -> dict:
    """The page data for ``folder`` (the artifact folder analyze.py wrote into)."""
    runs = pd.read_csv(folder / "runs.csv")
    variants = pd.read_csv(folder / "variants.csv")
    text = json.loads((folder / "page-text.json").read_text(encoding="utf-8"))
    finished = int((runs["status"] == "finished").sum())
    unlock = runs[runs["card"] == "base-unlock-pickup"]
    stats = [
        {"value": f"{finished} of {PLANNED}", "label": "runs finished", "tone": "info"},
        {"value": str(int(((unlock["final_greedy"] >= SOLVED) & (unlock["status"] == "finished")).sum())),
         "label": "UnlockPickup runs solved (greedy 80% or more)", "tone": "ok"},
        {"value": str(int(((unlock["final_greedy"] < SOLVED) & (unlock["status"] == "finished")).sum())),
         "label": "UnlockPickup runs not solved", "tone": "bad"},
    ]  # fmt: skip
    figures = [
        {
            "type": "figure",
            "src": f"plots/{name}.html",
            "height": height,
            "caption": text["captions"].get(name, ""),
        }
        for name, height in FIGURES
        if (folder / "plots" / f"{name}.html").is_file()
    ]
    return {
        "eyebrow": text["eyebrow"],
        "title": text["title"],
        "subtitle": text["subtitle"],
        "sections": [
            {
                "id": "answers",
                "title": "The five answers",
                "blocks": [
                    {"type": "stats", "items": stats},
                    {"type": "list", "ordered": True, "items": text["answers"]},
                    {
                        "type": "callout",
                        "title": "Recommendation",
                        "tone": "info",
                        **text["recommendation"],
                    },
                ],
            },
            {
                "id": "runs",
                "title": "Every run",
                "intro": text["runs_intro"],
                "blocks": [
                    matrix_block(runs),
                    variants_block(variants),
                    runs_block(runs),
                    health_block(variants),
                ],
            },
            {"id": "curves", "title": "Curves", "intro": text["curves_intro"], "blocks": figures},
            {
                "id": "chance",
                "title": "What chance alone does",
                "intro": text["chance_intro"],
                "blocks": [random_block(folder / "data")],
            },
            cards_section(folder),
            {
                "id": "notes",
                "title": "Notes",
                "collapsed": True,
                "blocks": [{"type": "details", "items": text["notes"]}],
            },
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the PPO diagnostic page data.")
    parser.add_argument(
        "folder", type=Path, help="artifact folder holding runs.csv and page-text.json"
    )
    arguments = parser.parse_args()
    page = build(arguments.folder)
    (arguments.folder / "data.json").write_text(json.dumps(page, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {arguments.folder / 'data.json'}")
