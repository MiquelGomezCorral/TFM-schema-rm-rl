def top_breach(env):
    return "top_breach" in env.events_this_step

def side_breach(env):
    return "side_breach" in env.events_this_step

def zombie_killed(env):
    return "zombie_killed" in env.events_this_step
