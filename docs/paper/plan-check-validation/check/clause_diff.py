"""Print the scorer's verdict and the clauses a copy has beyond or below its card's expect. Read-only.

Usage (cwd = the main checkout): python clause_diff.py SUITE RM_FACTS_JSON
"""

import json
import sys
from pathlib import Path

from src.benchmark.cards import load_cards
from src.benchmark.rm_facts import _normalized


def as_set(clauses) -> set[str]:
    return {json.dumps(c) for c in _normalized(list(clauses)) or []}


def main() -> None:
    suite, facts_path = sys.argv[1], Path(sys.argv[2])
    cards = {
        c.id: c for c in load_cards(Path("experiments/benchmark") / suite / "tasks.json").cards
    }
    facts = json.loads(facts_path.read_text(encoding="utf-8"))["bundles"]
    for key, fact in sorted(facts.items()):
        card = cards[key.split("/", 1)[1].split("~", 1)[0]]
        stored, expect = as_set(fact.get("stored_clauses") or []), as_set(card.expect)
        print(f"== {key}: {fact.get('clause_check')}")
        print(f"   extra:   {sorted(stored - expect)}")
        print(f"   missing: {sorted(expect - stored)}")


if __name__ == "__main__":
    main()
