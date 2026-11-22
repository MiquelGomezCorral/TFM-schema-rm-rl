def blocker_moved(env):
    return not any(c is not None and c.type == "door" and x > 0 and env.grid.get(x - 1, y) is not None and env.grid.get(x - 1, y).type == "ball" for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])
