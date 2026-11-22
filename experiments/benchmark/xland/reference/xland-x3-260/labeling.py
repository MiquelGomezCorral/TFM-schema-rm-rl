def green_star_made(env):
    return "green star" in env.products_made

def orange_star_held(env):
    return env.goal_reached

def orange_star_made(env):
    return "orange star" in env.products_made
