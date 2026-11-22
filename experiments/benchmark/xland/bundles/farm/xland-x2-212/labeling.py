def grey_star_made(env):
    return "grey star" in env.products_made

def grey_star_on_right(env):
    return bool(env.goal_reached)

def white_key_made(env):
    return "white key" in env.products_made
