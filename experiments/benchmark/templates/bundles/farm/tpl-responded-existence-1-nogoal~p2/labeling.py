def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])
