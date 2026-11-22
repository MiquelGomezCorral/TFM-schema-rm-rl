def top_breach(env):
    return any(event == "top_breach" for event in env.events_this_step)
