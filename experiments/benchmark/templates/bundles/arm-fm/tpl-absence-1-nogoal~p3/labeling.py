def key_found(env):
    return (
        (
            env.episode_memory["previous_valuation"]
            and env.episode_memory["previous_valuation"]["key_found"]
        )
        or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)
    )


def has_matching_key(env):
    return (
        env.carrying is not None
        and env.carrying.type == "key"
        and any(
            cell is not None
            and cell.type == "door"
            and cell.color == env.carrying.color
            and 0 <= y - (env.room_size - 1) * ((max([by * (bcell is not None and bcell.type == "ball") for bx in range(env.width) for by in range(env.height) for bcell in [env.grid.get(bx, by)]], default=0) or env.agent_pos[1]) // (env.room_size - 1)) <= env.room_size - 1
            for y in range(env.height)
            for cell in [env.grid.get(env.width - env.room_size, y)]
        )
    )


def target_door_open(env):
    return any(
        cell is not None
        and cell.type == "door"
        and cell.is_open
        and 0 <= y - (env.room_size - 1) * ((max([by * (bcell is not None and bcell.type == "ball") for bx in range(env.width) for by in range(env.height) for bcell in [env.grid.get(bx, by)]], default=0) or env.agent_pos[1]) // (env.room_size - 1)) <= env.room_size - 1
        for y in range(env.height)
        for cell in [env.grid.get(env.width - env.room_size, y)]
    )


def target_room_entered(env):
    return (
        (
            env.episode_memory["previous_valuation"]
            and env.episode_memory["previous_valuation"]["target_room_entered"]
        )
        or (
            env.agent_pos[0] >= env.width - env.room_size
            and 0 <= env.agent_pos[1] - (env.room_size - 1) * ((max([by * (bcell is not None and bcell.type == "ball") for bx in range(env.width) for by in range(env.height) for bcell in [env.grid.get(bx, by)]], default=0) or env.agent_pos[1]) // (env.room_size - 1)) <= env.room_size - 1
        )
    )


def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"
