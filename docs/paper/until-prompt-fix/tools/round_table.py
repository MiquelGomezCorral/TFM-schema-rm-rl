"""Round table for a run folder of the generator loop, one row per LABEL=FOLDER[@CASES].

    CC_ROOT=<W> PYTHONPATH=<W>/app python round_table.py LABEL=FOLDER[@a,b,c] [...]

Run it from this folder (its scorer modules sit beside it); local cards come from ../evidence/cards.

right / wrong: accepted machine right or not right (chain_score.classify); no machine: the run ended
without an accepted machine. first right: the first judged candidate. timeouts: logged calls whose
error names a timeout. >300 s ok: generator calls that took over 300 s and succeeded. reasoning max:
the largest reasoning-token count of one call, generator and critic.
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import arm_stats
import cases
import chain_score
import loopcrit


def row(folder: Path, only: set[str]) -> dict:
    n, walls, long_ok, longest = Counter(), [], [], 0.0
    reasoning = {"declare_proposal": [0], "critic": [0]}
    for path in sorted(folder.glob("*-r*.json")):
        case = path.stem.rsplit("-r", 1)[0]
        if case not in cases.ALL or (only and case not in only):
            continue
        record = json.loads(path.read_text())
        n["runs"] += 1
        walls.append(record.get("wall_s") or 0)
        if record.get("status") != "accepted":
            n["no_machine"] += 1
        elif chain_score.classify(case, record)[0] == "right":
            n["right"] += 1
        else:
            n["wrong"] += 1
        judged = list(loopcrit.verdicts(record))
        n["first_right"] += bool(judged) and arm_stats.score(case, judged[0][0]) == "right"
        log = path.with_suffix(".calls.jsonl")
        for line in log.read_text().splitlines() if log.exists() else []:
            call = json.loads(line)
            n["calls"] += 1 + (call.get("provider") or {}).get("resends", 0)
            error = (call.get("error") or "").lower()
            n["errors"] += bool(error)
            n["timeouts"] += "timeout" in error or "timed out" in error
            if call["stage"] == "declare_proposal" and not error:
                longest = max(longest, call["wall_s"])
                if call["wall_s"] > 300:
                    long_ok.append(f"{path.stem} {call['wall_s']:.0f}s")
            reasoning.setdefault(call["stage"], [0]).append(arm_stats.usage(call)[1])
    return {
        "runs": n["runs"],
        "right": n["right"],
        "wrong": n["wrong"],
        "no machine": n["no_machine"],
        "first right": f"{n['first_right']}/{n['runs']}",
        "calls": n["calls"],
        "call errors (timeouts)": f"{n['errors']} ({n['timeouts']})",
        "gen >300 s ok": f"{len(long_ok)}" + (f": {', '.join(long_ok)}" if long_ok else ""),
        "longest gen call s": f"{longest:.0f}",
        "wall s median (total)": f"{statistics.median(walls or [0]):.0f} ({sum(walls):.0f})",
        "reasoning max gen / critic": f"{max(reasoning['declare_proposal'])} / {max(reasoning['critic'])}",
    }


def main() -> None:
    rows = {}
    for spec in sys.argv[1:]:
        label, _, rest = spec.partition("=")
        folder, _, only = rest.partition("@")
        rows[label] = row(Path(folder), set(only.split(",")) if only else set())
    columns = list(next(iter(rows.values())))
    print("| round | " + " | ".join(columns) + " |")
    print("|---|" + "---|" * len(columns))
    for label, values in rows.items():
        print(f"| {label} | " + " | ".join(str(values[c]) for c in columns) + " |")


if __name__ == "__main__":
    main()
