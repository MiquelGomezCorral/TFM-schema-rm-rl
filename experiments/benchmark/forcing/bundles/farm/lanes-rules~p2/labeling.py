def top_breach(env):
    return any(event == "top_breach" for event in env.events_this_step)

def side_breach(env):
    return any(event == "side_breach" for event in env.events_this_step)

def plant_trampled(env):
    return any(event == "plant_trampled" for event in env.events_this_step)
