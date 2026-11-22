def at_exit(env):
    return env.grid.get(*env.agent_pos) is not None and env.grid.get(*env.agent_pos).type == "goal"

def box_fell(env):
    return "fall" in env.events_this_step

def holding_box(env):
    return env.carrying is not None and env.carrying.type == "box"
