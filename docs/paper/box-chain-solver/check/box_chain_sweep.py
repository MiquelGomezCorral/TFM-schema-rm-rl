"""Does each event-room card's own solving plan pass the card's own judge? Seeds 1 to 50, no provider call.

Run from the root of a repository tree (the script reads `experiments/benchmark/*/tasks.json` and imports `src`):

    PYTHONPATH=app python box_chain_sweep.py <output.json>

For every card on `MiniGrid-ServiceRoom-v0` it plays the card's `solve` plan on seeds 1 to 50 and judges the
labels with the card's `expect` clauses. A miss is a run the judge does not call a success. It also plays a
direct walk to the exit (no box) and counts how many of those the judge passes. Derived from the reviewer's
`event_sweep` and `box_check.py` of the card-fix-2 work.
"""

import json
import sys
from pathlib import Path

from src.benchmark.declare_judge import as_clause, judge_trace
from src.benchmark.plans import run_plan

CARDS = {
    c["id"]: c
    for suite in ("base", "templates", "complex")
    for c in json.loads(Path(f"experiments/benchmark/{suite}/tasks.json").read_text())["cards"]
}
ROOM = [c for c in CARDS.values() if c["env"]["gym_id"] == "MiniGrid-ServiceRoom-v0"]
DIRECT_EXIT = [{"do": "goto", "obj": "exit"}]


def main() -> None:
    rows = []
    for card in ROOM:
        clauses = [as_clause(c) for c in card["expect"]]
        misses, direct_pass, falls = [], 0, 0
        for seed in range(1, 51):
            solved = run_plan(card["env"], card["plans"]["solve"], seed)
            judged = judge_trace(clauses, solved.labels)
            falls += sum(bool(step.get("box_fell")) for step in solved.labels)
            if not judged.success:
                misses.append({"seed": seed, "verdicts": judged.to_dict()["verdicts"]})
            direct_pass += judge_trace(
                clauses, run_plan(card["env"], DIRECT_EXIT, seed).labels
            ).success
        rows.append(
            {
                "id": card["id"],
                "task": card["task"],
                "expect": card["expect"],
                "runs": 50,
                "solve_misses": len(misses),
                "direct_exit_passes": direct_pass,
                "box_falls_in_solve_runs": falls,
                "first_misses": misses[:3],
            }
        )
    total = {
        "cards": len(rows),
        "runs": 50 * len(rows),
        "solve_misses": sum(r["solve_misses"] for r in rows),
    }
    report = {"total": total, "cards": rows}
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(
            f"{row['id']:34s} solve misses {row['solve_misses']:2d}/50   direct exit passes {row['direct_exit_passes']:2d}/50"
        )
    print(
        f"total: {total['solve_misses']} solve misses over {total['runs']} runs on {total['cards']} cards"
    )


if __name__ == "__main__":
    main()
