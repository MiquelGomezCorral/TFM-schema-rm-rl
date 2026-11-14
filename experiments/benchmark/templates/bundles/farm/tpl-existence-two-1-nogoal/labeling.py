def has_key(env):
    return env.carrying is not None and env.carrying.type == "key" and env.carrying.color == "yellow"
