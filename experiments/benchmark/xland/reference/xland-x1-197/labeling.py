def blue_pyramid_made(env):
    return "blue pyramid" in env.products_made

def blue_pyramid_on_right(env):
    return env.goal_reached

def purple_star_made(env):
    return "purple star" in env.products_made
