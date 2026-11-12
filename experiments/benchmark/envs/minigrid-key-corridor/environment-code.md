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

Shorthand: `prev` is `env.episode_memory["previous_valuation"]`; at the first step every proposition is false in it. `(ax, ay)` is `env.agent_pos`, `d` is `env.agent_dir`. `B` is the row (0 to 2, from the top) of the target room in the 3x3 room grid: `max([y for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=ay) // 5`. The level's only ball lies in the target room, so the ball's row gives `B`; once the agent holds the ball, which ends the episode, no ball is on the grid and `ay` gives `B`, because the agent picks the ball up from inside the room or from its doorway. The target room is the right-column room in row `B`: rows `5 * B` to `5 * B + 5`, columns `env.width - 6` to `env.width - 1`. Its left wall, column `env.width - 6`, holds the target door, the room's only door.

| id | expression |
|---|---|
| `key_found` | `prev["key_found"] or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)`: the agent's 7x7 view, where cells hidden by a wall or a closed door are 0 (unseen), empty cells 1, and object index 5 is `key` [code: minigrid_env.py:gen_obs, grid.py:process_vis]. The level holds one key, so any key in the view is the matching one. The same cells as `env.agent_sees(kx, ky)` for the key cell `(kx, ky)` |
| `has_matching_key` | `env.carrying is not None and env.carrying.type == "key"`: the level holds one key and it has the locked door's color, so a key in hand is the matching one |
| `target_door_open` | `any(c is not None and c.type == "door" and c.is_open for y in range(5 * B, 5 * B + 6) for c in [env.grid.get(env.width - 6, y)])`: `is_open` of the door in the target room's left wall, found by place because unlocking clears `is_locked` |
| `target_room_entered` | `prev["target_room_entered"] or (ax >= env.width - 6 and 0 <= ay - 5 * B <= 5)`: the target room's 6x6 block, door cell included |
| `target_picked_up` | `env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"` |

Caution: unlocking clears `is_locked` and sets `is_open` [code: world_object.py:Door.toggle], so once the door has been unlocked its color and its cell cannot be found by `is_locked`. Labeling code cannot keep them for the episode: it writes nothing between steps and reads only the previous valuation (Labeling API below). So the rows do not look for the locked door. They take the target room from the ball, which lies in that room until the pickup ends the episode, and the target door from its place in the room's left wall; the key in hand is the matching one because the level holds only that key. The benchmark reference labeler notes the locked door at the first labels instead and keeps its color and cell for the episode (`app/src/benchmark/reference_labels.py`, `KeyCorridor`); the rows give the same values at every step [run: `outputs/wave-tests/kc-page/fresh_layouts.py`, 50 layouts, 4 plans, 0 differences].

## Evidence

Layout and mission text [code: keycorridor.py:KeyCorridorEnv._gen_grid, roomgrid.py; run: `layout_checks.py`, 300 seeds]. The seven actions and `done` doing nothing [code: minigrid_env.py:step].

- Environment, unlocked side-room doors: [code: roomgrid.py:RoomGrid.connect_all]; the 215 of 300 count [run: `layout_checks.py`].
- Environment, another door with the locked door's color in 200 of 300 layouts: [run: `layout_checks.py`, 300 seeds].
- Environment, opaque rooms and the agent's view stopping at walls and closed doors [code: roomgrid.py:RoomGrid.__init__].
- Environment, left-column key [code: keycorridor.py:_gen_grid; run: `layout_checks.py`, 300/300].
- Objective: step limit `30 * 6**2 = 1080` [code: KeyCorridorEnv.__init__]. Only the mission's ball ends the episode [code: KeyCorridorEnv.step].
- Reading `key_found`: a clear view, as the agent's own observation shows it. The earlier reading counted every key cell inside the 7x7 box with walls ignored; it latched `key_found` through a wall in 9 of 50 layouts at the first step, where MiniGrid's `agent_sees` says the key is hidden (card fix 2, `outputs/wave-tests/card-fix-2/before/mechanics.py`). With the view reading, 0 of 50 layouts latch `key_found` at the first step, so none without a view [run: `outputs/wave-tests/card-fix-2/after/key_view_check.py`, seeds 1 to 50]. The view is available to labeling code as `env.gen_obs()["image"]` (Labeling API below), the same read the hand-written benchmark labeling (`armfm-wave3/manual-bundles/KeyCorridor-1/labeling.py:6-14`) uses. Key already in the box at reset in 39 of 300 layouts [run: `layout_checks.py`, earlier box reading].
- Reading `target_room_entered`: the environment's own room test counts the room's wall ring, door cell included, as inside [code: roomgrid.py:Room.pos_inside]. The benchmark labeling counts the doorway too (`labeling.py:31`, validated on 300 layouts per size in `armfm-wave3/manual-bundles/REPORT.md`). Ball next to the doorway in 23 of 300 layouts [run: `layout_checks.py`].
- Reading the target room and door by place: one key, one ball and one locked door in 500 of 500 layouts; the locked door lies in column `width - 6` and has the key's color; the ball lies in the same room row; the room's 6x6 block holds that one door and no other. Column `width - 6` holds more than one door in 500 of 500 layouts, and another unlocked door of the key's color in 117 of 500, so neither the column nor the color alone finds the target door [code: keycorridor.py:KeyCorridorEnv._gen_grid, roomgrid.py:RoomGrid.add_door, connect_all; run: `outputs/wave-tests/kc-page/layout_facts.py`, seeds 1 to 500].
- Reading the rows through the sandbox: the rows above, copied into a labeling and run through the runtime against the reference labeler, on layouts 1 to 50 and four plans (key, unlock, drop, ball; key, unlock, wait 1000; key, wait 1000; key, unlock, drop, stand in the room facing the ball, wait 20): 107,646 steps, 51,800 of them after the unlock and 50 of them the pickup step, 0 errors and 0 differences in all five propositions. The rows before this change differ from the unlock toggle on, in all 50 layouts of the three plans that unlock. Thirty random actions after the pickup, which belong to no episode, also give 0 differences [run: `outputs/wave-tests/kc-page/fresh_layouts.py`].
- Constraints, `has_matching_key` after `key_found`: [code: minigrid_env.py:step, gen_obs; run: `minigrid_family.py keycorridor explore`, 0 of 300 random episodes, 204 reached it, under the earlier box reading; and the solving plan on seeds 1 to 50, key held before `key_found` in 0 of 50 with the view reading, `outputs/wave-tests/card-fix-2/after/key_view_check.py`].
- Constraints, `target_door_open` after `has_matching_key`: [code: world_object.py:Door.toggle; run: same, 0 of 300, 57 reached it].
- Constraints, `target_room_entered` after `target_door_open`: [code: roomgrid.py:RoomGrid.connect_all, keycorridor.py:_gen_grid; run: `layout_checks.py`, wall ring holds only the locked door and walls, target unreachable without it, 300/300 seeds; `minigrid_family.py keycorridor explore`, 0 of 300, 43 reached it].
- Constraints, `target_picked_up` after `target_door_open`: [code and run as above; 0 of 300, 17 reached it].
- Constraints, `target_picked_up` after `target_room_entered`: [code: keycorridor.py:_gen_grid, roomgrid.py:Room.pos_inside; run: same, 0 of 300, 17 reached it].
- Constraints, `has_matching_key` with `target_picked_up`: [code: minigrid_env.py:step; run: `mechanics_check.py`, 0 of 300 random episodes].
- Constraints, `key_found` and `target_room_entered` latches: follow from the table of `environment.md`.
- Can: [code: minigrid_env.py:step].
- Cannot: [code: minigrid_env.py:step, Door.toggle; run: `mechanics_check.py`].
- `key_found` when the view changes to include the key: a turn, a move, or a toggle that opens a door in front of it [code: minigrid_env.py:step, Door.toggle, process_vis].
- `has_matching_key` and `target_door_open` can turn false [code: Door.toggle, `drop`].
- Example trace: seed 0, `MiniGrid-KeyCorridorS6R3-v0`, scripted solver with privileged grid access [run: `minigrid_family.py keycorridor 0`, log `keycorridor_trace_seed0.jsonl`]. Recorded under the earlier box reading of `key_found`; the step where it turns true is not re-checked under the view reading.

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
- `env.gen_obs()["image"]`: the agent's current 7x7 view as an array indexed `[column][row][channel]`.
  Channel `0` is the object index: `0` for a cell the agent cannot see (hidden by a wall or a
  closed door), `1` for an empty one, `5` for a key. For example,
  `any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)` is true while a key is in
  view. Labeling code runs in a sandbox that allows no NumPy method calls (`.any()`, `.sum()`);
  iterate the array with the built-in `any`.
- `env.width`, `env.height`: grid size.

Object classes cannot be imported. To scan the grid, guard empty cells with
`cell is not None` before reading an attribute. This expression checks whether any cell holds
a given object type:

    any(cell is not None and cell.type == "<type>" for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
