"""Print the LTLf of the clauses in the two worked examples (items w18 and w06 of the critic set).

Usage: PYTHONPATH=app python -W ignore example_ltlf.py     (run from the repository root)
No model call. The LTLf is the one the compiler hands to MONA, in the flat syntax.
"""

from pylogics.syntax.ltl import Atomic

from src.compiler.ltlf import to_flat_syntax
from src.engines.structured import SUPPORTED_TEMPLATES

EXAMPLES = {
    "w18, candidate (all hard)": [
        ("Existence", ("at_goal",)),
        ("Precedence", ("door_open", "at_goal")),
        ("Precedence", ("has_key", "door_open")),
        ("Existence", ("has_key",)),
    ],
    "w06, candidate (hard)": [("Precedence", ("at_exit", "switch_toggled"))],
    "w06, fixed (hard)": [("Precedence", ("switch_toggled", "at_exit"))],
}


def main() -> None:
    for name, clauses in EXAMPLES.items():
        print(name)
        for pattern, props in clauses:
            template, _ = SUPPORTED_TEMPLATES[pattern]
            ltlf = to_flat_syntax(template(*(Atomic(p) for p in props)).to_ltlf())
            print(f"  {pattern}({', '.join(props)}): {ltlf}")


if __name__ == "__main__":
    main()
