"""Check one-holding-step negatives across procedural layouts.

Run from the root of a repository tree: PYTHONPATH=app python count_negatives.py <output dir>
"""

import json
import sys
from pathlib import Path

from src.benchmark.declare_judge import as_clause, judge_trace
from src.benchmark.plans import run_plan

cards = json.loads(Path("experiments/benchmark/templates/tasks.json").read_text())["cards"]
rows = []
for card in cards:
    if card["id"] not in ("tpl-existence-two-2-nogoal", "tpl-existence-two-3-nogoal"):
        continue
    for seed in range(1, 51):
        rollout = run_plan(card["env"], card["plans"]["wrong"][0]["steps"], seed)
        rows.append(
            {
                "id": card["id"],
                "seed": seed,
                "failed": judge_trace(
                    [as_clause(c) for c in card["expect"]], rollout.labels
                ).failed(),
                "held_steps": sum(s[card["expect"][0][1][0]] for s in rollout.labels),
                "actions": rollout.actions,
            }
        )
Path(sys.argv[1]).mkdir(parents=True, exist_ok=True)
Path(sys.argv[1], "count-negatives.json").write_text(json.dumps(rows, indent=2) + "\n")
bad = [r for r in rows if not r["failed"]]
print(
    json.dumps(
        {
            "runs": len(rows),
            "false_negatives": len(bad),
            "by_card": {
                i: sum(1 for r in bad if r["id"] == i) for i in sorted({r["id"] for r in rows})
            },
            "seeds": [(r["id"], r["seed"], r["held_steps"]) for r in bad],
        },
        indent=2,
    )
)
