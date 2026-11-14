def blocker_moved(env):
    return not any(cell is not None and cell.type == "ball" for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)] if any(d is not None and d.type == "door" and x == dx - 1 and y == dy for dx in range(env.width) for dy in range(env.height) for d in [env.grid.get(dx, dy)]))

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(dc is not None and dc.type == "door" and dc.color == env.carrying.color for x in range(env.width) for y in range(env.height) for dc in [env.grid.get(x, y)])

def door_open(env):
    return any(dc is not None and dc.type == "door" and dc.is_open for x in range(env.width) for y in range(env.height) for dc in [env.grid.get(x, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"

def key_lost(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(dc is not None and dc.type == "door" and dc.color == env.carrying.color for x in range(env.width) for y in range(env.height) for dc in [env.grid.get(x, y)])) and not any(dc is not None and dc.type == "door" and dc.is_open for x in range(env.width) for y in range(env.height) for dc in [env.grid.get(x, y)]))
