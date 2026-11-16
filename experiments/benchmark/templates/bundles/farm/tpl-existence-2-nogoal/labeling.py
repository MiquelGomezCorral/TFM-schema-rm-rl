def blocker_moved(env):
    return any(c is not None and c.type == "door" and x > 0 and not any(b is not None and b.type == "ball" for b in [env.grid.get(x - 1, y)]) for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])
