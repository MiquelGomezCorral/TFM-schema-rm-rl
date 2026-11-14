def key_found(env):
    return bool(env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)


def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and env.carrying.color == max([c.color for y in range(5 * (max([y for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // 5), 5 * (max([y for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // 5) + 6) for c in [env.grid.get(env.width - 6, y)] if c is not None and c.type == "door"], default=None)


def target_door_open(env):
    return any(c is not None and c.type == "door" and c.is_open for y in range(5 * (max([y for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // 5), 5 * (max([y for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // 5) + 6) for c in [env.grid.get(env.width - 6, y)])


def target_room_entered(env):
    return bool(env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or (env.agent_pos[0] >= env.width - 6 and 0 <= env.agent_pos[1] - 5 * (max([y for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // 5) <= 5)


def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"
