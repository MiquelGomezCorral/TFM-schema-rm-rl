def key_found(env):
    return (bool(env.episode_memory["previous_valuation"]) and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)


def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.is_locked and cell.color == env.carrying.color for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])


def target_door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_locked and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])


def target_room_entered(env):
    return (bool(env.episode_memory["previous_valuation"]) and env.episode_memory["previous_valuation"]["target_room_entered"]) or any(
        cell is not None and cell.type == "door" and cell.is_locked and (
            (env.agent_pos[0] == x and env.agent_pos[1] == y)
            or (env.grid.get(x - 1, y) is not None and env.grid.get(x - 1, y).type == "wall" and env.agent_pos[0] >= x + 1 and env.agent_pos[0] <= x + 5 and env.agent_pos[1] >= y - 2 and env.agent_pos[1] <= y + 3)
            or (env.grid.get(x + 1, y) is not None and env.grid.get(x + 1, y).type == "wall" and env.agent_pos[0] <= x - 1 and env.agent_pos[0] >= x - 5 and env.agent_pos[1] >= y - 2 and env.agent_pos[1] <= y + 3)
            or (env.grid.get(x, y - 1) is not None and env.grid.get(x, y - 1).type == "wall" and env.agent_pos[1] >= y + 1 and env.agent_pos[1] <= y + 5 and env.agent_pos[0] >= x - 2 and env.agent_pos[0] <= x + 3)
            or (env.grid.get(x, y + 1) is not None and env.grid.get(x, y + 1).type == "wall" and env.agent_pos[1] <= y - 1 and env.agent_pos[1] >= y - 5 and env.agent_pos[0] >= x - 2 and env.agent_pos[0] <= x + 3)
        )
        for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)]
    )


def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == "pick up the " + env.carrying.color + " ball"
