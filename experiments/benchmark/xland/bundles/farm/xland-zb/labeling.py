def blue_pyramid_on_right(env):
    return bool(env.goal_reached)

def blue_star_picked_up(env):
    return env.picked_up == "blue star"
