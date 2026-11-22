def orange_star_made(env): return "orange star" in env.products_made

def blue_key_picked_up(env): return env.picked_up == "blue key"

def purple_ball_picked_up(env): return env.picked_up == "purple ball"

def orange_star_held(env): return env.goal_reached
