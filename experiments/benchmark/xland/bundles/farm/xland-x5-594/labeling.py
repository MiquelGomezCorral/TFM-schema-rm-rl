def pink_ball_made(env):
    return "pink ball" in env.products_made

def pink_ball_on_right(env):
    return bool(env.goal_reached)
