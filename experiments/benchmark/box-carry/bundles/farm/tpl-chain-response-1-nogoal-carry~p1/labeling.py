def at_exit(env):
    return any(cell is not None and cell.type == "goal" for cell in [env.grid.get(env.agent_pos[0], env.agent_pos[1])])

def box_fell(env):
    return "fall" in env.events_this_step

def holding_box(env):
    return env.carrying is not None and env.carrying.type == "box"
