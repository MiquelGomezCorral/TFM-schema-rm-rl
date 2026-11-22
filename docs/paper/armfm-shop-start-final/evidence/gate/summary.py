"""One line per ARM-FM shop bundle on the freeze: status, stamp, start and final states, gate results. Read-only.

Usage: python summary.py <bundles-freeze/arm-fm folder> <this gate folder>
"""

import json
import sys
from pathlib import Path

folder, gate = Path(sys.argv[1]), Path(sys.argv[2])
for status_path in sorted(folder.glob("*.status.json")):
    name = status_path.name.removesuffix(".status.json")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    bundle = folder / name
    lines = (bundle / "reward_machine.txt").read_text(encoding="utf-8").splitlines()
    field = {
        k.strip(): v.strip() for k, _, v in (line.partition(":") for line in lines) if v.strip()
    }
    start, finals = field["INITIAL_STATE"], [s.strip() for s in field["FINAL_STATES"].split(",")]
    states = [s.strip() for s in field["STATES"].split(",")]
    edges = sum(1 for line in lines if line.startswith("(") and line.split(")")[0].count(",") == 1)
    stamp = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))["provenance"][
        "stamp"
    ]
    record = json.loads((gate / "shop" / f"{name}.armfm_gate.json").read_text(encoding="utf-8"))
    checks = " ".join(
        f"{k}={record[k]['ok']}"
        for k in ("facts", "pay_order", "labeling", "plan_check")
        if k in record
    )
    print(
        f"{name}: {status['status']} ({status.get('reason', '-')}); commit {stamp['commit'][:7]} reasoning "
        f"{stamp['reasoning']} {stamp['generator_model']}/{stamp['critic_model']} attempts {stamp['attempts']}; "
        f"{len(states)} states, {edges} edges, start {start}, finals {finals}, start final {start in finals}; "
        f"gate {checks}"
    )
