def client_arrived(env):
    return "arrive" in env.events_this_step

def food_fell(env):
    return "fall" in env.events_this_step

def food_prepared(env):
    return "prepare" in env.events_this_step

def holding_food(env):
    return env.carrying is not None and env.carrying.type == "box"

def order_served(env):
    return "serve" in env.events_this_step

def order_taken(env):
    return "order" in env.events_this_step
