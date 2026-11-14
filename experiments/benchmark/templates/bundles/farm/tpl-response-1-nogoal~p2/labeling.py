def blocker_moved(env):
    return not any(c is not None and c.type == "ball" for x in range(env.width) for y in range(env.height) for d in [env.grid.get(x, y)] if d is not None and d.type == "door" for c in [env.grid.get(x - 1, y)])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])
