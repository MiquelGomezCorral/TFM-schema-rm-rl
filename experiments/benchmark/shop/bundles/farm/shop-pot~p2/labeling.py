def pot_boiling(env):
    return env.pot_boiling


def stove_fixed(env):
    return "fix" in env.events_this_step
