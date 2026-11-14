def blocker_moved(env):
    return not any(env.grid.get(dx - 1, dy) is not None and env.grid.get(dx - 1, dy).type == "ball" for x in range(env.width) for y in range(env.height) for dx in [x] for dy in [y] if env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door")


def door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])


def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])


def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == "pick up the " + env.carrying.color + " box"
