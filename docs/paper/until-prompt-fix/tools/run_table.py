"""Per-run table: NL task, LTLf, clauses, verdict and critic trail of every run in the folders.

    CC_ROOT=<W> PYTHONPATH=<W>/app python run_table.py FOLDER [FOLDER...] [--cases a,b]

Run it from this folder (its scorer modules sit beside it); local cards come from ../evidence/cards.
Verdicts come from chain_score.classify against the cards. candidates: each judged candidate in
order, R/A/W by the same scorer, with + accepted / - rejected. calls: logged model requests.
"""

import json
import sys
from pathlib import Path

import arm_stats
import cases
import chain_score
import loopcrit

from src.utils import ltlf_of

LETTER = {"right": "R", "accepted": "A", "wrong": "W"}


def main() -> None:
    args = sys.argv[1:]
    only = set(args.pop(args.index("--cases") + 1).split(",")) if "--cases" in args else set()
    folders = [Path(a) for a in args if a != "--cases"]
    print("| run | NL task | LTLf | clauses | verdict | candidates | calls | wall s |")
    print("|---|---|---|---|---|---|---|---|")
    for folder in folders:
        for path in sorted(folder.glob("*-r*.json")):
            case = path.stem.rsplit("-r", 1)[0]
            if case not in cases.ALL or (only and case not in only):
                continue
            record = json.loads(path.read_text())
            verdict, tag, shown = chain_score.classify(case, record)
            ltlf = "; ".join(ltlf_of(t, n) for t, n, _ in record.get("clauses") or []) or "-"
            trail = " ".join(
                LETTER[arm_stats.score(case, c)] + ("+" if ok else "-")
                for c, ok in loopcrit.verdicts(record)
            )
            log = path.with_suffix(".calls.jsonl")
            calls = len(log.read_text().splitlines()) if log.exists() else 0
            status = verdict if verdict != "wrong" or tag != "failed" else f"no machine ({shown})"
            print(
                f"| {folder.name}/{path.stem} | {record.get('task')} | `{ltlf}` | `{shown}` | {status} "
                f"| {trail or '-'} | {calls} | {record.get('wall_s')} |"
            )


if __name__ == "__main__":
    main()
