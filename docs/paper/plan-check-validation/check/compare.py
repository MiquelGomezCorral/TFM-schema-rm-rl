"""List every copy whose plan-check verdict or problem list differs between two record folders.

Usage: python compare.py BEFORE_DIR AFTER_DIR OUT_JSON   (folders written by snapshot_records.py)
"""

import json
import sys
from pathlib import Path


def records(folder: Path) -> dict[str, dict]:
    return {
        str(p.relative_to(folder)).removesuffix(".plan_check.json"): json.loads(
            p.read_text(encoding="utf-8")
        )
        for p in sorted(folder.glob("*/*/*/*.plan_check.json"))
    }


def main() -> None:
    before, after = records(Path(sys.argv[1])), records(Path(sys.argv[2]))
    changes = []
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key, {}), after.get(key, {})
        if old.get("passed") == new.get("passed") and old.get("problems") == new.get("problems"):
            continue
        change = {
            "copy": key,
            "before": "pass" if old.get("passed") else "FAIL",
            "after": "pass" if new.get("passed") else "FAIL",
            "gone": [p for p in old.get("problems", []) if p not in new.get("problems", [])],
            "new": [p for p in new.get("problems", []) if p not in old.get("problems", [])],
        }
        changes.append(change)
        print(
            f"{key}: {change['before']} -> {change['after']}; gone {len(change['gone'])}, new {len(change['new'])}"
        )
    Path(sys.argv[3]).write_text(json.dumps(changes, indent=1) + "\n", encoding="utf-8")
    print(f"{len(changes)} of {len(before)} copies changed")


if __name__ == "__main__":
    main()
