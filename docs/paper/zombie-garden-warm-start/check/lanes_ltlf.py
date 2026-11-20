"""Print the LTLf of the three clauses of the zombie garden card (`lanes-rules`).

Usage (from the repository root): PYTHONPATH=app python -W ignore docs/paper/zombie-garden-warm-start/check/lanes_ltlf.py
No model call. The LTLf is the one the compiler hands to MONA, in the flat syntax.
"""

from pylogics.syntax.ltl import Atomic

from src.compiler.ltlf import to_flat_syntax
from src.engines.structured import SUPPORTED_TEMPLATES

CLAUSES = [
    ("Absence", "top_breach", "hard"),
    ("Absence", "side_breach", "soft"),
    ("Absence", "plant_trampled", "soft"),
]


def main() -> None:
    for pattern, event, priority in CLAUSES:
        template, _ = SUPPORTED_TEMPLATES[pattern]
        print(f"{pattern}({event}) {priority}: {to_flat_syntax(template(Atomic(event)).to_ltlf())}")


if __name__ == "__main__":
    main()
