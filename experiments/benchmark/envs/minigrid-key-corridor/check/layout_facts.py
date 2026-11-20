"""Check the KeyCorridor layout facts that the page's target lookup relies on.

usage (repository root):
  PYTHONPATH=app python experiments/benchmark/envs/minigrid-key-corridor/check/layout_facts.py [GYM_ID]

GYM_ID defaults to MiniGrid-KeyCorridorS6R3-v0; the room size S comes from the env (`room_size`).
"""

import sys
from collections import Counter

from src.arm_fm.environments import make_environment

GYM_ID = sys.argv[1] if len(sys.argv) > 1 else "MiniGrid-KeyCorridorS6R3-v0"
SEEDS = range(1, 501)
counts = Counter()

for seed in SEEDS:
    env = make_environment(GYM_ID)
    env.reset(seed=seed)
    u = env.unwrapped
    cells = [(x, y, u.grid.get(x, y)) for x in range(u.width) for y in range(u.height)]
    keys = [(x, y, c) for x, y, c in cells if c is not None and c.type == "key"]
    balls = [(x, y, c) for x, y, c in cells if c is not None and c.type == "ball"]
    locked = [(x, y, c) for x, y, c in cells if c is not None and c.type == "door" and c.is_locked]
    counts["one key"] += len(keys) == 1
    counts["one ball"] += len(balls) == 1
    counts["one locked door"] += len(locked) == 1
    lx, ly, door = locked[0]
    bx, by, _ = balls[0]
    size = u.room_size
    top = (size - 1) * (ly // (size - 1))
    left = u.width - size
    counts["locked door in column width-S"] += lx == left
    counts["key color == locked door color"] += keys[0][2].color == door.color
    counts["ball row band == locked door row band"] += by // (size - 1) == ly // (size - 1)
    counts["ball inside the right-column block"] += left < bx < u.width - 1
    block = [
        (x, y)
        for x, y, c in cells
        if c is not None and c.type == "door" and left <= x and top <= y <= top + size - 1
    ]
    counts["the S x S block holds exactly one door"] += len(block) == 1
    column = [c for x, y, c in cells if c is not None and c.type == "door" and x == left]
    counts["column width-S holds more than one door"] += len(column) > 1
    counts["another unlocked door of the key color in column width-S"] += any(
        not c.is_locked and c.color == door.color for c in column
    )
    counts["key in the left column"] += keys[0][0] < size - 1
    counts["another door anywhere has the locked door's color"] += any(
        c is not None and c.type == "door" and c is not door and c.color == door.color
        for _, _, c in cells
    )
    counts["ball next to the doorway, inside the room"] += (bx, by) == (lx + 1, ly)
    env.close()

print(f"{GYM_ID}, seeds {SEEDS.start} to {SEEDS.stop - 1}")
for name, value in counts.items():
    print(f"{value:4d} of {len(SEEDS)}  {name}")
