def siren_ringing(env):
    return env.siren_ringing

def switch_toggled(env):
    return "toggle" in env.events_this_step

def holding_box(env):
    return env.carrying is not None and env.carrying.type == "box"

def box_fell(env):
    return "fall" in env.events_this_step

def at_exit(env):
    return env.grid.get(*env.agent_pos) is not None and env.grid.get(*env.agent_pos).type == "goal"
