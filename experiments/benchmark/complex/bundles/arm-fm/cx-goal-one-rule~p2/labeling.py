def blocker_moved(env):
    return not any(c is not None and c.type == "ball" for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "door" and x - 1 >= 0 and y == y for _ in [0]) and not any(c is not None and c.type == "ball" for dx in range(env.width) for dy in range(env.height) for d in [env.grid.get(dx, dy)] if d is not None and d.type == "door" for c in [env.grid.get(dx - 1, dy)])


def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])


def door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])


def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == "pick up the " + str(env.carrying.color) + " box"


def key_lost(env):
    return bool(env.episode_memory["previous_valuation"]) and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])) and not any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])
