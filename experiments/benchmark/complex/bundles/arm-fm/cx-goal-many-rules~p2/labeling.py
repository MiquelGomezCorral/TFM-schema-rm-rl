def blocker_moved(env):
    return not any(
        env.grid.get(dx - 1, dy) is not None and env.grid.get(dx - 1, dy).type == "ball"
        for dx in range(env.width)
        for dy in range(env.height)
        for cell in [env.grid.get(dx, dy)]
        if cell is not None and cell.type == "door"
    )


def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(
        env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).color == env.carrying.color
        for x in range(env.width)
        for y in range(env.height)
    )


def door_open(env):
    return any(
        env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_open
        for x in range(env.width)
        for y in range(env.height)
    )


def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"


def key_lost(env):
    return (
        env.episode_memory["previous_valuation"]
        and env.episode_memory["previous_valuation"]["has_door_key"]
        and not (env.carrying is not None and env.carrying.type == "key" and any(
            env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).color == env.carrying.color
            for x in range(env.width)
            for y in range(env.height)
        ))
        and not any(
            env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_open
            for x in range(env.width)
            for y in range(env.height)
        )
    )
