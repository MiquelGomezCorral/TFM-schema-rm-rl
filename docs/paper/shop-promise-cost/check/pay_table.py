"""Part 2 table: per shop level, the solving plan and every well plan, before and after, seed by seed.

Usage: python pay_table.py BEFORE.json AFTER.json
"""

import json
import sys
from pathlib import Path


def well_plans(level):
    return [
        name
        for name, seeds in level["plans"].items()
        if any(r["end"].startswith("well") for r in seeds.values())
    ]


def cell(run):
    return f"{run['plain']:g} / {run['discounted']:g}"


def main() -> None:
    before = {level["label"]: level for level in json.loads(Path(sys.argv[1]).read_text())}
    after = {level["label"]: level for level in json.loads(Path(sys.argv[2]).read_text())}
    print(
        "| level | promise | plan | seed | before plain / disc | after plain / disc | below solve after |"
    )
    print("|---|---|---|---|---|---|---|")
    for label, old in before.items():
        new = after[label]
        card, promise = old["card"], "on" if old["switches"]["reward_promise_cost"] else "off"
        for name in ["solve", *well_plans(old)]:
            for seed, run in old["plans"][name].items():
                fresh = new["plans"][name][seed]
                solve = new["plans"]["solve"][seed]
                below = (
                    ""
                    if name == "solve"
                    else str(
                        fresh["plain"] < solve["plain"]
                        and fresh["discounted"] < solve["discounted"]
                    )
                )
                print(
                    f"| {card} | {promise} | {name} | {seed} | {cell(run)} | {cell(fresh)} | {below} |"
                )


if __name__ == "__main__":
    main()
