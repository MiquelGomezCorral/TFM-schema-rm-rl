"""Check the KeyCorridor layout facts that the page's target lookup relies on.

usage (repository root): PYTHONPATH=app python experiments/benchmark/envs/minigrid-key-corridor/check/layout_facts.py
"""

from collections import Counter

from src.arm_fm.environments import make_environment

SEEDS = range(1, 501)
counts = Counter()

for seed in SEEDS:
    env = make_environment("MiniGrid-KeyCorridorS6R3-v0")
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
    left = u.width - 6
    counts["locked door in column width-6"] += lx == left
    counts["key color == locked door color"] += keys[0][2].color == door.color
    counts["ball row band == locked door row band"] += by // 5 == ly // 5
    counts["ball inside the right-column block"] += left < bx < u.width - 1
    block = [
        (x, y)
        for x, y, c in cells
        if c is not None
        and c.type == "door"
        and left <= x
        and 5 * (ly // 5) <= y <= 5 * (ly // 5) + 5
    ]
    counts["the 6x6 block holds exactly one door"] += len(block) == 1
    column = [c for x, y, c in cells if c is not None and c.type == "door" and x == left]
    counts["column width-6 holds more than one door"] += len(column) > 1
    counts["another unlocked door of the key color in column width-6"] += any(
        not c.is_locked and c.color == door.color for c in column
    )
    env.close()

print(f"seeds {SEEDS.start} to {SEEDS.stop - 1}")
for name, value in counts.items():
    print(f"{value:4d} of {len(SEEDS)}  {name}")
