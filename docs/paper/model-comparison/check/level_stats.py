"""Per reasoning level: the arm_stats row plus the sweep columns of the loop-2 report.

    CARD_DIR=<cards> CC_ROOT=$PWD PYTHONPATH=app:<check> python <check>/level_stats.py \
        LABEL=FOLDER[,FOLDER...] [LABEL=...] [--cases a,b]

Extra columns, per label:
- short first: first proposals that are not right and have fewer clauses than the smallest correct
  answer of the card (`expect` without its forced clauses, or any `also_ok` set).
- wall per run: median and total, every record (failed and errored runs too).
- tokens per call: median and max output tokens, and median and max reasoning tokens, per stage.
- errors: logged calls that raised, of them timeouts, refused sends (resends inside calls), provider
  reruns of whole requests, and records that ended without an accepted machine (by status).
--cases a,b keeps only those cases, so two rounds compare on the same cases.
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import arm_stats
import cases
import loopcrit


def smallest_answer(case):
    card = cases.card_of(case)
    sizes = [len([c for i, c in enumerate(card.expect) if i not in card.forced])]
    sizes += [len(answer) for answer in card.also_ok]
    return min(sizes)


def is_timeout(error):
    text = error.lower()
    return "timeout" in text or "timed out" in text


def extras(folders, only=()):
    n, walls, tokens = Counter(), [], {}
    for folder in folders:
        for path in sorted(Path(folder).glob("*-r*.json")):
            case = path.stem.rsplit("-r", 1)[0]
            if case not in cases.ALL or (only and case not in only):
                continue
            record = json.loads(path.read_text())
            walls.append(record.get("wall_s") or 0)
            n["records"] += 1
            if record.get("status") != "accepted":
                n["status_" + str(record.get("status"))] += 1
            n["provider_reruns"] += record.get("provider_reruns") or 0
            judged = list(loopcrit.verdicts(record))
            if judged:
                first = judged[0][0]
                if arm_stats.score(case, first) != "right" and len(first) < smallest_answer(case):
                    n["short_first"] += 1
            log = path.with_suffix(".calls.jsonl")
            for line in log.read_text().splitlines() if log.exists() else []:
                call = json.loads(line)
                if call.get("error"):
                    n["call_errors"] += 1
                    n["timeouts"] += is_timeout(call["error"])
                n["resends"] += (call.get("provider") or {}).get("resends", 0)
                tokens.setdefault(call["stage"], []).append(arm_stats.usage(call))
    return n, walls, tokens


def spread(values):
    return f"{statistics.median(values):.0f} / {max(values)}" if values else "-"


def main() -> None:
    args = sys.argv[1:]
    only = set(args.pop(args.index("--cases") + 1).split(",")) if "--cases" in args else set()
    args = [a for a in args if a != "--cases"]
    print(
        "| level | runs | right | accepted | wrong | first right | catch@1 | false alarm | critic calls/run "
        "| short first | wall s median (total) | gen out med/max | gen reasoning med/max "
        "| critic out med/max | critic reasoning med/max | call errors (timeouts) | resends | not accepted |"
    )
    print("|---|" + "---|" * 17)
    for spec in args:
        label, _, folders = spec.partition("=")
        folders = folders.split(",")
        n, _walls, rounds, _per_call = arm_stats.arm(folders, None, only)
        x, walls, tokens = extras(folders, only)
        gen = tokens.get("declare_proposal", [])
        crit = tokens.get("critic", [])
        runs = n["runs"] or 1
        bad = (
            ", ".join(f"{k[7:]} {v}" for k, v in sorted(x.items()) if k.startswith("status_"))
            or "0"
        )
        print(
            f"| {label} | {x['records']} | {n['right']} ({100 * n['right'] / runs:.0f}%) | {n['accepted']} "
            f"| {n['wrong']} | {n['first_right']}/{n['runs']} | {n['catch1']}/{n['first_bad']} "
            f"| {n['false_alarm']}/{n['right_judged']} | {statistics.fmean(rounds or [0]):.2f} "
            f"| {x['short_first']} | {statistics.median(walls or [0]):.0f} ({sum(walls):.0f}) "
            f"| {spread([o for o, _ in gen])} | {spread([r for _, r in gen])} "
            f"| {spread([o for o, _ in crit])} | {spread([r for _, r in crit])} "
            f"| {x['call_errors']} ({x['timeouts']}) | {x['resends']} | {bad} |"
        )


if __name__ == "__main__":
    main()
