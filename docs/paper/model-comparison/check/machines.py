"""Print task, clauses and LTLf of the machines the page draws, from their run records.

Usage: PYTHONPATH=app python -W ignore docs/paper/model-comparison/check/machines.py     (from the repository root)
No model call. The LTLf is the one the compiler hands to MONA, in the flat syntax. Each record is the run that
built the machine; its RM text is `graphs/<name>.rm`.
"""

import json
from pathlib import Path

from pylogics.syntax.ltl import Atomic

from src.compiler.ltlf import to_flat_syntax
from src.engines.structured import SUPPORTED_TEMPLATES

ENTRY = Path(__file__).resolve().parent.parent
RUNS = ENTRY / "evidence"
MACHINES = {
    "none-W5a": "model-compare/runs/r1/A/W5a-r1",
    "medium-W5a": "llm-loop/runs/b4/A/W5a-r1",
    "none-U5": "model-compare/runs/r1/A/U5-r1",
    "medium-U5": "llm-loop/runs/b4/A/U5-r1",
    "none-S2": "model-compare/runs/r1/A/S2-r1",
    "medium-S2": "llm-loop/runs/b4/A/S2-r1",
    "none-O7": "model-compare/runs/r1/A/O7-r1",
    "medium-O7": "llm-loop/runs/b4/A/O7-r1",
    "oldcard-G12": "model-compare/runs/r1b/B/G12-r1",
    "medium-G12": "llm-loop/runs/b4/A/G12-r1",
}


def describe(name: str) -> dict:
    """Task, status and the clauses with their LTLf for one machine."""
    record = json.loads((RUNS / f"{MACHINES[name]}.json").read_text())
    clauses = []
    for pattern, props, priority in record["clauses"]:
        template, _ = SUPPORTED_TEMPLATES[pattern]
        ltlf = to_flat_syntax(template(*(Atomic(p) for p in props)).to_ltlf())
        clauses.append(
            {"clause": f"{pattern}({', '.join(props)})", "priority": priority, "ltlf": ltlf}
        )
    return {"task": record["task"], "status": record["status"], "clauses": clauses}


def main() -> None:
    for name in MACHINES:
        info = describe(name)
        print(f"{name}  [{info['status']}]  {info['task']}")
        for c in info["clauses"]:
            print(f"  {c['priority']:4} {c['clause']}: {c['ltlf']}")


if __name__ == "__main__":
    main()
