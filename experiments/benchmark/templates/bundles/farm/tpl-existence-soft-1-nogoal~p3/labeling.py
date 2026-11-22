def switch_toggled(env):
    return bool(env.events_this_step) and "toggle" in env.events_this_step
