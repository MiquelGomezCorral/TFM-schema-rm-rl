def blocker_moved(env):
    return not any(env.grid.get(dx - 1, dy) is not None and env.grid.get(dx - 1, dy).type == "ball" for dx in range(env.width) for dy in range(env.height) for door in [env.grid.get(dx, dy)] if door is not None and door.type == "door")

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).color == env.carrying.color for x in range(env.width) for y in range(env.height))
