"""Recompute the soft-rule quality measure for judged runs from their saved test traces; no training.

For every ``judge.json`` given whose card has a soft clause, re-judges each test episode's saved
reference labels (``agent-traces/ep<k>.json``) with ``src.benchmark.judge_trace`` (the code
PYTHONPATH points at) and averages, per experiment (seeds together) and arm:
``soft_break_count`` (separate soft breaks) and ``any_soft_break`` (share of episodes with one),
beside the stored ``mean_judged_success`` and ``mean_soft_breaks`` (broken soft clauses). The
old ``soft_breaks`` is recomputed too, as a check that the traces reproduce the stored judge.

Usage: PYTHONPATH=<app> python recompute_soft.py OUT.jsonl WORKTREES_ROOT
(every ``<worktree>/outputs/runs/<experiment>/<seed run>/judge.json`` of the packet's cards)
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from src.benchmark import judge_trace

SEED_SUFFIX = re.compile(r"-(s|seed)\d+$")
CARDS = re.compile(r"cx-goal-one-rule|cx-goal-many-rules|lanes-rules|tpl-[a-z-]+-soft-1-goal")


def arm_of(judge):
    bundle = judge.get("rm_bundle")
    return "no-RM" if not bundle else "ARM-FM" if "/arm-fm/" in bundle else "FARM"


def one_run(path):
    """Per-episode recomputed fields of one run, or the reason it cannot be recomputed."""
    judge = json.loads(path.read_text())
    clauses = [(c["clause"][0], tuple(c["clause"][1]), c["clause"][2]) for c in judge["expect"]]
    if not any(priority == "soft" for *_, priority in clauses):
        return judge, None, "no soft clause"
    episodes = judge.get("per_episode")
    if not episodes:
        return judge, None, "judge.json has no per-episode records"
    rows = []
    for episode in episodes:
        trace = path.parent / episode["file"]
        if not trace.is_file():
            return judge, None, f"missing {episode['file']}"
        verdict = judge_trace(clauses, json.loads(trace.read_text())["labels"]).to_dict()
        rows.append({**verdict, "stored_soft_breaks": episode["soft_breaks"]})
    return judge, rows, None


def main():
    out, root = Path(sys.argv[1]), Path(sys.argv[2])
    groups, skipped = defaultdict(list), []
    for path in sorted(root.glob("*/outputs/runs/*/*/judge.json")):
        if not CARDS.fullmatch(json.loads(path.read_text()).get("id", "")):
            continue
        judge, rows, reason = one_run(path)
        run = path.parent.parent
        worktree = run.parent.parent.parent.name
        key = (judge["id"], worktree, SEED_SUFFIX.sub("", run.name), arm_of(judge))
        if reason:
            skipped.append((key, str(path), reason))
            continue
        groups[key].append((judge, rows))

    table = []
    for (card, worktree, experiment, arm), runs in sorted(groups.items()):
        episodes = [row for _, rows in runs for row in rows]
        mismatch = sum(row["soft_breaks"] != row["stored_soft_breaks"] for row in episodes)
        table.append(
            {
                "card": card,
                "task": runs[0][0]["task"],
                "worktree": worktree,
                "experiment": experiment,
                "arm": arm,
                "seeds": len(runs),
                "episodes": len(episodes),
                "judged_success": round(fmean(j["mean_judged_success"] for j, _ in runs), 3),
                "soft_breaks_stored": round(fmean(j["mean_soft_breaks"] for j, _ in runs), 3),
                "soft_break_count": round(fmean(r["soft_break_count"] for r in episodes), 3),
                "any_soft_break": round(fmean(r["any_soft_break"] for r in episodes), 3),
                "old_measure_mismatches": mismatch,
            }
        )
    out.write_text("\n".join(json.dumps(row) for row in table) + "\n")

    tasks = {row["card"]: row["task"] for row in table}
    for card, task in tasks.items():
        print(f"\n### {card}: {task}\n")
        print(
            "| worktree / experiment | arm | seeds x episodes | judged success | soft breaks "
            "(clauses, stored) | separate soft breaks | episodes with a soft break | old "
            "measure mismatches |"
        )
        print("|---|---|---|---|---|---|---|---|")
        for row in (r for r in table if r["card"] == card):
            print(
                f"| {row['worktree']} / {row['experiment']} | {row['arm']} | {row['seeds']} x "
                f"{row['episodes'] // row['seeds']} | {row['judged_success']} | "
                f"{row['soft_breaks_stored']} | {row['soft_break_count']} | "
                f"{row['any_soft_break']} | {row['old_measure_mismatches']} |"
            )
    print("\nNot recomputed:")
    for key, path, reason in skipped:
        print(f"  {key}: {reason} ({path})")


if __name__ == "__main__":
    main()
