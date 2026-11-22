def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for y in range((env.room_size - 1) * (max([by for bx in range(env.width) for by in range(env.height) for b in [env.grid.get(bx, by)] if b is not None and b.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)), (env.room_size - 1) * (max([by for bx in range(env.width) for by in range(env.height) for b in [env.grid.get(bx, by)] if b is not None and b.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) + env.room_size) for c in [env.grid.get(env.width - env.room_size, y)])

def target_door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for y in range((env.room_size - 1) * (max([by for bx in range(env.width) for by in range(env.height) for b in [env.grid.get(bx, by)] if b is not None and b.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)), (env.room_size - 1) * (max([by for bx in range(env.width) for by in range(env.height) for b in [env.grid.get(bx, by)] if b is not None and b.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) + env.room_size) for c in [env.grid.get(env.width - env.room_size, y)])

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or (env.agent_pos[0] >= env.width - env.room_size and (env.room_size - 1) * (max([by for bx in range(env.width) for by in range(env.height) for b in [env.grid.get(bx, by)] if b is not None and b.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) <= env.agent_pos[1] <= (env.room_size - 1) * (max([by for bx in range(env.width) for by in range(env.height) for b in [env.grid.get(bx, by)] if b is not None and b.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) + env.room_size - 1)

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"
