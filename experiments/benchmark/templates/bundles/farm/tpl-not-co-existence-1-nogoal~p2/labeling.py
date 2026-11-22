def blocker_moved(env):
    return any(front is None or front.type != "ball" for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)] if cell is not None and cell.type == "door" and x > 0 for front in [env.grid.get(x - 1, y)])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
