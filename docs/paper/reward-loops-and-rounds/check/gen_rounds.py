"""Count generator-then-critic rounds per stage over the frozen FARM set.

Each FARM bundle's ``attempts.json`` lists one row per generator answer the critic judged: stage
``compiler`` is the machine, ``labeling`` the labeling code, status ``accepted`` or ``rejected``. The
manifest stamp (``provenance.stamp``) adds the counted attempts, critic interventions and provider retries.
Reads ``evidence/bundles.json`` (from ``bundle_list.py``), writes ``evidence/gen-rounds.txt``.
Run: python docs/paper/reward-loops-and-rounds/check/gen_rounds.py (from the repo root).
"""

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
BUNDLES = json.loads((EVIDENCE / "bundles.json").read_text(encoding="utf-8"))


def read_json(path, missing):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else missing


# ========= One row per asked FARM bundle =========
farm = [r for r in BUNDLES if r["arm"] == "farm"]
rows = []
for r in farm:
    root = REPO / r["path"]
    attempts = read_json(root / "attempts.json", None)
    stamp = read_json(root / "manifest.json", {}).get("provenance", {}).get("stamp", {})
    by_stage = None if attempts is None else Counter((a["stage"], a["status"]) for a in attempts)
    rows.append((r, by_stage, stamp))
built = [(r, by_stage, stamp) for r, by_stage, stamp in rows if r["built"]]

# ========= The same lines as the source note =========
lines = [
    f"ledger {len(farm)} {Counter(r['status'] for r in farm)}",
    f"built {len(built)} no attempts.json {sum(by_stage is None for _, by_stage, _ in built)}",
]
patterns = Counter(tuple(sorted((by_stage or Counter()).items())) for _, by_stage, _ in built)
lines += [f"{count} {pattern}" for pattern, count in patterns.most_common()]
lines.append(f"stamp keys {sorted({key for _, _, stamp in built for key in stamp})}")
for key in ("attempts", "critic_interventions", "retries"):
    lines.append(f"stamp {key} {Counter(stamp.get(key) for _, _, stamp in built)}")
lines += [
    f"not built {r['suite']} {r['bundle']} {r['status']} {by_stage} {stamp.get('attempts')}"
    for r, by_stage, stamp in rows
    if not r["built"]
]

text = "\n".join(lines) + "\n"
(EVIDENCE / "gen-rounds.txt").write_text(text, encoding="utf-8")
print(text, end="")
