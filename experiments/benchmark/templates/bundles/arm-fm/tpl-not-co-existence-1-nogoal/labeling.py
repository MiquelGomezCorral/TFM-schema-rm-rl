def blocker_moved(env): return not any(env.grid.get(dx - 1, dy) is not None and env.grid.get(dx - 1, dy).type == "ball" for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "door" for dx in [x] for dy in [y])

def has_door_key(env): return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def door_open(env): return any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def target_picked_up(env): return env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"

def key_lost(env): return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])) and not any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)]))
