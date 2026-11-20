"""Count the pay-order sweep from `evidence/pay-order-sweep.json`.

Each row is one clause set (a card answer, `card`, or a stored bundle, `stored`) with its pay-order verdict on
the code before the chain-progress fix (`before`, main at `45c6747`) and on current main (`after`): "ok" or the
line that broke. `before` or `after` is null when the set did not exist at that commit.

Usage: python sweep_summary.py
"""

import json
from collections import Counter
from pathlib import Path

ROWS = json.loads(
    (Path(__file__).resolve().parent.parent / "evidence/pay-order-sweep.json").read_text()
)


def main() -> None:
    for kind in ("card", "stored"):
        rows = [r for r in ROWS if r["kind"] == kind]
        before = sum(r["before"] == "ok" for r in rows)
        after = sum(r["after"] == "ok" for r in rows)
        both = [r for r in rows if r["before"] and r["after"]]
        fixed = sum(r["before"] != "ok" and r["after"] == "ok" for r in both)
        lost = [r["name"] for r in both if r["before"] == "ok" and r["after"] != "ok"]
        print(
            f"{kind}: pass before {before}/{sum(r['before'] is not None for r in rows)}, "
            f"after {after}/{sum(r['after'] is not None for r in rows)}; fixed {fixed}, newly failing {len(lost)}"
        )
        for name in lost:
            print("   newly failing:", name)
        # a broken verdict is the pair of pay levels that failed, e.g. ["started", "not started"]
        still = Counter(" vs ".join(r["after"]) for r in rows if r["after"] not in ("ok", None))
        print("   still failing:", dict(still))


if __name__ == "__main__":
    main()
