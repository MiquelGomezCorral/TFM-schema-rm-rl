def at_exit(env):
    return env.grid.get(env.agent_pos[0], env.agent_pos[1]) is not None and env.grid.get(env.agent_pos[0], env.agent_pos[1]).type == "goal"

def switch_toggled(env):
    return "toggle" in env.events_this_step
