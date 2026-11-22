def blocker_moved(env): return any(door is not None and door.type == "door" and not any(ball is not None and ball.type == "ball" for ball in [env.grid.get(x - 1, y)]) for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])

def has_door_key(env): return env.carrying is not None and env.carrying.type == "key" and any(door is not None and door.type == "door" and door.color == env.carrying.color for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])

def door_open(env): return any(door is not None and door.type == "door" and door.is_open for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])

def target_picked_up(env): return env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"

def key_lost(env): return (env.episode_memory["previous_valuation"] and env.episode_memory["previous_valuation"]["has_door_key"] and not (env.carrying is not None and env.carrying.type == "key" and any(door is not None and door.type == "door" and door.color == env.carrying.color for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)])) and not any(door is not None and door.type == "door" and door.is_open for x in range(env.width) for y in range(env.height) for door in [env.grid.get(x, y)]))
