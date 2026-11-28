"""Draw the four FARM RMs of the shop two-jobs tasks with the repository's own `render-rm --html`.

Run from the repository root (needs the committed FARM bundles, writes docs/paper/shop-two-jobs/graphs):
    PYTHONPATH=app python -P -W ignore docs/paper/shop-two-jobs/check/render_graphs.py
For each task of data/tasks.json it copies the bundle's `reward_machine.txt` to graphs/<bundle>.rm byte for byte
and calls `render_file` of app/scripts/render_rm.py, the function behind `app/main.py render-rm`, which writes
graphs/<bundle>.svg and the interactive graphs/<bundle>.html. No model call.
"""

import json
import shutil
from pathlib import Path

from scripts.render_rm import render_file

BUNDLES = Path("experiments/benchmark/shop/bundles/farm")
DATA = Path("docs/paper/shop-two-jobs/data")
GRAPHS = Path("docs/paper/shop-two-jobs/graphs")


def main() -> None:
    tasks = json.loads((DATA / "tasks.json").read_text(encoding="utf-8"))
    for task in tasks.values():
        bundle = task["bundle"]
        rm = GRAPHS / f"{bundle}.rm"
        shutil.copyfile(BUNDLES / bundle / "reward_machine.txt", rm)
        for written in render_file(rm, GRAPHS / f"{bundle}.svg", html=True):
            print(written)


if __name__ == "__main__":
    main()
