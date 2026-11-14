def blocker_moved(env): return not any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "ball" for x in range(env.width) for y in range(env.height) for dx in [x] for dy in [y] if any(env.grid.get(a, b) is not None and env.grid.get(a, b).type == "door" and a == dx + 1 and b == dy for a in range(env.width) for b in range(env.height)))

def has_door_key(env): return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def door_open(env): return any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def target_picked_up(env): return env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"

def key_lost(env): return bool(env.episode_memory["previous_valuation"]) and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])) and not any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])
