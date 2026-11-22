def blue_key_picked_up(env):
    return env.picked_up == "blue key"

def orange_star_held(env):
    return bool(env.goal_reached)

def orange_star_made(env):
    return any(product == "orange star" for product in env.products_made)
