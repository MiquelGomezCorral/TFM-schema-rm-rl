def blue_key_picked_up(env):
    return env.picked_up == "blue key"

def blue_pyramid_on_right(env):
    return bool(env.goal_reached)
