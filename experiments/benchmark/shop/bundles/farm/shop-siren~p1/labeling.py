def siren_ringing(env):
    return bool(env.siren_ringing)

def switch_toggled(env):
    return bool(env.events_this_step) and any(event == "toggle" for event in env.events_this_step)
