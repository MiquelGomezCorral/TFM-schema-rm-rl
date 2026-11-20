"""Per-arm table for the report: machines, first proposals, critic, rounds, calls and time.

    CC_ROOT=$PWD PYTHONPATH=app python docs/paper/model-comparison/check/arm_stats.py LABEL=FOLDER[,FOLDER...] [LABEL=...]

right / accepted / wrong: the final machine, by the loop's chain_score.classify.
first right: the generator's first candidate (before any critic feedback), same scorer.
catch@1: runs whose first candidate was not right (wrong or form A) and the critic rejected it.
false alarm: right candidates the critic rejected / right candidates it judged (any call).
rounds: critic calls per run. calls: logged model requests (generator, critic). time: run wall s.
LLM-loop additions: s/call (median wall of one generator and one critic request), output tokens
(reasoning tokens) of every logged request where the log has usage (OpenCode since this loop, CLI
always), --letters: one letter per run and case (R right, A accepted, W wrong), and --cases a,b: only
those cases.

The call logs (`*.calls.jsonl`, one per run) are slim copies (prompts and schema dropped), so every column,
"calls gen+critic", "s/call" and "output tokens" included, is computed from the copied records.
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import cases
import chain_score
import loopcrit


def score(case, clauses):
    stored = [[c["pattern"], c["propositions"], c["priority"]] for c in clauses]
    return chain_score.classify(case, {"status": "accepted", "clauses": stored})[0]


def usage(call):
    provider = (call.get("provider") or {}).get("usage") or {}
    if provider:
        details = provider.get("completion_tokens_details") or {}
        return provider.get("completion_tokens") or 0, details.get("reasoning_tokens") or 0
    cli = (call.get("cli") or {}).get("usage") or {}
    return cli.get("output_tokens") or 0, cli.get("reasoning_output_tokens") or 0


def arm(folders, letters=None, only=()):
    n, walls, rounds, per_call = Counter(), [], [], {"declare_proposal": [], "critic": []}
    for folder in folders:
        for path in sorted(Path(folder).glob("*-r*.json")):
            case = path.stem.rsplit("-r", 1)[0]
            record = json.loads(path.read_text())
            if (
                case not in cases.ALL
                or record.get("status") not in ("accepted", "failed")
                or (only and case not in only)
            ):
                continue
            n["runs"] += 1
            verdict = chain_score.classify(case, record)[0]
            n[verdict] += 1
            if letters is not None:
                letters.setdefault(case, []).append(
                    {"right": "R", "accepted": "A", "wrong": "W"}[verdict]
                )
            judged = list(loopcrit.verdicts(record))
            if judged:
                first, accepted = judged[0]
                verdict = score(case, first)
                n["first_" + verdict] += 1
                if verdict != "right":
                    n["first_bad"] += 1
                    n["catch1"] += not accepted
            for clauses, accepted in judged:
                if score(case, clauses) == "right":
                    n["right_judged"] += 1
                    n["false_alarm"] += not accepted
            rounds.append(len(judged))
            walls.append(record.get("wall_s") or 0)
            log = path.with_suffix(".calls.jsonl")
            for line in log.read_text().splitlines() if log.exists() else []:
                call = json.loads(line)
                n["calls_" + call["stage"]] += 1
                per_call.setdefault(call["stage"], []).append(call["wall_s"])
                out, thought = usage(call)
                n["tokens_out"] += out
                n["tokens_reasoning"] += thought
    return n, walls, rounds, per_call


def main() -> None:
    args = sys.argv[1:]
    show_letters = "--letters" in args
    args = [a for a in args if a != "--letters"]
    only = set(args.pop(args.index("--cases") + 1).split(",")) if "--cases" in args else set()
    args = [a for a in args if a != "--cases"]
    print(
        "| arm | runs | right | accepted | wrong | first right | catch@1 | false alarm | rounds/run "
        "| calls gen+critic | wall s median (sum) | s/call gen, critic | output tokens (reasoning) |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    table = {}
    for spec in args:
        label, _, folders = spec.partition("=")
        letters = table.setdefault(label, {})
        n, walls, rounds, per_call = arm(folders.split(","), letters, only)
        med = {k: statistics.median(v) if v else 0 for k, v in per_call.items()}
        runs = n["runs"] or 1
        print(
            f"| {label} | {n['runs']} | {n['right']} ({100 * n['right'] / runs:.0f}%) | {n['accepted']} "
            f"| {n['wrong']} | {n['first_right']}/{n['runs']} | {n['catch1']}/{n['first_bad']} "
            f"| {n['false_alarm']}/{n['right_judged']} | {statistics.fmean(rounds or [0]):.2f} "
            f"| {n['calls_declare_proposal']}+{n['calls_critic']} "
            f"| {statistics.median(walls or [0]):.0f} ({sum(walls):.0f}) "
            f"| {med['declare_proposal']:.0f}, {med['critic']:.0f} | {n['tokens_out']} ({n['tokens_reasoning']}) |"
        )
    if show_letters:
        case_names = sorted({c for letters in table.values() for c in letters})
        print("\n| case | " + " | ".join(table) + " |")
        print("|---|" + "---|" * len(table))
        for case in case_names:
            print(
                f"| {case} | "
                + " | ".join("".join(table[label].get(case, "-")) for label in table)
                + " |"
            )


if __name__ == "__main__":
    main()
