def blocker_moved(env):
    return not any(cell is not None and cell.type == "ball" for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)] for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)] if door is not None and door.type == "door" for cell in [env.grid.get(x + offset[0], y + offset[1])])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == "pick up the " + str(env.carrying.color) + " box"

def key_lost(env):
    return bool(env.episode_memory["previous_valuation"]) and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])) and not any(cell is not None and cell.type == "door" and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
