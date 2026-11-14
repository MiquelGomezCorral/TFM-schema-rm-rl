def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def has_matching_key(env):
    return (env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.is_locked and env.carrying.color == cell.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])) or (env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.is_open and env.carrying.color == cell.color and env.episode_memory["previous_valuation"] and not any(cell2 is not None and cell2.type == "door" and cell2.is_locked for x in range(env.width) for y in range(env.height) for cell2 in [env.grid.get(x, y)]) for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)]))

def target_door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_locked and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)]) or (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["has_matching_key"] and any(cell is not None and cell.type == "door" and cell.is_open and not cell.is_locked for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)]) and not any(cell is not None and cell.type == "door" and cell.is_locked for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)]))

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or any(cell is not None and cell.type == "door" and env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_door_open"] and x <= env.agent_pos[0] <= x + 5 and 5 * (y // 5) <= env.agent_pos[1] <= 5 * (y // 5) + 5 for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == "pick up the " + str(env.carrying.color) + " ball"
