def has_key(env):
    return env.carrying is not None and env.carrying.type == "key" and env.carrying.color == "yellow"

def door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
