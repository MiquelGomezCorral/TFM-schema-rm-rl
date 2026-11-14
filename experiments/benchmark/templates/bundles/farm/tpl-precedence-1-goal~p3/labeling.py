def blocker_moved(env):
    return not any(cell is not None and cell.type == 'ball' for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)] if door is not None and door.type == 'door' for ddx in [x] for ddy in [y] for cell in [env.grid.get(ddx - 1, ddy)])

def door_open(env):
    return any(cell is not None and cell.type == 'door' and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == 'key' and any(cell is not None and cell.type == 'door' and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == 'box' and env.mission == 'pick up the ' + str(env.carrying.color) + ' box'
