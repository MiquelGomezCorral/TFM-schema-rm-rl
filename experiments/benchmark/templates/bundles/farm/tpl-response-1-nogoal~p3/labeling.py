def blocker_moved(env):
    return not any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "ball" and any(env.grid.get(nx, ny) is not None and env.grid.get(nx, ny).type == "door" and abs(nx - x) + abs(ny - y) == 1 for nx in range(env.width) for ny in range(env.height)) for x in range(env.width) for y in range(env.height))


def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).color == env.carrying.color for x in range(env.width) for y in range(env.height))
