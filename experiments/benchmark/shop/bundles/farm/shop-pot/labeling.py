def pot_boiling(env):
    return bool(env.pot_boiling)


def stove_fixed(env):
    return bool(env.events_this_step and "fix" in env.events_this_step)
