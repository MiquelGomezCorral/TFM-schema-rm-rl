# MiniGrid KeyCorridor S6R3: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/KeyCorridorS6R3>
- Gymnasium ID: `MiniGrid-KeyCorridorS6R3-v0`.
- Reproduction note: the paper's human-intervention table says S3R3, while its released code and artifacts use S6R3. This example follows the released artifact.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`). `[run: script]` is a scripted run or check on the real environment, with `minigrid_family.py keycorridor`, `layout_checks.py` or `mechanics_check.py`.

## Truth conditions in code

Shorthand: `prev` is `env.episode_memory["previous_valuation"]`. `(ax, ay)` is `env.agent_pos`, `d` is `env.agent_dir`. `L` is the color of the door whose `is_locked` is true. `scan` is `for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)]`.

| id | expression |
|---|---|
| `key_found` | `prev["key_found"] or any(c is not None and c.type == "key" and c.color == L and x0 <= x <= x0 + 6 and y0 <= y <= y0 + 6 scan)`, with `x0 = ax + (0, -3, -6, -3)[d]` and `y0 = ay + (-3, 0, -3, -6)[d]` (the 7x7 view box of MiniGrid's `get_view_exts`, walls ignored) |
| `has_matching_key` | `env.carrying is not None and env.carrying.type == "key" and env.carrying.color == L` |
| `target_door_open` | `is_open` of the locked door, found by `scan` as the door with `is_locked` true |
| `target_room_entered` | `prev["target_room_entered"] or (dx <= ax <= dx + 5 and 5 * (dy // 5) <= ay <= 5 * (dy // 5) + 5)`, where `(dx, dy)` is the locked door cell (the room's 6x6 block, door cell included) |
| `target_picked_up` | `env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"` |

Caution: unlocking clears `is_locked` and sets `is_open` [code: world_object.py:Door.toggle], so `L` and the locked door cell cannot be found by `is_locked` once the door has been unlocked. How the labeling code keeps them is not settled in the previous file.

## Evidence

Layout and mission text [code: keycorridor.py:KeyCorridorEnv._gen_grid, roomgrid.py; run: `layout_checks.py`, 300 seeds]. The seven actions and `done` doing nothing [code: minigrid_env.py:step].

- Environment, unlocked side-room doors: [code: roomgrid.py:RoomGrid.connect_all]; the 215 of 300 count [run: `layout_checks.py`].
- Environment, another door with the locked door's color in 200 of 300 layouts: [run: `layout_checks.py`, 300 seeds].
- Environment, opaque rooms and the agent's view stopping at walls and closed doors [code: roomgrid.py:RoomGrid.__init__].
- Environment, left-column key [code: keycorridor.py:_gen_grid; run: `layout_checks.py`, 300/300].
- Objective: step limit `30 * 6**2 = 1080` [code: KeyCorridorEnv.__init__]. Only the mission's ball ends the episode [code: KeyCorridorEnv.step].
- Reading `key_found`: walls are ignored because the labeling code has no visibility information, so it is not known to the labeling code whether the agent can actually see the key. Key already in the box at reset in 39 of 300 layouts [run: `layout_checks.py`]. The hand-written benchmark labeling (`armfm-wave3/manual-bundles/KeyCorridor-1/labeling.py:6-14`) reads the occluded view through `env.gen_obs()`, which the documented labeling API does not offer. The occluded view differs from the ignore-walls reading of `environment.md`, so the two can differ.
- Reading `target_room_entered`: the environment's own room test counts the room's wall ring, door cell included, as inside [code: roomgrid.py:Room.pos_inside]. The benchmark labeling counts the doorway too (`labeling.py:31`, validated on 300 layouts per size in `armfm-wave3/manual-bundles/REPORT.md`). Ball next to the doorway in 23 of 300 layouts [run: `layout_checks.py`].
- Constraints, `has_matching_key` after `key_found`: [code: minigrid_env.py:step, get_view_exts; run: `minigrid_family.py keycorridor explore`, 0 of 300 random episodes, 204 reached it].
- Constraints, `target_door_open` after `has_matching_key`: [code: world_object.py:Door.toggle; run: same, 0 of 300, 57 reached it].
- Constraints, `target_room_entered` after `target_door_open`: [code: roomgrid.py:RoomGrid.connect_all, keycorridor.py:_gen_grid; run: `layout_checks.py`, wall ring holds only the locked door and walls, target unreachable without it, 300/300 seeds; `minigrid_family.py keycorridor explore`, 0 of 300, 43 reached it].
- Constraints, `target_picked_up` after `target_door_open`: [code and run as above; 0 of 300, 17 reached it].
- Constraints, `target_picked_up` after `target_room_entered`: [code: keycorridor.py:_gen_grid, roomgrid.py:Room.pos_inside; run: same, 0 of 300, 17 reached it].
- Constraints, `has_matching_key` with `target_picked_up`: [code: minigrid_env.py:step; run: `mechanics_check.py`, 0 of 300 random episodes].
- Constraints, `key_found` and `target_room_entered` latches: follow from the table of `environment.md`.
- Can: [code: minigrid_env.py:step].
- Cannot: [code: minigrid_env.py:step, Door.toggle; run: `mechanics_check.py`].
- `key_found` only on a turn or a move [code: minigrid_env.py:step].
- `has_matching_key` and `target_door_open` can turn false [code: Door.toggle, `drop`].
- Example trace: seed 0, `MiniGrid-KeyCorridorS6R3-v0`, scripted solver with privileged grid access [run: `minigrid_family.py keycorridor 0`, log `keycorridor_trace_seed0.jsonl`].

## Labeling API

- `env.mission`: the mission string, for example `pick up the grey box`. Mission targets
  come from it: do not assume a fixed color or object, match the designated one.
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid
  coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- Object attributes: `type` (for example `key`, `door`, `box`, `ball`, `wall`, `goal`),
  `color`, and `is_open` and `is_locked` on doors. Door openness and lock state come from
  them.
- `env.carrying`: the carried object, or `None`; it exposes `type` and `color`. Carry state
  comes from it.
- `env.width`, `env.height`: grid size.

Object classes cannot be imported. To scan the grid, guard empty cells with
`cell is not None` before reading an attribute. This expression checks whether any cell holds
a given object type:

    any(cell is not None and cell.type == "<type>" for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
