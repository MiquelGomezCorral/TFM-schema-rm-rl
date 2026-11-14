def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_locked and env.carrying.color == env.grid.get(x, y).color for x in range(env.width) for y in range(env.height))

def target_door_open(env):
    return any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_locked and env.grid.get(x, y).is_open for x in range(env.width) for y in range(env.height)) or (not any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_locked for x in range(env.width) for y in range(env.height)) and any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_open and env.agent_pos[0] == x and env.agent_pos[1] == y for x in range(env.width) for y in range(env.height)))

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or any(env.grid.get(x, y) is not None and env.grid.get(x, y).type == "door" and env.grid.get(x, y).is_open and x <= env.agent_pos[0] <= x + 5 and 5 * (y // 5) <= env.agent_pos[1] <= 5 * (y // 5) + 5 for x in range(env.width) for y in range(env.height))

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == "pick up the " + str(env.carrying.color) + " ball"
