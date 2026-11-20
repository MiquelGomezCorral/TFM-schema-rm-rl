"""Rescore the critic set from the slim records, with the original scorer.

    python rescore.py LABEL [LABEL ...]      e.g. python rescore.py k0 v3f

Prints the summary row per label, the flags by defect kind and the per-item table: the tables of
`score.py` next to this file, which is the original scorer. Only the loader is replaced, because the slim
records sit in one file per label (`evidence/runs/<label>.json`). No model call.
"""

import json
from pathlib import Path

import score

EVIDENCE = Path(__file__).resolve().parent.parent / "evidence"


def load(label: str) -> list[dict]:
    rows = json.loads((EVIDENCE / "runs" / f"{label}.json").read_text())
    return [r for r in rows if r.get("end") and r.get("calls") is not None]


score.load = load

if __name__ == "__main__":
    score.main()
