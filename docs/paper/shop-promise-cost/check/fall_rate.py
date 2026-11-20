"""Food falls and wells over training, per block of steps, from a run's episodes.csv rm_path.

Every machine state with an edge into the well is a "food fell, pick it up next" state, so a path
through one had a fall (the food was carried). A fall is saved when the next state is not the well.
Today's shop-serve machine: fell states u3 u4 u5 u8 u9 u11 u13 u16, well u14.

Usage: python fall_rate.py BLOCK_STEPS EPISODES.csv [...]
"""

import csv
import sys
from collections import Counter
from pathlib import Path

FELL = {"u3", "u4", "u5", "u8", "u9", "u11", "u13", "u16"}
WELL = "u14"


def main() -> None:
    block_steps = int(sys.argv[1])
    for path in sys.argv[2:]:
        rows = Counter()
        with Path(path).open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                block = int(row["global_step"]) // block_steps
                states = row["rm_path"].split()
                falls = [i for i, state in enumerate(states) if state in FELL]
                rows[block, "episodes"] += 1
                rows[block, "fell"] += bool(falls)
                rows[block, "saved"] += any(
                    i + 1 < len(states) and states[i + 1] != WELL for i in falls
                )
                rows[block, "well"] += states[-1] == WELL
                rows[block, "prepared"] += any(
                    state in ("u2", "u5", "u7", "u9") for state in states
                )
        print(path.split("/")[-3])
        for block in sorted({block for block, _ in rows}):
            n = rows[block, "episodes"]
            print(
                f"  {block * block_steps / 1e6:.1f}M: {n} ep, fell {rows[block, 'fell'] / n:.0%}, "
                f"a fall saved {rows[block, 'saved'] / n:.0%}, well {rows[block, 'well'] / n:.0%}, "
                f"prepared-state {rows[block, 'prepared'] / n:.0%}"
            )


if __name__ == "__main__":
    main()
