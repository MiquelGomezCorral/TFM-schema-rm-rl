"""List the cards behind the generation table: id, suite, NL task, expected LTLf, machine paths.

Reads only the tracked `tasks.json` of each suite. A card with paraphrases gives one bundle per
paraphrase (`<id>~p<k>`, k from 1), generated from the paraphrase text with the card's clauses.
The LTLf is the card's expected clause list, the benchmark's reference; it is not what a model
compiled. Run from the repository root inside `RM_RL_env`:

    PYTHONPATH=app python -W ignore docs/paper/generation-table/check/cards_list.py <output.md>

No bundle is read, so the counts can be compared with the table: bundles per arm.
"""

import json
import sys
from pathlib import Path

from src.benchmark.declare_judge import as_clause, ltlf_of

ROOT = Path("experiments/benchmark")
SUITES = ("base", "complex", "templates", "box-carry", "forced-start", "pilot")


def names(card: dict, with_paraphrases: bool) -> list[tuple[str, str]]:
    """(bundle name, NL task) for the card and, when asked, each paraphrase."""
    out = [(card["id"], card["task"])]
    if with_paraphrases:
        out += [
            (f"{card['id']}~p{k}", text) for k, text in enumerate(card.get("paraphrases", ()), 1)
        ]
    return out


def ltl_of(card: dict) -> str:
    return "; ".join(ltlf_of(as_clause(clause))["readable"] for clause in card["expect"])


def main(output: Path) -> None:
    lines = ["# Cards behind the generation table", ""]
    total = 0
    for suite in SUITES:
        cards = json.loads((ROOT / suite / "tasks.json").read_text(encoding="utf-8"))["cards"]
        # pilot cards were generated without paraphrases, the other suites with them
        rows = [
            (card, name, text) for card in cards for name, text in names(card, suite != "pilot")
        ]
        total += len(rows)
        arms = "farm" if suite == "pilot" else "{arm-fm,farm}"
        lines += [
            f"## {suite}: {len(rows)} bundles per arm"
            if suite != "pilot"
            else f"## pilot: {len(rows)} bundles (FARM only)",
            "",
            f"Machine of a row: `experiments/benchmark/{suite}/bundles/{arms}/<bundle>/reward_machine.txt`.",
            "",
            "| bundle | NL task | expected LTLf |",
            "|---|---|---|",
        ]
        for card, name, text in rows:
            lines.append(f"| `{name}` | {text} | {ltl_of(card)} |")
        lines.append("")
    lines.append(f"Total: {total} bundle names.")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {output}: {total} bundle names")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
