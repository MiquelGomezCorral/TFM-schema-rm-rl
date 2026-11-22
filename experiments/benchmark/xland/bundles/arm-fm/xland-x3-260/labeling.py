def orange_star_made(env): return "orange star" in env.products_made
def green_star_made(env): return "green star" in env.products_made
def grey_pyramid_made(env): return "grey pyramid" in env.products_made
def orange_ball_made(env): return "orange ball" in env.products_made
def white_ball_made(env): return "white ball" in env.products_made
def blue_key_picked_up(env): return env.picked_up == "blue key"
def white_pyramid_picked_up(env): return env.picked_up == "white pyramid"
def blue_hex_picked_up(env): return env.picked_up == "blue hex"
def orange_star_held(env): return env.goal_reached
