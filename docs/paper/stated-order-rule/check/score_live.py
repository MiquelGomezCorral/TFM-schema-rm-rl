"""Score live bundles against one card with the card scorer and print a Markdown table row each.

Per bundle: the clauses with their LTLf, the scorer verdict, the first attempt flag and the RM path.
A bundle without stored clauses (generation failed) scores `missing`.

Usage: PYTHONPATH=<worktree>/app python score_live.py <tasks.json> <card-id> <bundle folder> ...
"""

import json
import sys
from pathlib import Path

from src.benchmark.cards import load_cards
from src.benchmark.declare_judge import ltlf_of
from src.benchmark.rm_facts import _normalized, clause_status


def main() -> None:
    tasks, card_id, *folders = sys.argv[1:]
    card = next(card for card in load_cards(Path(tasks)).cards if card.id == card_id)
    print(f"card {card_id}: {card.task}")
    print("| run | clauses | LTLf | verdict | attempt | RM path |")
    print("|---|---|---|---|---|---|")
    for folder in map(Path, folders):
        manifest_path = folder / "manifest.json"
        generation = {}
        if manifest_path.exists():
            generation = json.loads(manifest_path.read_text(encoding="utf-8")).get("generation", {})
        stored = _normalized(generation.get("clauses"))
        clauses = "; ".join(f"{t}({', '.join(n)})" for t, n, _ in stored or [])
        ltl = " & ".join(ltlf_of(tuple(c))["readable"] for c in stored or [])
        machine = folder / "reward_machine.txt"
        print(
            f"| {folder.name} | {clauses or '-'} | {ltl or '-'} | {clause_status(stored, card)} "
            f"| {generation.get('attempt', '-')} | {machine if machine.exists() else '-'} |"
        )


if __name__ == "__main__":
    main()
