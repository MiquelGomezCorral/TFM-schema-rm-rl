"""Count the shop two-jobs FARM runs (suite shop-two) once the judge pass has written their judge.json.

Run from the repository root with any Python 3 (reads outputs/runs, writes docs/paper/shop-two-jobs/data):
    python -I docs/paper/shop-two-jobs/check/count_farm.py
Rules of the experiment: a run passes at mean_judged_success >= 0.8; a task is learned when
at least 2 of its 3 runs pass. Only `seed*-*/judge.json` files count (a run folder without one is unjudged).
Writes counts-farm.csv (one row per judged run, one per missing run) and counts-farm.md (the 16 cells).
"""

import csv
import json
from pathlib import Path

RUNS = Path("outputs/runs")
OUT = Path("docs/paper/shop-two-jobs/data")
PASS_AT = 0.8
LEARNED_AT = 2
SEEDS = (1, 2, 3)
TASKS = {
    "serve-falls": "T1 serve + falls",
    "serve-siren": "T2 serve + siren",
    "full-falls": "T3 full serve + falls",
    "full-siren": "T4 full serve + siren",
}
SHOPS = ("3x3", "5x5", "7x7", "grow")


def judged_runs(card: str) -> dict[int, list[float]]:
    """Run number -> the judged success of each judged folder of that run (one expected)."""
    found: dict[int, list[float]] = {}
    experiment = RUNS / f"bench__shop-two__{card}__farm__ppo"
    for judge in sorted(experiment.glob("seed*-*/judge.json")):
        seed = int(judge.parent.name.split("-")[0].removeprefix("seed"))
        success = json.loads(judge.read_text(encoding="utf-8"))["mean_judged_success"]
        found.setdefault(seed, []).append(success)
    return found


def main() -> None:
    rows, cells, notes = [], {}, []
    for task in TASKS:
        for shop in SHOPS:
            card = f"shop-two-{task}-{shop}"
            found = judged_runs(card)
            scores = {}
            for seed in SEEDS:
                values = found.get(seed, [])
                if len(values) > 1:
                    notes.append(f"{card} run {seed}: {len(values)} judged folders, first one used")
                if not values:
                    notes.append(f"{card} run {seed}: no judge.json")
                scores[seed] = values[0] if values else None
                passed = scores[seed] is not None and scores[seed] >= PASS_AT
                rows.append(
                    [card, seed, "" if scores[seed] is None else f"{scores[seed]:.2f}", int(passed)]
                )
            passes = sum(1 for v in scores.values() if v is not None and v >= PASS_AT)
            cells[(task, shop)] = (scores, passes, passes >= LEARNED_AT)

    with (OUT / "counts-farm.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["card", "seed", "judged_success", "pass"])
        writer.writerows(rows)

    def score_text(value: float | None) -> str:
        return "missing" if value is None else f"{value:.2f}"

    learned_total = sum(1 for cell in cells.values() if cell[2])
    lines = [
        "# Shop two jobs, FARM: runs passing and tasks learned",
        "",
        f"Suite `shop-two` (FARM, ppo-shop, 5M steps, 3 runs per card). A run passes at a judged success of "
        f"{PASS_AT} or more; a task is learned when {LEARNED_AT} of its 3 runs pass. Built by `count_farm.py` "
        "from the `judge.json` files; per-run rows in `counts-farm.csv`.",
        "",
        f"**Learned: {learned_total} of {len(cells)} cards.**",
        "",
        "## Cells: runs passing of 3, then learned",
        "",
        "| Task | " + " | ".join(SHOPS) + " |",
        "|---|" + "---|" * len(SHOPS),
    ]
    for task, label in TASKS.items():
        row = [
            f"{cells[(task, shop)][1]}/3 {'learned' if cells[(task, shop)][2] else 'no'}"
            for shop in SHOPS
        ]
        lines.append(f"| {label} | " + " | ".join(row) + " |")
    lines += [
        "",
        "## Judged success per run (runs 1, 2, 3)",
        "",
        "| Task | " + " | ".join(SHOPS) + " |",
        "|---|" + "---|" * len(SHOPS),
    ]
    for task, label in TASKS.items():
        row = [
            ", ".join(score_text(cells[(task, shop)][0][seed]) for seed in SEEDS) for shop in SHOPS
        ]
        lines.append(f"| {label} | " + " | ".join(row) + " |")
    lines += ["", "## Notes", ""]
    lines += [f"- {note}" for note in notes] or ["- All 48 runs judged, one judged folder per run."]
    (OUT / "counts-farm.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
