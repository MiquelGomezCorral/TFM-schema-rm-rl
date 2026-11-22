def has_prerequisite_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for y in range(env.height) for cell in [env.grid.get(10, y)])

def has_target_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for y in range(env.height) for cell in [env.grid.get(5, y)])

def prerequisite_door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_open for y in range(env.height) for cell in [env.grid.get(10, y)])

def target_ball_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball"

def target_door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_open for y in range(env.height) for cell in [env.grid.get(5, y)])
