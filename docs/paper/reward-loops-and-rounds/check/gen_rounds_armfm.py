"""Count generator rounds per stage over the frozen ARM-FM set, the ARM-FM side of ``gen_rounds.py``.

ARM-FM's ``attempts.json`` has other stages than FARM's: ``reward_machine`` (the machine) and
``labeling`` go through the critic; ``descriptions`` (state texts) has no critic. Its statuses add
``failed``: an answer that does not parse or compile, refused before any critic sees it. A round is
one generator answer of a stage, a failed one included. The manifest stamp (``provenance.stamp``)
adds the counted attempts, critic interventions and provider retries.
Reads ``evidence/bundles.json`` (from ``bundle_list.py``), writes ``evidence/gen-rounds-armfm.txt``.
Run: python docs/paper/reward-loops-and-rounds/check/gen_rounds_armfm.py (from the repo root).
"""

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
BUNDLES = json.loads((EVIDENCE / "bundles.json").read_text(encoding="utf-8"))
STAGES = ("reward_machine", "labeling", "descriptions")
CRITIC_STAGES = ("reward_machine", "labeling")


def read_json(path, missing):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else missing


def built_after(attempts):
    """How a built bundle got through: first try, or after which kind of refused answer."""
    statuses = {a["status"] for a in attempts}
    if "failed" in statuses and "rejected" in statuses:
        return "after an invalid output and a critic rejection"
    if "failed" in statuses:
        return "after an invalid output"
    if "rejected" in statuses:
        return "after a critic rejection"
    return "first try"


# ========= One row per asked ARM-FM bundle =========
armfm = [r for r in BUNDLES if r["arm"] == "arm-fm"]
rows = []
for r in armfm:
    root = REPO / r["path"]
    attempts = read_json(root / "attempts.json", None)
    stamp = read_json(root / "manifest.json", {}).get("provenance", {}).get("stamp", {})
    rows.append((r, attempts, stamp))
built = [(r, attempts, stamp) for r, attempts, stamp in rows if r["built"]]
assert all(attempts is not None for _, attempts, _ in built), "a built bundle has no attempts.json"

# ========= Patterns, as in gen_rounds.py =========
lines = [
    f"ledger {len(armfm)} {Counter(r['status'] for r in armfm)}",
    f"built {len(built)} no attempts.json 0",
]
patterns = Counter(
    tuple(sorted(Counter((a["stage"], a["status"]) for a in attempts).items()))
    for _, attempts, _ in built
)
lines += [f"{count} {pattern}" for pattern, count in patterns.most_common()]

# ========= Rounds per stage: how many needed 1, 2, ... and the mean =========
total_critic_rounds = 0
for stage in STAGES:
    answers = [[a for a in attempts if a["stage"] == stage] for _, attempts, _ in built]
    rounds = [len(stage_answers) for stage_answers in answers]
    invalid = sum(a["status"] == "failed" for stage_answers in answers for a in stage_answers)
    if stage in CRITIC_STAGES:
        total_critic_rounds += sum(rounds)
    lines.append(
        f"stage {stage} rounds {dict(sorted(Counter(rounds).items()))} "
        f"mean {sum(rounds)}/{len(built)} = {sum(rounds) / len(built):.3f} invalid answers {invalid}"
    )
lines.append(
    f"critic stages together {total_critic_rounds}/{len(built)} = {total_critic_rounds / len(built):.3f}"
)
lines.append(f"built {Counter(built_after(attempts) for _, attempts, _ in built)}")

# ========= Stamp, and every invalid answer of a built bundle =========
lines.append(f"stamp keys {sorted({key for _, _, stamp in built for key in stamp})}")
for key in ("attempts", "critic_interventions", "retries"):
    lines.append(f"stamp {key} {Counter(stamp.get(key) for _, _, stamp in built)}")
lines.append(
    "stamp (attempts, critic_interventions, retries) "
    f"{Counter((s.get('attempts'), s.get('critic_interventions'), s.get('retries')) for _, _, s in built)}"
)
lines += [
    f"invalid {r['path']} {a['stage']} attempt {a['attempt']}: {a['error']} "
    f"(stamp critic_interventions {stamp.get('critic_interventions')})"
    for r, attempts, stamp in built
    for a in attempts
    if a["status"] == "failed"
]

text = "\n".join(lines) + "\n"
(EVIDENCE / "gen-rounds-armfm.txt").write_text(text, encoding="utf-8")
print(text, end="")
