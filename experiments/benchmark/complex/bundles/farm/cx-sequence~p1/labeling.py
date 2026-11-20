def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color and (env.room_size - 1) * by <= yy <= (env.room_size - 1) * by + env.room_size - 1 for by in [max([cy for cx in range(env.width) for cy in range(env.height) for cc in [env.grid.get(cx, cy)] if cc is not None and cc.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)] for yy in range(env.height) for c in [env.grid.get(env.width - env.room_size, yy)])

def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def target_door_open(env):
    return any(c is not None and c.type == "door" and c.is_open and (env.room_size - 1) * by <= yy <= (env.room_size - 1) * by + env.room_size - 1 for by in [max([cy for cx in range(env.width) for cy in range(env.height) for cc in [env.grid.get(cx, cy)] if cc is not None and cc.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)] for yy in range(env.height) for c in [env.grid.get(env.width - env.room_size, yy)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == "pick up the " + env.carrying.color + " ball"

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or (env.agent_pos[0] >= env.width - env.room_size and 0 <= env.agent_pos[1] - (env.room_size - 1) * (max([cy for cx in range(env.width) for cy in range(env.height) for cc in [env.grid.get(cx, cy)] if cc is not None and cc.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) <= env.room_size - 1)
