"""Compare two pay-order sweep files row by row: every verdict change, and every summary change.

Usage: python compare.py BEFORE.jsonl AFTER.jsonl
Rows are keyed by ``name`` (chain-progress sweep) or ``suite/card answer`` (card sweep).
"""

import json
import sys
from pathlib import Path


def key(row):
    return row.get("name") or f"{row['suite']}/{row['card']} {row['answer']}"


def load(path):
    with Path(path).open() as lines:
        return {key(row): row for row in map(json.loads, lines)}


def main():
    before, after = load(sys.argv[1]), load(sys.argv[2])
    assert before.keys() == after.keys(), "the two sweeps cover different rows"
    flips, texts = [], []
    for name in before:
        old, new = before[name], after[name]
        if old.get("ok") != new.get("ok"):
            flips.append((name, old.get("summary"), new.get("summary")))
        elif old.get("summary") != new.get("summary"):
            texts.append((name, old.get("summary"), new.get("summary")))
    print(
        f"rows {len(before)}; ok before {sum(r.get('ok', False) for r in before.values())}, "
        f"after {sum(r.get('ok', False) for r in after.values())}; verdict changes {len(flips)}; "
        f"summary-only changes {len(texts)}"
    )
    for title, rows in (("VERDICT CHANGES", flips), ("SUMMARY-ONLY CHANGES", texts)):
        print(f"\n== {title} ==")
        for name, old, new in rows:
            print(f"{name}\n  before: {old}\n  after:  {new}")


if __name__ == "__main__":
    main()
