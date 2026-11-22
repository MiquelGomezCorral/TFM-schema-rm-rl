def key_found(env):
    return env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"] or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def target_door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_open for y in range((env.room_size - 1) * (max([by for bx in range(env.width) for by in range(env.height) for obj in [env.grid.get(bx, by)] if obj is not None and obj.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)), (env.room_size - 1) * (max([by for bx in range(env.width) for by in range(env.height) for obj in [env.grid.get(bx, by)] if obj is not None and obj.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) + env.room_size) for cell in [env.grid.get(env.width - env.room_size, y)])

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"
