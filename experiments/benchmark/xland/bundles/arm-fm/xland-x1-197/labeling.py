def blue_pyramid_made(env):
    return "blue pyramid" in env.products_made

def purple_star_made(env):
    return "purple star" in env.products_made

def red_hex_made(env):
    return "red hex" in env.products_made

def purple_star_picked_up(env):
    return env.picked_up == "purple star"

def blue_pyramid_on_right(env):
    return env.goal_reached
