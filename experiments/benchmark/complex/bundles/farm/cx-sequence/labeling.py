def key_found(env):
    return env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"] or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)

def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and env.carrying.color == max([c.color for y in range(5 * (max([y2 for x2 in range(env.width) for y2 in range(env.height) for c2 in [env.grid.get(x2, y2)] if c2 is not None and c2.type == "ball"], default=env.agent_pos[1]) // 5), 5 * (max([y2 for x2 in range(env.width) for y2 in range(env.height) for c2 in [env.grid.get(x2, y2)] if c2 is not None and c2.type == "ball"], default=env.agent_pos[1]) // 5) + 6) for c in [env.grid.get(env.width - 6, y)] if c is not None and c.type == "door"], default=None)

def target_door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for y in range(5 * (max([y2 for x2 in range(env.width) for y2 in range(env.height) for c2 in [env.grid.get(x2, y2)] if c2 is not None and c2.type == "ball"], default=env.agent_pos[1]) // 5), 5 * (max([y2 for x2 in range(env.width) for y2 in range(env.height) for c2 in [env.grid.get(x2, y2)] if c2 is not None and c2.type == "ball"], default=env.agent_pos[1]) // 5) + 6) for c in [env.grid.get(env.width - 6, y)])

def target_room_entered(env):
    return env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"] or (env.agent_pos[0] >= env.width - 6 and 0 <= env.agent_pos[1] - 5 * (max([y2 for x2 in range(env.width) for y2 in range(env.height) for c2 in [env.grid.get(x2, y2)] if c2 is not None and c2.type == "ball"], default=env.agent_pos[1]) // 5) <= 5)

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == "pick up the " + env.carrying.color + " ball"
