"""Count the shop two-jobs no-RM runs (suite shop-two-reward) once the judge pass has written their judge.json.

Run from the repository root with any Python 3 (reads outputs/runs and data/counts-farm.csv, writes
docs/paper/shop-two-jobs/data):
    python -I docs/paper/shop-two-jobs/check/count_no_rm.py
Same rules as count_farm.py: a run passes at mean_judged_success >= 0.8; a task is learned when at least 2 of
its 3 runs pass. Only `seed*-*/judge.json` files count (a run folder without one is unjudged). Writes
counts-no-rm.csv (one row per judged run, one per missing run, plus mean_served_count), counts-no-rm.md (the 16
cells) and counts-both.md (FARM from counts-farm.csv beside no RM).
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
# RM bundle that FARM's judge files name for each task (the no-RM runs train without one).
BUNDLES = {
    "serve-falls": "shop-ladder-deliver",
    "serve-siren": "shop-ladder-deliver-siren",
    "full-falls": "shop-serve",
    "full-siren": "shop-full",
}
SHOPS = ("3x3", "5x5", "7x7", "grow")


def judged_runs(card: str) -> dict[int, list[tuple[float, float | None]]]:
    """Run number -> (judged success, mean served count) of each judged folder of that run (one expected)."""
    found: dict[int, list[tuple[float, float | None]]] = {}
    experiment = RUNS / f"bench__shop-two-reward__{card}__no-rm__ppo"
    for judge in sorted(experiment.glob("seed*-*/judge.json")):
        seed = int(judge.parent.name.split("-")[0].removeprefix("seed"))
        data = json.loads(judge.read_text(encoding="utf-8"))
        found.setdefault(seed, []).append(
            (data["mean_judged_success"], data.get("mean_served_count"))
        )
    return found


def farm_passes() -> dict[str, int]:
    """Card -> runs passing of 3 for FARM, from counts-farm.csv."""
    passes: dict[str, int] = {}
    with (OUT / "counts-farm.csv").open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            passes[row["card"]] = passes.get(row["card"], 0) + int(row["pass"])
    return passes


def collect() -> tuple[list, dict, list[str]]:
    """CSV rows, the (task, shop) cells and the notes of the judged runs."""
    rows, cells, notes = [], {}, []
    for task in TASKS:
        for shop in SHOPS:
            card = f"shop-two-{task}-{shop}"
            found = judged_runs(card)
            scores, served = {}, {}
            for seed in SEEDS:
                values = found.get(seed, [])
                if len(values) > 1:
                    notes.append(f"{card} run {seed}: {len(values)} judged folders, first one used")
                if not values:
                    notes.append(f"{card} run {seed}: no judge.json")
                scores[seed], served[seed] = values[0] if values else (None, None)
                passed = scores[seed] is not None and scores[seed] >= PASS_AT
                rows.append(
                    [
                        card,
                        seed,
                        "" if scores[seed] is None else f"{scores[seed]:.2f}",
                        int(passed),
                        "" if served[seed] is None else f"{served[seed]:.2f}",
                    ]
                )
            passes = sum(1 for v in scores.values() if v is not None and v >= PASS_AT)
            cells[(task, shop)] = (scores, passes, passes >= LEARNED_AT, served)
    return rows, cells, notes


def write_no_rm(rows: list, cells: dict, notes: list[str]) -> int:
    """Write counts-no-rm.csv and counts-no-rm.md; return the number of learned cards."""
    with (OUT / "counts-no-rm.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["card", "seed", "judged_success", "pass", "mean_served_count"])
        writer.writerows(rows)

    def number_text(value: float | None) -> str:
        return "missing" if value is None else f"{value:.2f}"

    learned_total = sum(1 for cell in cells.values() if cell[2])
    lines = [
        "# Shop two jobs, no RM: runs passing and tasks learned",
        "",
        f"Suite `shop-two-reward` (no RM, env reward only, ppo-shop, 5M steps, 3 runs per card). A run passes at a "
        f"judged success of {PASS_AT} or more; a task is learned when {LEARNED_AT} of its 3 runs pass. Built by "
        "`count_no_rm.py` from the `judge.json` files; per-run rows in `counts-no-rm.csv`.",
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
            ", ".join(number_text(cells[(task, shop)][0][seed]) for seed in SEEDS) for shop in SHOPS
        ]
        lines.append(f"| {label} | " + " | ".join(row) + " |")
    lines += [
        "",
        "## Mean served count per run (runs 1, 2, 3)",
        "",
        "Orders served per judged episode, from `mean_served_count` in the judge file.",
        "",
        "| Task | " + " | ".join(SHOPS) + " |",
        "|---|" + "---|" * len(SHOPS),
    ]
    for task, label in TASKS.items():
        row = [
            ", ".join(number_text(cells[(task, shop)][3][seed]) for seed in SEEDS) for shop in SHOPS
        ]
        lines.append(f"| {label} | " + " | ".join(row) + " |")
    lines += ["", "## Notes", ""]
    lines += [f"- {note}" for note in notes] or ["- All 48 runs judged, one judged folder per run."]
    (OUT / "counts-no-rm.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return learned_total


def write_both(cells: dict, learned_total: int) -> None:
    """Write counts-both.md: FARM from counts-farm.csv beside no RM."""
    farm = farm_passes()
    farm_learned = 0
    both = [
        "# Shop two jobs: FARM against no RM",
        "",
        f"Same 16 cards, 3 runs each, ppo-shop, 5M steps. A run passes at a judged success of {PASS_AT} or more; "
        f"a task is learned when {LEARNED_AT} of its 3 runs pass. FARM trains with the RM bundle named in the first "
        "column, no RM trains without one. Grow is judged at 7x7. Sources: `counts-farm.csv`, `counts-no-rm.csv`.",
        "",
        "| Task | RM bundle (FARM) | Shop | FARM runs passing | FARM learned | No RM runs passing | No RM learned |",
        "|---|---|---|---|---|---|---|",
    ]
    for task, label in TASKS.items():
        for shop in SHOPS:
            farm_runs = farm[f"shop-two-{task}-{shop}"]
            farm_ok = farm_runs >= LEARNED_AT
            farm_learned += farm_ok
            _, no_rm_runs, no_rm_ok, _ = cells[(task, shop)]
            both.append(
                f"| {label} | `{BUNDLES[task]}` | {shop} | {farm_runs}/3 | {'learned' if farm_ok else 'no'} "
                f"| {no_rm_runs}/3 | {'learned' if no_rm_ok else 'no'} |"
            )
    both += [
        "",
        f"**Learned: FARM {farm_learned} of {len(cells)} cards, no RM {learned_total} of {len(cells)} cards.**",
    ]
    (OUT / "counts-both.md").write_text("\n".join(both) + "\n", encoding="utf-8")
    print("\n".join(both))


def main() -> None:
    rows, cells, notes = collect()
    write_both(cells, write_no_rm(rows, cells, notes))


if __name__ == "__main__":
    main()
