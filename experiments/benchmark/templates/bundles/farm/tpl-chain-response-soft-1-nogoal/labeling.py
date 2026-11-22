def box_fell(env):
    return "fall" in env.events_this_step

def holding_box(env):
    return env.carrying is not None and env.carrying.type == "box"
