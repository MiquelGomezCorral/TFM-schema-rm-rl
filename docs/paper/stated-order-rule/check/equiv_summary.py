"""Group equiv_check.py's mismatch rows: implied extras, other equivalent forms, different task.

Usage: python equiv_summary.py equiv-all.json
"""

import json
import sys
from collections import Counter
from pathlib import Path


def short(clause) -> str:
    template, names, priority = clause
    return f"{template}({', '.join(names)}){'' if priority == 'hard' else ' soft'}"


rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
mismatch = [row for row in rows if row.get("status") == "mismatch"]
groups = Counter()
for row in mismatch:
    name = row["bundle"].removeprefix("experiments/benchmark/").replace("/bundles/farm/", ": ")
    found = row["equivalent_to"]
    if not found:
        groups["different task"] += 1
        continue
    implied = [item for item in found if item["extra"] is not None]
    item = (implied or found)[0]
    kind = "implied extras" if implied else "equivalent, other clauses"
    groups[kind] += 1
    machine = item["machine"]
    rewards = (
        "same rewards"
        if not machine["rewards"]
        else f"{len(machine['rewards'])} reward differences"
    )
    extra = ", ".join(map(short, item["extra"])) if item["extra"] else "-"
    print(f"| {name} | {kind} | {item['answer']} | {extra} | {machine['structure']} | {rewards} |")
print(dict(groups), "errors:", [row["bundle"] for row in rows if "error" in row])
