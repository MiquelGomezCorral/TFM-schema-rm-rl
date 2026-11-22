def blocker_moved(env):
    return not any(door is not None and door.type == "door" and blocking_cell is not None and blocking_cell.type == "ball" for x in range(1, env.width) for y in range(env.height) for door in [env.grid.get(x, y)] for blocking_cell in [env.grid.get(x - 1, y)])

def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(door is not None and door.type == "door" and door.color == env.carrying.color for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])

def door_open(env):
    return any(door is not None and door.type == "door" and door.is_open for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"

def key_lost(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(door is not None and door.type == "door" and door.color == env.carrying.color for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])) and not (any(door is not None and door.type == "door" and door.is_open for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])))
