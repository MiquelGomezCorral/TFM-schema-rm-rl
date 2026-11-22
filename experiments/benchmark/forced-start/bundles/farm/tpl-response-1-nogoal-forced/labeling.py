def blocker_moved(env):
    return not any(x > 0 and door is not None and door.type == "door" and env.grid.get(x - 1, y) is not None and env.grid.get(x - 1, y).type == "ball" for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(door is not None and door.type == "door" and door.color == env.carrying.color for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])
