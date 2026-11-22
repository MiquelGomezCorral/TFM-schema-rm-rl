def target_picked_up(env):
    return env.carrying is not None and env.mission == "pick up the " + env.carrying.color + " " + env.carrying.type

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or (env.agent_pos[0] >= env.width - env.room_size and 0 <= env.agent_pos[1] - (env.room_size - 1) * (max([y for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)] if cell is not None and cell.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1)) <= env.room_size - 1)
