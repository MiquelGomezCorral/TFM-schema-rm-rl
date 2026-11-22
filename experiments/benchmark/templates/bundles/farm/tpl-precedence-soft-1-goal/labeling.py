def blocker_moved(env):
    return any(cell is not None and cell.type == "door" and x > 0 and (env.grid.get(x - 1, y) is None or env.grid.get(x - 1, y).type != "ball") for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"
