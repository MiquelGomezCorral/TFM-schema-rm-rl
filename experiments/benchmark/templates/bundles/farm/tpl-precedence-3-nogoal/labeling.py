def blocker_moved(env):
    return any(env.grid.get(dx - 1, dy) is None or env.grid.get(dx - 1, dy).type != "ball" for dx in range(env.width) for dy in range(env.height) for door in [env.grid.get(dx, dy)] if door is not None and door.type == "door" and dx - 1 >= 0)

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
