def blue_pyramid_made(env):
    return any(product == "blue pyramid" for product in env.products_made)

def blue_pyramid_on_right(env):
    return bool(env.goal_reached)

def purple_star_made(env):
    return any(product == "purple star" for product in env.products_made)
