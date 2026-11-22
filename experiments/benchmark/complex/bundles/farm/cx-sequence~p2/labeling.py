def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for B in [max([y for y in range(env.height) for x in range(env.width) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)] for y in range((env.room_size - 1) * B, (env.room_size - 1) * B + env.room_size) for c in [env.grid.get(env.width - env.room_size, y)])

def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def target_door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for B in [max([y for y in range(env.height) for x in range(env.width) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)] for y in range((env.room_size - 1) * B, (env.room_size - 1) * B + env.room_size) for c in [env.grid.get(env.width - env.room_size, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or any(env.agent_pos[0] >= env.width - env.room_size and 0 <= env.agent_pos[1] - (env.room_size - 1) * B <= env.room_size - 1 for B in [max([y for y in range(env.height) for x in range(env.width) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)])
