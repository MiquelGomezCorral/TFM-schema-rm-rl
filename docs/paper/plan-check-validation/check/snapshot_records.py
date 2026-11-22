"""Copy every copy's .plan_check.json to RECORDS_DIR/<set>/<suite>/<arm>/, so the next run cannot overwrite it.

Usage: python snapshot_records.py S_DIR RECORDS_DIR
"""

import shutil
import sys
from pathlib import Path


def main() -> None:
    copies, records = Path(sys.argv[1]) / "copies", Path(sys.argv[2])
    if records.exists():
        raise SystemExit(f"{records} exists")
    paths = sorted(copies.glob("*/*/*/*.plan_check.json"))
    for path in paths:
        target = records / path.relative_to(copies)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    print(f"{len(paths)} records copied to {records}")


if __name__ == "__main__":
    main()
