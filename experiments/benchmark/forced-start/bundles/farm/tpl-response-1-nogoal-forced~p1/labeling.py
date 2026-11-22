def blocker_moved(env):
    return not any(
        ball is not None and ball.type == "ball"
        and door is not None and door.type == "door"
        for x in range(env.width - 1)
        for y in range(env.height)
        for ball in [env.grid.get(x, y)]
        for door in [env.grid.get(x + 1, y)]
    )


def has_door_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(
        cell is not None and cell.type == "door" and cell.color == env.carrying.color
        for x in range(env.width)
        for y in range(env.height)
        for cell in [env.grid.get(x, y)]
    )
