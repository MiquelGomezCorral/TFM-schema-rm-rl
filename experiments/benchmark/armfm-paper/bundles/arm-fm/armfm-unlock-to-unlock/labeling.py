def has_prerequisite_key(env): return any(d is not None and d.type == "door" and env.carrying is not None and env.carrying.type == "key" and env.carrying.color == d.color for y in range(env.height) for d in [env.grid.get(10, y)])

def prerequisite_door_open(env): return any(d is not None and d.type == "door" and d.is_open for y in range(env.height) for d in [env.grid.get(10, y)])

def has_target_door_key(env): return any(d is not None and d.type == "door" and env.carrying is not None and env.carrying.type == "key" and env.carrying.color == d.color for y in range(env.height) for d in [env.grid.get(5, y)])

def target_door_open(env): return any(d is not None and d.type == "door" and d.is_open for y in range(env.height) for d in [env.grid.get(5, y)])

def target_ball_picked_up(env): return env.carrying is not None and env.carrying.type == "ball"

def required_key_lost(env): return (env.episode_memory["previous_valuation"] and env.carrying is None and ((env.episode_memory["previous_valuation"]["has_prerequisite_key"] and not any(d is not None and d.type == "door" and d.is_open for y in range(env.height) for d in [env.grid.get(10, y)])) or (env.episode_memory["previous_valuation"]["has_target_door_key"] and not any(d is not None and d.type == "door" and d.is_open for y in range(env.height) for d in [env.grid.get(5, y)]))))
