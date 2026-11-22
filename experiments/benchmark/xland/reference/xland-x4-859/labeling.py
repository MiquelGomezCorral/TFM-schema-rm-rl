def blue_ball_made(env):
    return "blue ball" in env.products_made

def blue_ball_reached(env):
    return env.goal_reached

def brown_pyramid_made(env):
    return "brown pyramid" in env.products_made
