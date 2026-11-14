def target_picked_up(env):
    return env.carrying is not None and env.carrying.type == "ball" and env.mission == "pick up the " + str(env.carrying.color) + " ball"

def target_room_entered(env):
    return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["target_room_entered"]) or (env.agent_pos[0] >= env.width - 6 and 0 <= env.agent_pos[1] - 5 * (max([y for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // 5) <= 5)
