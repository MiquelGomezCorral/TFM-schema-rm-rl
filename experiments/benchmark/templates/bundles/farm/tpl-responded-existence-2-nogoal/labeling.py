def siren_ringing(env):
    return bool(env.siren_ringing)

def switch_toggled(env):
    return env.events_this_step is not None and "toggle" in env.events_this_step
