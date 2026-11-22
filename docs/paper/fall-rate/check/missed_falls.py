"""Where the falls of one world and agent were not pickable, from ``falls.json``.

Usage: python missed_falls.py <falls.json> <world> <agent> [first_seed last_seed]
Prints the missed count and the commonest (type in front, agent cell, direction) of the misses.
"""

import json
import sys
from collections import Counter
from pathlib import Path

falls_by_episode = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
world, agent = sys.argv[2], sys.argv[3]
first, last = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (0, 999)
total, misses = 0, Counter()
for seed in range(first, last + 1):
    for _step, x, y, direction, front in falls_by_episode[f"{world}/{agent}/{seed}"]:
        total += 1
        if front != "box":
            misses[(front, (x, y), direction)] += 1
print(f"{world}/{agent} seeds {first}-{last}: {sum(misses.values())} of {total} falls missed")
for (front, cell, direction), count in misses.most_common(5):
    print(f"  {count}: {front} in front, agent at {cell} facing {direction} (0 right, 1 down)")
