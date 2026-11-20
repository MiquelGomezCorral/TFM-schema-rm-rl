"""Compare two plan_check_all.py outputs: goal bundles must not change; list each no-goal verdict.

Usage: python compare_checks.py BEFORE.jsonl AFTER.jsonl
"""

import json
import sys
from pathlib import Path

VERDICT = {True: "pass", False: "FAIL", None: "unchecked"}


def rows(path: Path) -> dict:
    return {
        f"{row['suite']}/{row['key']}": row
        for row in map(json.loads, path.read_text().splitlines())
    }


def main() -> None:
    before, after = rows(Path(sys.argv[1])), rows(Path(sys.argv[2]))
    goal_changed = [
        key
        for key, row in before.items()
        if row.get("goal")
        and (row["passed"], row["problems"]) != (after[key]["passed"], after[key]["problems"])
    ]
    print(
        f"goal bundles: {sum(1 for r in before.values() if r.get('goal'))}, verdict or problems changed: {len(goal_changed)} {goal_changed[:5]}"
    )
    print("no-goal bundles (before -> after; first problem):")
    moves = {}
    for key, row in sorted(before.items()):
        if row.get("goal"):
            continue
        new = after[key]
        move = f"{VERDICT[row['passed']]} -> {VERDICT[new['passed']]}"
        moves[move] = moves.get(move, 0) + 1
        control = "" if row.get("control_same", True) else " (rebuild control differs)"
        print(
            f"  {key}: {move}{control} | before: {row['problems'][:1]} | after: {new['problems'][:1]}"
        )
    print("moves:", moves)


if __name__ == "__main__":
    main()
