def has_key(env): return env.carrying is not None and env.carrying.type == "key" and env.carrying.color == "yellow"

def door_open(env): return any(cell is not None and cell.type == "door" and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def at_goal(env): return any(cell is not None and cell.type == "goal" for cell in [env.grid.get(env.agent_pos[0], env.agent_pos[1])])

def key_lost(env): return bool(env.episode_memory["previous_valuation"]) and env.episode_memory["previous_valuation"]["has_key"] and not (env.carrying is not None and env.carrying.type == "key" and env.carrying.color == "yellow") and not any(cell is not None and cell.type == "door" and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
