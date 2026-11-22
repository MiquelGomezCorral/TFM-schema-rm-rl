def key_found(env): return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(view_cell[0] == 5 for view_col in env.gen_obs()["image"] for view_cell in view_col)

def has_matching_key(env):
    return env.carrying is not None and env.carrying.type == "key" and env.carrying.color == max(
        [door.color for dy in range(env.height)
         for door in [env.grid.get(env.width - env.room_size, dy)]
         if door is not None and door.type == "door"
         and dy // (env.room_size - 1) == max(
             [by for bx in range(env.width)
              for by in range(env.height)
              for ball_cell in [env.grid.get(bx, by)]
              if ball_cell is not None and ball_cell.type == "ball"],
             default=env.agent_pos[1]
         ) // (env.room_size - 1)],
        default=None
    )

def target_door_open(env):
    return any(
        door is not None and door.type == "door" and door.is_open
        and dy // (env.room_size - 1) == max(
            [by for bx in range(env.width)
             for by in range(env.height)
             for ball_cell in [env.grid.get(bx, by)]
             if ball_cell is not None and ball_cell.type == "ball"],
            default=env.agent_pos[1]
        ) // (env.room_size - 1)
        for dy in range(env.height)
        for door in [env.grid.get(env.width - env.room_size, dy)]
    )

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or (
        env.agent_pos[0] >= env.width - env.room_size
        and 0 <= env.agent_pos[1] - (env.room_size - 1) * (max(
            [by for bx in range(env.width)
             for by in range(env.height)
             for ball_cell in [env.grid.get(bx, by)]
             if ball_cell is not None and ball_cell.type == "ball"],
            default=env.agent_pos[1]
        ) // (env.room_size - 1)) <= env.room_size - 1
    )

def target_picked_up(env): return env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"
