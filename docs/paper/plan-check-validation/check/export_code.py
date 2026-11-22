"""Write a commit's app/ tree into a folder with read-only `git show`, to run that commit's check.

Usage (cwd = the main checkout): python export_code.py COMMIT TARGET_DIR
Phase 1 runs e6c3acb (main before the D1/D3 merge 029d82c landed at 14:19 during the run).
"""

import sys
from pathlib import Path

from build import copy_from_git


def main() -> None:
    commit, target = sys.argv[1], Path(sys.argv[2])
    if target.exists():
        raise SystemExit(f"{target} exists")
    copy_from_git(commit, "app", target / "app")
    print(f"{commit}:app written to {target / 'app'}")


if __name__ == "__main__":
    main()
