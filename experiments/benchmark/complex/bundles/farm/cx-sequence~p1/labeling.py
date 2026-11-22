def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(door is not None and door.type == "door" and door.color == env.carrying.color for b in [max([yy for xx in range(env.width) for yy in range(env.height) for obj in [env.grid.get(xx, yy)] if obj is not None and obj.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)] for y in range((env.room_size - 1) * b, (env.room_size - 1) * b + env.room_size) for door in [env.grid.get(env.width - env.room_size, y)])

def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def target_door_open(env):
    return any(door is not None and door.type == "door" and door.is_open for b in [max([yy for xx in range(env.width) for yy in range(env.height) for obj in [env.grid.get(xx, yy)] if obj is not None and obj.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)] for y in range((env.room_size - 1) * b, (env.room_size - 1) * b + env.room_size) for door in [env.grid.get(env.width - env.room_size, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == "pick up the " + env.carrying.color + " ball"

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or (env.agent_pos[0] >= env.width - env.room_size and 0 <= env.agent_pos[1] - (env.room_size - 1) * (max([yy for xx in range(env.width) for yy in range(env.height) for obj in [env.grid.get(xx, yy)] if obj is not None and obj.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) <= env.room_size - 1)
