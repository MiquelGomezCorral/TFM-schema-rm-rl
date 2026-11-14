def blocker_moved(env):
    return not any(cell is not None and cell.type == "ball" and any(d is not None and d.type == "door" and x == dx - 1 and y == dy for dx in range(env.width) for dy in range(env.height) for d in [env.grid.get(dx, dy)]) for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
