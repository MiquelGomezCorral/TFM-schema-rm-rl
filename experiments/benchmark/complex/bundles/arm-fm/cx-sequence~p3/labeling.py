def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(door is not None and door.type == "door" and door.color == env.carrying.color for b in [max([y for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)] if cell is not None and cell.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)] for door_y in range((env.room_size - 1) * b, (env.room_size - 1) * b + env.room_size) for door in [env.grid.get(env.width - env.room_size, door_y)])

def target_door_open(env):
    return any(door is not None and door.type == "door" and door.is_open for b in [max([y for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)] if cell is not None and cell.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)] for door_y in range((env.room_size - 1) * b, (env.room_size - 1) * b + env.room_size) for door in [env.grid.get(env.width - env.room_size, door_y)])

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or (env.agent_pos[0] >= env.width - env.room_size and any((env.room_size - 1) * b <= env.agent_pos[1] <= (env.room_size - 1) * b + env.room_size - 1 for b in [max([y for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)] if cell is not None and cell.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)]))

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"
