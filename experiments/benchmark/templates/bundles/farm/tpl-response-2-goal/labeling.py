def has_key(env):
    return env.carrying is not None and env.carrying.type == "key" and env.carrying.color == "yellow"

def door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])

def at_goal(env):
    return any(c is not None and c.type == "goal" for c in [env.grid.get(env.agent_pos[0], env.agent_pos[1])])
