def blocker_moved(env):
    return not any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "ball" for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)] if door is not None and door.type == "door" for bx in [x - 1] for by in [y] if 0 <= bx < env.width and 0 <= by < env.height and env.grid.get(bx, by) is not None and env.grid.get(bx, by).type == "ball")

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).color == env.carrying.color for x in range(env.width) for y in range(env.height))

def door_open(env):
    return any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_open for x in range(env.width) for y in range(env.height))

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == "pick up the " + env.carrying.color + " box"

def key_lost(env):
    return env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).color == env.carrying.color for x in range(env.width) for y in range(env.height))) and not any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_open for x in range(env.width) for y in range(env.height))
