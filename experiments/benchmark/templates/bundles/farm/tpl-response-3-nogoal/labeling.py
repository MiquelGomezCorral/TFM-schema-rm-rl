def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(
        cell[0] == 5 for col in env.gen_obs()["image"] for cell in col
    )

def target_door_open(env):
    return any(
        cell is not None and cell.type == "door" and cell.is_open
        for room_row in [
            max(
                [y for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"]
                or [env.agent_pos[1]]
            ) // (env.room_size - 1)
        ]
        for y in range((env.room_size - 1) * room_row, (env.room_size - 1) * room_row + env.room_size)
        for cell in [env.grid.get(env.width - env.room_size, y)]
    )
