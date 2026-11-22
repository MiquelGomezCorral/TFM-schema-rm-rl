def key_found(env):
    return ((env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["key_found"]) or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col))

def has_matching_key(env):
    return (env.carrying is not None and env.carrying.type == "key" and any(cell is not None and cell.type == "door" and cell.color == env.carrying.color for row in range((env.room_size - 1) * (max([ball_y for ball_x in range(env.width) for ball_y in range(env.height) for ball_cell in [env.grid.get(ball_x, ball_y)] if ball_cell is not None and ball_cell.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)), (env.room_size - 1) * (max([ball_y for ball_x in range(env.width) for ball_y in range(env.height) for ball_cell in [env.grid.get(ball_x, ball_y)] if ball_cell is not None and ball_cell.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) + env.room_size) for cell in [env.grid.get(env.width - env.room_size, row)]))

def target_door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_open for row in range((env.room_size - 1) * (max([ball_y for ball_x in range(env.width) for ball_y in range(env.height) for ball_cell in [env.grid.get(ball_x, ball_y)] if ball_cell is not None and ball_cell.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)), (env.room_size - 1) * (max([ball_y for ball_x in range(env.width) for ball_y in range(env.height) for ball_cell in [env.grid.get(ball_x, ball_y)] if ball_cell is not None and ball_cell.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) + env.room_size) for cell in [env.grid.get(env.width - env.room_size, row)])

def target_room_entered(env):
    return ((env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or (env.agent_pos[0] >= env.width - env.room_size and 0 <= env.agent_pos[1] - (env.room_size - 1) * (max([ball_y for ball_x in range(env.width) for ball_y in range(env.height) for ball_cell in [env.grid.get(ball_x, ball_y)] if ball_cell is not None and ball_cell.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) <= env.room_size - 1))

def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == "pick up the " + env.carrying.color + " ball"
