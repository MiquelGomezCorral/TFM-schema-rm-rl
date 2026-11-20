"""Count final clauses whose `normalized_clause` text is a formula ("Precedence(a, b)") instead of words.

Usage: python docs/paper/hidden-output-schema/check/formula_text.py     (from the repository root)
No model call. Reads the `texts` field (one `normalized_clause` per final clause) of every run record:
loop 2 at low to max (before the fix) and the shape-fix rounds at max, high and none (after).
"""

import json
import re
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "evidence" / "runs"
TEMPLATES = "Existence|ExistenceTwo|Absence|Response|Precedence|ChainResponse|RespondedExistence|NotCoExistence"
FORMULA = re.compile(rf"^\s*({TEMPLATES})\s*\(")
ROUNDS = {
    "before (loop 2, low to max)": ["loop2-low", "loop2-medium", "loop2-high", "loop2-max"],
    "after (shape fix, max, high, none)": ["shape-max", "shape-high", "shape-none"],
}


def count(folders: list[str]) -> tuple[int, int, list[str]]:
    formulas, total, examples = 0, 0, []
    for folder in folders:
        for path in sorted((RUNS / folder / "A").glob("*-r*.json")):
            for text in json.loads(path.read_text()).get("texts") or []:
                total += 1
                if FORMULA.match(text):
                    formulas += 1
                    examples.append(f"{folder}/{path.stem}: {text}")
    return formulas, total, examples


def main() -> None:
    for label, folders in ROUNDS.items():
        formulas, total, examples = count(folders)
        print(f"{label}: {formulas} of {total} clause texts are formulas")
        for example in examples[:3]:
            print(f"  e.g. {example}")


if __name__ == "__main__":
    main()
