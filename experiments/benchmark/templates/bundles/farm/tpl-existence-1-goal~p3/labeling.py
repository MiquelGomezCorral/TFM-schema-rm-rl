def has_key(env):
    return env.carrying is not None and env.carrying.type == "key" and env.carrying.color == "yellow"


def at_goal(env):
    return any(cell is not None and cell.type == "goal" for cell in [env.grid.get(env.agent_pos[0], env.agent_pos[1])])
