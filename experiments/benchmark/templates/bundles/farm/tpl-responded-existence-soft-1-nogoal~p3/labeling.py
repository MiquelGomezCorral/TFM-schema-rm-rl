def siren_ringing(env):
    return bool(env.siren_ringing)

def switch_toggled(env):
    return env.events_this_step is not None and any(event == "toggle" for event in env.events_this_step)
