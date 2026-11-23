"""Sort the frozen ARM-FM bundles that failed their own check by the failure they ended on.

Kinds: ``invalid output`` (the last generator answer did not parse or compile), ``critic rejections
until attempts ran out`` (the last answer was rejected), ``plan check failed`` (generation passed,
the card's plans did not), ``other``. A plan-check failure also gets the problem its status names
(the first one ``app/src/benchmark/plan_check.py`` found). Reads the bundle list
``docs/paper/reward-loops-and-rounds/evidence/bundles.json`` and, per failed bundle,
``<bundle>.status.json`` and ``<bundle>/attempts.json``; writes ``evidence/failures.json``.
Run: python docs/paper/armfm-failure-kinds/check/failure_kinds.py (from the repo root).
"""

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
BUNDLES = REPO / "docs/paper/reward-loops-and-rounds/evidence/bundles.json"
PLAN_CHECK_FAILED = "plan-check-failed"  # plan_check.FAILED_REASON
PROBLEMS = (  # plan_check._problems wording -> what the machine does wrong
    ("ends the episode before the agent acts", "the machine ends before the agent acts"),
    ("reaches the final at step", "a plan that breaks a hard rule reaches the final"),
    ("breaks only soft rules and pays nothing", "a plan that breaks only soft rules pays nothing"),
    ("not the final", "the solving plan does not reach the final"),
    ("the labeling failed", "the labeling code crashes"),
)
KINDS = ("invalid output", "critic rejections until attempts ran out", "plan check failed", "other")
SHORT = 160


def read_json(path, missing):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else missing


def failure_kind(reason, attempts):
    if reason.startswith(PLAN_CHECK_FAILED):
        return "plan check failed"
    last = attempts[-1]["status"] if attempts else None
    if last == "failed":
        return "invalid output"
    if last == "rejected":
        return "critic rejections until attempts ran out"
    return "other"


def generation_passed(attempts):
    """Every generation stage's last answer was accepted."""
    last = {a["stage"]: a["status"] for a in attempts}
    return bool(last) and all(status == "accepted" for status in last.values())


def plan_check_problem(reason):
    if not reason.startswith(PLAN_CHECK_FAILED):
        return None
    return next((name for words, name in PROBLEMS if words in reason), "other plan-check problem")


# ========= One row per failed ARM-FM bundle =========
asked = [r for r in json.loads(BUNDLES.read_text(encoding="utf-8")) if r["arm"] == "arm-fm"]
failed = [r for r in asked if not r["built"]]
rows = []
for r in failed:
    status = read_json(REPO / f"{r['path']}.status.json", {})
    reason = status.get("reason") or ""
    attempts = read_json(REPO / r["path"] / "attempts.json", [])
    rows.append(
        {
            "suite": r["suite"],
            "card": r["card"],
            "bundle": r["bundle"],
            "path": r["path"],
            "status": status.get("status"),
            "kind": failure_kind(reason, attempts),
            "problem": plan_check_problem(reason),
            "error": reason[:SHORT],
            "generation_passed": generation_passed(attempts),
        }
    )

# ========= Counts and one example per kind =========
examples = {}
for row in rows:
    examples.setdefault(row["problem"] or row["kind"], {k: row[k] for k in ("path", "error")})
counts = {
    "asked": len(asked),
    "built": len(asked) - len(failed),
    "failed": len(failed),
    "failed_after_generation_passed": sum(row["generation_passed"] for row in rows),
    "by_kind": {kind: sum(row["kind"] == kind for row in rows) for kind in KINDS},
    "by_plan_check_problem": dict(
        Counter(row["problem"] for row in rows if row["problem"]).most_common()
    ),
    "by_suite_and_problem": {
        f"{suite} | {problem}": n
        for (suite, problem), n in sorted(
            Counter((row["suite"], row["problem"] or row["kind"]) for row in rows).items()
        )
    },
}
record = {"counts": counts, "examples": examples, "rows": rows}
(EVIDENCE / "failures.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
print(json.dumps({"counts": counts, "examples": examples}, indent=1))
