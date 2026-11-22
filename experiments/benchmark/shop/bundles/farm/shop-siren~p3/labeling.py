def siren_ringing(env):
    return env.siren_ringing

def switch_toggled(env):
    return "toggle" in env.events_this_step
