def target_door_open(env):
    return any(cell is not None and cell.type == "door" and cell.is_open for y in range(env.height) for cell in [env.grid.get(env.width - env.room_size, y)] if y // (env.room_size - 1) == max([yy for x in range(env.width) for yy in range(env.height) for c in [env.grid.get(x, yy)] if c is not None and c.type == "ball"], default=env.agent_pos[1]) // (env.room_size - 1))
