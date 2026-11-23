"""List the frozen FARM and ARM-FM bundles the way the final results count them.

Writes ``evidence/bundles.json``: one row per bundle each arm was asked to build (arm, suite, card, bundle,
path from the repository root, status, built, trained card). The selection is the results builder's
``STATUS`` and ``bundle_root`` under ``.git/agent-memory/artifacts/final-results``; this is the only script
of the entry that needs it, the other two read the list.

Run from the repository root:
env PYTHONPATH=app:.git/agent-memory/artifacts/final-results python -P
docs/paper/reward-loops-and-rounds/check/bundle_list.py
"""

import contextlib
import io
import json
from pathlib import Path

with contextlib.redirect_stdout(io.StringIO()):  # the builder prints its report on import
    import build_results as b

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1] / "evidence" / "bundles.json"

rows = []
for arm in ("farm", "arm-fm"):
    for (suite, name), status in sorted(b.STATUS[arm].items()):
        card = name.split("~p")[0]
        rows.append(
            {
                "arm": arm,
                "suite": suite,
                "card": card,
                "bundle": name,
                "path": str((b.bundle_root(suite, arm) / name).resolve().relative_to(REPO)),
                "status": status,
                "built": status == "complete",
                "trained": b.trained(suite, card, arm),
            }
        )

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
for arm in ("farm", "arm-fm"):
    mine = [r for r in rows if r["arm"] == arm]
    print(arm, "asked", len(mine), "built", sum(r["built"] for r in mine))
