def key_found(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)


def has_matching_key(env):
    return (
        env.carrying is not None
        and env.carrying.type == "key"
        and any(
            door is not None
            and door.type == "door"
            and door.color == env.carrying.color
            for b in [max(
                [by for bx in range(env.width) for by in range(env.height) for bc in [env.grid.get(bx, by)] if bc is not None and bc.type == "ball"],
                default=env.agent_pos[1],
            ) // (env.room_size - 1)]
            for ty in range((env.room_size - 1) * b, (env.room_size - 1) * b + env.room_size)
            for door in [env.grid.get(env.width - env.room_size, ty)]
        )
    )


def target_door_open(env):
    return any(
        door is not None and door.type == "door" and door.is_open
        for b in [max(
            [by for bx in range(env.width) for by in range(env.height) for bc in [env.grid.get(bx, by)] if bc is not None and bc.type == "ball"],
            default=env.agent_pos[1],
        ) // (env.room_size - 1)]
        for ty in range((env.room_size - 1) * b, (env.room_size - 1) * b + env.room_size)
        for door in [env.grid.get(env.width - env.room_size, ty)]
    )


def target_picked_up(env):
    return (
        env.carrying is not None
        and env.carrying.type == "ball"
        and env.mission == "pick up the " + env.carrying.color + " ball"
    )
