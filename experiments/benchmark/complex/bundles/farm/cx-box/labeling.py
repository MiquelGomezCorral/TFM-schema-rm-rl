def box_fell(env):
    return any(event == "fall" for event in env.events_this_step)

def holding_box(env):
    return env.carrying is not None and env.carrying.type == "box"
