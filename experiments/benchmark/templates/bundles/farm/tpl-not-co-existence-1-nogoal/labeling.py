def blocker_moved(env):
    return not any(cell is not None and cell.type == "ball" for door_x in range(env.width) for door_y in range(env.height) for door in [env.grid.get(door_x, door_y)] if door is not None and door.type == "door" for cell in [env.grid.get(door_x - 1, door_y)])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
