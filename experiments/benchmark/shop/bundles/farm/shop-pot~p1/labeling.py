def pot_boiling(env):
    return bool(env.pot_boiling)

def stove_fixed(env):
    return any(event == "fix" for event in env.events_this_step)
