def grey_star_made(env):
    return "grey star" in env.products_made

def white_key_made(env):
    return "white key" in env.products_made

def grey_square_made(env):
    return "grey square" in env.products_made

def yellow_hex_made(env):
    return "yellow hex" in env.products_made

def green_key_made(env):
    return "green key" in env.products_made

def green_ball_picked_up(env):
    return env.picked_up == "green ball"

def white_pyramid_picked_up(env):
    return env.picked_up == "white pyramid"

def grey_star_on_right(env):
    return env.goal_reached
