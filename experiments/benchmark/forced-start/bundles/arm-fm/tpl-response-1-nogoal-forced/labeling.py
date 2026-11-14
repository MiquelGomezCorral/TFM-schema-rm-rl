def blocker_moved(env): return not any(c is not None and c.type == "ball" for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] for d in [(dx, dy) for dx in range(env.width) for dy in range(env.height) for cell in [env.grid.get(dx, dy)] if cell is not None and cell.type == "door"] for dx in [d[0]] for dy in [d[1]] if x == dx - 1 and y == dy)

def has_door_key(env): return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def door_open(env): return any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def target_picked_up(env): return env.carrying is not None and env.carrying.type == "box" and env.mission == "pick up the " + str(env.carrying.color) + " box"

def key_lost(env): return env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])) and not any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])
