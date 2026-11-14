def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.is_locked and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def target_door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_locked and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or any(cell is not None and cell.type == "door" and cell.is_locked and cell.is_open and min(x, (x // 6) * 6) <= env.agent_pos[0] <= max(x, (x // 6) * 6 + 5) and min(y, (y // 6) * 6) <= env.agent_pos[1] <= max(y, (y // 6) * 6 + 5) for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == "pick up the " + str(env.carrying.color) + " ball"
