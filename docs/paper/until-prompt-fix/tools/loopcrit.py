"""Critic verdicts in pipeline-loop runs, scored against the cards.

    CC_ROOT=$PWD PYTHONPATH=app python loopcrit.py LABEL=FOLDER[,FOLDER...] [LABEL=...]

Every candidate the critic judged is scored with chain_score.classify: wrong (card mismatch),
form A (an ordered case passed only with an earlier-step Existence: the critic should reject it),
or right. caught = wrong or form A rejected; false alarm = right rejected. Rounds = critic calls
per finished run (generation rounds).
"""

import json
import sys
from collections import Counter
from pathlib import Path

import cases
import chain_score


def verdicts(record):
    generated = {}
    for item in record.get("trace", []):
        value = item["value"]
        if item["step"] == "generate":
            generated[item["attempt"]] = value
            continue
        if item["step"] != "critic" or item["attempt"] not in generated:
            continue
        verdict = json.loads(value) if isinstance(value, str) else value
        yield json.loads(generated[item["attempt"]]), verdict["accepted"]


def main() -> None:
    print("version   cand  wrong rej  formA rej  right rej(false alarm)  rounds/run")
    for spec in sys.argv[1:]:
        label, folders = spec.split("=", 1)
        n = Counter()
        rounds = []
        for folder in folders.split(","):
            for path in sorted(Path(folder).glob("*-r*.json")):
                case = path.stem.rsplit("-r", 1)[0]
                record = json.loads(path.read_text())
                if case not in cases.ALL or record.get("status") not in ("accepted", "failed"):
                    continue
                calls = 0
                for clauses, accepted in verdicts(record):
                    calls += 1
                    stored = [[c["pattern"], c["propositions"], c["priority"]] for c in clauses]
                    score, _tag, _shown = chain_score.classify(
                        case, {"status": "accepted", "clauses": stored}
                    )
                    kind = {"wrong": "wrong", "accepted": "formA", "right": "right"}[score]
                    n[kind] += 1
                    n[kind + "_rej"] += not accepted
                rounds.append(calls)
        total = n["wrong"] + n["formA"] + n["right"]
        mean = sum(rounds) / len(rounds) if rounds else 0
        print(
            f"{label:9} {total:5}  {n['wrong_rej']:3}/{n['wrong']:<4}  {n['formA_rej']:3}/{n['formA']:<4}"
            f"  {n['right_rej']:3}/{n['right']:<4}               {mean:5.2f}"
        )


if __name__ == "__main__":
    main()
