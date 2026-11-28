"""Collect what the page and the Reading quote from the judge files of the 96 shop two-jobs runs.

Run from the repository root with any Python 3 (reads outputs/runs and the shop task file):
    python -I docs/paper/shop-two-jobs/check/collect.py
Writes, in docs/paper/shop-two-jobs/data:
    judged.csv  one row per run: judged success, orders served, the environment's reward split into its
                positive and negative part (episode means over the 100 judged episodes) and the share of
                judged episodes in which each clause of the task holds
    tasks.json  per task: the RM bundle, the natural-language task, and the clauses with their LTLf, as the
                FARM judge files store them
Stops if the 12 FARM judge files of a task disagree on the bundle, the task text or the clauses, or if a task
text differs from the card's own text in the task file.
"""

import csv
import json
from pathlib import Path

RUNS = Path("outputs/runs")
TASK_FILE = Path("experiments/benchmark/shop/tasks.json")
OUT = Path("docs/paper/shop-two-jobs/data")
TASKS = {
    "serve-falls": "T1 serve + falls",
    "serve-siren": "T2 serve + siren",
    "full-falls": "T3 full serve + falls",
    "full-siren": "T4 full serve + siren",
}
SHOPS = ("3x3", "5x5", "7x7", "grow")
METHODS = {
    "farm": "bench__shop-two__{card}__farm__ppo",
    "no-rm": "bench__shop-two-reward__{card}__no-rm__ppo",
}


def judge_files(method: str, card: str) -> list[tuple[int, dict]]:
    """Run number and parsed judge file of each run of one card, in run order."""
    experiment = RUNS / METHODS[method].format(card=card)
    found = []
    for path in sorted(experiment.glob("seed*-*/judge.json")):
        run = int(path.parent.name.split("-")[0].removeprefix("seed"))
        found.append((run, json.loads(path.read_text(encoding="utf-8"))))
    return found


def card_texts() -> dict[str, str]:
    """Card id -> natural-language task, from the shop task file."""
    cards = json.loads(TASK_FILE.read_text(encoding="utf-8"))["cards"]
    return {card["id"]: card["task"] for card in cards}


def main() -> None:
    texts = card_texts()
    rows, tasks = [], {}
    for task, label in TASKS.items():
        facts = set()
        for shop in SHOPS:
            card = f"shop-two-{task}-{shop}"
            for method in METHODS:
                for run, judge in judge_files(method, card):
                    rates = " ".join(f"{rate:.2f}" for rate in judge["rule_pass_rates"])
                    rows.append(
                        [
                            method,
                            card,
                            run,
                            f"{judge['mean_judged_success']:.2f}",
                            f"{judge['mean_served_count']:.2f}",
                            f"{judge['mean_env_return_positive']:.3f}",
                            f"{judge['mean_env_return_negative']:.3f}",
                            rates,
                        ]
                    )
                    assert judge["task"] == texts[card], (
                        f"{card}: judge task differs from the task file"
                    )
                    if method == "farm":
                        clauses = [
                            (c["clause"], c["ltlf"]["raw"], c["ltlf"]["readable"])
                            for c in judge["expect"]
                        ]
                        facts.add(
                            (Path(judge["rm_bundle"]).name, judge["task"], json.dumps(clauses))
                        )
        assert len(facts) == 1, f"{task}: the FARM judge files disagree on bundle, task or clauses"
        bundle, text, clauses = facts.pop()
        assert texts[bundle] == text, (
            f"{bundle}: bundle card text differs from the judged task text"
        )
        tasks[task] = {
            "label": label,
            "bundle": bundle,
            "task": text,
            "clauses": [
                {
                    "template": c[0][0],
                    "args": c[0][1],
                    "priority": c[0][2],
                    "ltlf_raw": c[1],
                    "ltlf": c[2],
                }
                for c in json.loads(clauses)
            ],
        }

    assert len(rows) == 96, f"{len(rows)} judged runs, expected 96"
    with (OUT / "judged.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "method",
                "card",
                "run",
                "judged_success",
                "mean_served_count",
                "env_return_positive",
                "env_return_negative",
                "clause_pass_rates",
            ]
        )
        writer.writerows(rows)
    (OUT / "tasks.json").write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    print(f"96 judged runs; wrote {OUT / 'judged.csv'} and {OUT / 'tasks.json'}")


if __name__ == "__main__":
    main()
