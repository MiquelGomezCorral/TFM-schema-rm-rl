def blocker_moved(env):
    return not any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "ball" and any(env.grid.get(dx, dy) is not None and env.grid.get(dx, dy).type == "door" and dx - 1 == x and dy == y for dx in range(env.width) for dy in range(env.height)) for x in range(env.width) for y in range(env.height))

def door_open(env):
    return any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_open for x in range(env.width) for y in range(env.height))

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).color == env.carrying.color for x in range(env.width) for y in range(env.height))

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == "pick up the " + env.carrying.color + " box"
