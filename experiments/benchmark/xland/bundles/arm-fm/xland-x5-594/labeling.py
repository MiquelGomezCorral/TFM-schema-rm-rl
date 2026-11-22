def pink_ball_made(env):
    return "pink ball" in env.products_made

def orange_square_made(env):
    return "orange square" in env.products_made

def purple_square_made(env):
    return "purple square" in env.products_made

def brown_pyramid_picked_up(env):
    return env.picked_up == "brown pyramid"

def brown_hex_picked_up(env):
    return env.picked_up == "brown hex"

def pink_ball_on_right(env):
    return env.goal_reached
