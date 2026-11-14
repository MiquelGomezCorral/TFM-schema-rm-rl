def blocker_moved(env):
    return not any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "ball" for x in range(env.width) for y in range(env.height) for _ in [0] if any(d is not None and d.type == "door" and x == dx and y == dy for dx in range(env.width) for dy in range(env.height) for d in [env.grid.get(dx, dy)])) and not any(c is not None and c.type == "ball" for c in [env.grid.get(([dx for dx in range(env.width) for dy in range(env.height) for d in [env.grid.get(dx, dy)] if d is not None and d.type == "door"][0] - 1 if any(d is not None and d.type == "door" for dx in range(env.width) for dy in range(env.height) for d in [env.grid.get(dx, dy)]) else 0), ([dy for dx in range(env.width) for dy in range(env.height) for d in [env.grid.get(dx, dy)] if d is not None and d.type == "door"][0] if any(d is not None and d.type == "door" for dx in range(env.width) for dy in range(env.height) for d in [env.grid.get(dx, dy)]) else 0))])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"

def key_lost(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])) and not any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)]))
