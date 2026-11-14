def blocker_moved(env): return not any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "ball" and any(env.grid.get(dx2, dy2) is not None and env.grid.get(dx2, dy2).type == "door" and dx2 - x == 1 and dy2 == y for dx2 in range(env.width) for dy2 in range(env.height)) for x in range(env.width) for y in range(env.height))

def has_door_key(env): return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def door_open(env): return any(cell is not None and cell.type == "door" and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def target_picked_up(env): return env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"

def key_lost(env): return bool(env.episode_memory["previous_valuation"]) and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])) and not any(cell is not None and cell.type == "door" and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
