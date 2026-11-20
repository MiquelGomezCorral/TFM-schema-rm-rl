"""Rescore the generator loop from the slim records, with the original scorer.

    CC_ROOT=<repo root> PYTHONPATH=<repo root>/app python rescore.py v0=v0 v11=v11 --base=v0
    ... python rescore.py v6v7=v6,v7 v11=v11 --base=v6v7 --sets

The command line is the one of `chain_score.py` next to this file (the original scorer): `LABEL=FOLDER[,FOLDER...]`,
where each FOLDER is now a version name (a file `evidence/runs/<version>.json`). Only the
loader is replaced, and three filters are added: `--first=6` (runs r1-r6 of each case, the report's "42 cases x 6"),
`--no-soft` and `--soft-only` (the soft-last-step cases S1-S4). No model call. The cards come from the repository at CC_ROOT (`experiments/benchmark`) and
the soft-step cards from `evidence/cards/local-soft`.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import cases
import chain_score

EVIDENCE = Path(__file__).resolve().parent.parent / "evidence"

SOFT = ["S1", "S2", "S3", "S4"]


def option(name: str) -> str | None:
    """Pop `--name` or `--name=value` from the command line; return the value (or "1" for a bare flag)."""
    for arg in list(sys.argv):
        if arg == f"--{name}" or arg.startswith(f"--{name}="):
            sys.argv.remove(arg)
            return arg.partition("=")[2] or "1"
    return None


FIRST = int(
    option("first") or 0
)  # keep only runs r1..rK of each case (the report's "42 cases x 6")
SOFT_ONLY = option("soft-only")  # keep only the soft-last-step cases S1-S4
NO_SOFT = option("no-soft")  # drop the soft-last-step cases S1-S4


def load(folders):
    rows = defaultdict(list)
    for version in folders:
        for record in json.loads((EVIDENCE / "runs" / f"{version}.json").read_text()):
            case, _, run = record["file"].removesuffix(".json").rpartition("-r")
            if case not in cases.ALL or record.get("status") not in ("accepted", "failed"):
                continue
            if (
                (SOFT_ONLY and case not in SOFT)
                or (NO_SOFT and case in SOFT)
                or (FIRST and int(run) > FIRST)
            ):
                continue
            rows[case].append((Path(record["file"]), record, *chain_score.classify(case, record)))
    return rows


chain_score.load = load

if __name__ == "__main__":
    chain_score.main()
