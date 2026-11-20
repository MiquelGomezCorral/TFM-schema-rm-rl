"""Critic-set table: one row per critic, pooled over the folders given (one run per item each).

    python docs/paper/model-comparison/check/critic_stats.py LABEL=FOLDER[,FOLDER...] [LABEL=...] [--items w01,r02] [--kinds]

A later folder's item replaces an earlier one's, so OLD,NEW merges a rerun of a few items.
Wrong items (labelled defects) and right items (none), as in the model-compare report:
caught@1 = first call rejects a wrong item; flag@1 / flag@run = defects flagged on call 1 / in the run;
missed = accepted with a defect left; fixed-rej = rejected the fully fixed candidate; false alarm =
a right item rejected on its first call. Calls: critic calls and judge calls (the judge is deepseek on
OpenCode). Tokens: output and reasoning tokens of the critic calls, from the call logs; those logs are not
copied (see the entry's README), so the token column prints 0 here.
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path


def load(folders, only):
    records = {}
    for folder in folders:
        for path in sorted(Path(folder).glob("*-r1.json")):
            record = json.loads(path.read_text())
            if record.get("end") in (None, "error") or (only and record["item"] not in only):
                continue
            records[record["item"]] = (record, path.with_suffix(".calls.jsonl"))
    return records


def tokens(log: Path) -> Counter:
    out = Counter()
    for line in log.read_text().splitlines() if log.exists() else []:
        call = json.loads(line)
        if call["stage"] != "critic":
            continue
        out["logged"] += 1
        usage = (call.get("provider") or {}).get("usage") or {}
        if usage:  # OpenCode
            out["output"] += usage.get("completion_tokens") or 0
            out["reasoning"] += (usage.get("completion_tokens_details") or {}).get(
                "reasoning_tokens"
            ) or 0
            continue
        cli = call.get("cli") or {}
        usage = cli.get("usage") or {}
        out["output"] += usage.get("output_tokens") or 0
        out["reasoning"] += usage.get("reasoning_output_tokens") or 0
    return out


def row(label, records):
    n, kinds_all, kinds_hit, walls, tok = Counter(), Counter(), Counter(), [], Counter()
    for record, log in records.values():
        calls = record["calls"]
        n["critic_calls"] += len(calls)
        n["judge_calls"] += sum("judge_raw" in c for c in calls)
        walls.append(record["wall_s"])
        tok += tokens(log)
        if record["defects"]:
            n["wrong"] += 1
            n["defects"] += record["defects"]
            n["caught1"] += record["rejected_first"]
            n["flag1"] += record["flagged_first"]
            n["flag_run"] += record["flagged_total"]
            n["missed"] += record["end"] == "accepted-with-defects"
            n["fixed_rej"] += record["end"] == "false-alarm"
            kinds_all.update(record["flagged_kinds"] + record["missed_kinds"])
            kinds_hit.update(record["flagged_kinds"])
        else:
            n["right"] += 1
            n["false_alarm"] += record["rejected_first"]
    print(
        f"| {label} | {n['caught1']}/{n['wrong']} | {n['flag1']}/{n['defects']} ({100 * n['flag1'] / max(n['defects'], 1):.0f}%) "
        f"| {n['flag_run']}/{n['defects']} | {n['missed']} | {n['fixed_rej']} | {n['false_alarm']}/{n['right']} "
        f"| {n['critic_calls']} | {n['judge_calls']} | {statistics.median(walls or [0]):.0f} "
        f"| {tok['output']} ({tok['reasoning']}) |"
    )
    return kinds_all, kinds_hit


def main() -> None:
    args = sys.argv[1:]
    only = set(args.pop(args.index("--items") + 1).split(",")) if "--items" in args else set()
    args = [a for a in args if a != "--items"]
    show_kinds = "--kinds" in args
    args = [a for a in args if a != "--kinds"]
    print(
        "| critic | caught on call 1 | defects flagged on call 1 | flagged in the run | accepted with a defect left "
        "| rejected the fixed candidate | false alarms (right items) | critic calls | judge calls | wall s median "
        "| critic output tokens (reasoning) |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    per_kind = []
    for spec in args:
        label, _, folders = spec.partition("=")
        per_kind.append((label, *row(label, load(folders.split(","), only))))
    if show_kinds:
        for label, kinds_all, kinds_hit in per_kind:
            print(label, " ".join(f"{k} {kinds_hit[k]}/{kinds_all[k]}" for k in sorted(kinds_all)))


if __name__ == "__main__":
    main()
