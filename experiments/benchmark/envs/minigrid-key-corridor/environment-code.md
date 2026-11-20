# MiniGrid KeyCorridor: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/KeyCorridorS6R3>
- Gymnasium IDs: `MiniGrid-KeyCorridorS6R3-v0` (room size 6) and `MiniGrid-KeyCorridorS4R3-v0` (room size 4), both with 3 room rows. The rows below read the room size from `env.room_size`, so they hold on both.
- Reproduction note: the paper's human-intervention table says S3R3, while its released code and artifacts use S6R3. This example follows the released artifact.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`). `[run: script]` is a scripted run or check on the real environment, with `minigrid_family.py keycorridor`, `layout_checks.py` or `mechanics_check.py`.

## Truth conditions in code

Shorthand: `prev` is `env.episode_memory["previous_valuation"]`; at the first step every proposition is false in it. `(ax, ay)` is `env.agent_pos`, `d` is `env.agent_dir`. `S` is `env.room_size`, the side of one room in cells, wall ring included (6 on S6R3, 4 on S4R3). `B` is the row (0 to 2, from the top) of the target room in the 3x3 room grid: `max([y for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "ball"], default=ay) // (S - 1)`. The level's only ball lies in the target room, so the ball's row gives `B`; once the agent holds the ball, which ends the episode, no ball is on the grid and `ay` gives `B`, because the agent picks the ball up from inside the room or from its doorway. The target room is the right-column room in row `B`: neighbouring rooms share their wall, so room rows start every `S - 1` cells: rows `(S - 1) * B` to `(S - 1) * B + S - 1`, columns `env.width - S` to `env.width - 1`. Its left wall, column `env.width - S`, holds the target door, the room's only door. `L` is the color of that door: `max([c.color for y in range((S - 1) * B, (S - 1) * B + S) for c in [env.grid.get(env.width - S, y)] if c is not None and c.type == "door"], default=None)`.

| id | expression |
|---|---|
| `key_found` | `prev["key_found"] or any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)`: the agent's 7x7 view, where cells hidden by a wall or a closed door are 0 (unseen), empty cells 1, and object index 5 is `key` [code: minigrid_env.py:gen_obs, grid.py:process_vis]. The level holds one key, so any key in the view is the matching one. The same cells as `env.agent_sees(kx, ky)` for the key cell `(kx, ky)` |
| `has_matching_key` | `env.carrying is not None and env.carrying.type == "key" and env.carrying.color == L`: a key in hand whose color is the target door's color `L` |
| `target_door_open` | `any(c is not None and c.type == "door" and c.is_open for y in range((S - 1) * B, (S - 1) * B + S) for c in [env.grid.get(env.width - S, y)])`: `is_open` of the door in the target room's left wall, found by place because unlocking clears `is_locked` |
| `target_room_entered` | `prev["target_room_entered"] or (ax >= env.width - S and 0 <= ay - (S - 1) * B <= S - 1)`: the target room's `S` x `S` block, door cell included |
| `target_picked_up` | `env.carrying is not None and env.carrying.type == "ball" and env.mission == f"pick up the {env.carrying.color} ball"` |

Caution: the target door is found by place, not by `is_locked`: unlocking clears `is_locked` [code: world_object.py:Door.toggle] and labeling code keeps no memory between steps (Labeling API below), so after the unlock no door is locked any more. The target door is still the door that starts locked, the one in the target room's left wall, with or without its lock.

## Evidence

Layout and mission text [code: keycorridor.py:KeyCorridorEnv._gen_grid, roomgrid.py; run: `layout_checks.py`, 300 seeds]. The seven actions and `done` doing nothing [code: minigrid_env.py:step].

- Room size: the counts below come from S6R3 unless they name S4R3. `check/layout_facts.py` takes the level as input and finds the same structure on S4R3 and S6R3 in 500 of 500 layouts each: one locked door, on the left wall of a right-column room whose wall ring holds no other door; the ball in that room; the key in the left column. Another door has the locked door's color in 323 of 500 on S4R3 (316 on S6R3), and the ball lies next to the doorway, inside the room, in 143 of 500 on S4R3 (39 on S6R3) [code: roomgrid.py:RoomGrid.__init__, keycorridor.py:_gen_grid; run: `check/layout_facts.py MiniGrid-KeyCorridorS4R3-v0` and `MiniGrid-KeyCorridorS6R3-v0`, seeds 1 to 500, 2026-11-20].

- Environment, unlocked side-room doors: [code: roomgrid.py:RoomGrid.connect_all]; the 215 of 300 count [run: `layout_checks.py`].
- Environment, another door with the locked door's color in 200 of 300 layouts: [run: `layout_checks.py`, 300 seeds].
- Environment, opaque rooms and the agent's view stopping at walls and closed doors [code: roomgrid.py:RoomGrid.__init__].
- Environment, left-column key [code: keycorridor.py:_gen_grid; run: `layout_checks.py`, 300/300].
- Objective: step limit `30 * room_size**2`, 1080 on S6R3 and 480 on S4R3 [code: KeyCorridorEnv.__init__]. Only the mission's ball ends the episode [code: KeyCorridorEnv.step].
- Reading `key_found`: a clear view, as the agent's own observation shows it. The earlier reading counted every key cell inside the 7x7 box with walls ignored; it latched `key_found` through a wall in 9 of 50 layouts at the first step, where MiniGrid's `agent_sees` says the key is hidden (card fix 2, `check/card-fix-2-before-mechanics.py`, the record of that run; on the current labeler it prints 0). With the view reading, 0 of 50 layouts latch `key_found` at the first step, so none without a view [run: `check/card-fix-2-after-key-view-check.py`, seeds 1 to 50]. The view is available to labeling code as `env.gen_obs()["image"]` (Labeling API below), the same read the hand-written benchmark labeling (`armfm-wave3/manual-bundles/KeyCorridor-1/labeling.py:6-14`) uses. Key already in the box at reset in 39 of 300 layouts [run: `layout_checks.py`, earlier box reading].
- Reading `target_room_entered`: the environment's own room test counts the room's wall ring, door cell included, as inside [code: roomgrid.py:Room.pos_inside]. The benchmark labeling counts the doorway too (`labeling.py:31`, validated on 300 layouts per size in `armfm-wave3/manual-bundles/REPORT.md`). Ball next to the doorway in 23 of 300 layouts [run: `layout_checks.py`].
- Reading the rows on every room size: the FARM labelings generated from the rows above on 2026-11-20 against the reference labeler, and both readings of `target_room_entered` against MiniGrid's own room test (the latched `Room.pos_inside` of the ball's room), 300 random episodes and 300 key-and-unlock episodes per size: 0 episodes differ in any of the five propositions, and `target_room_entered` never turns true outside the room. Checked on S4R3, S5R3 and S6R3 for `complex/bundles/farm/cx-sequence`, and on S4R3 for its paraphrase bundles `cx-sequence~p1`, `~p2` and `~p3`; also on all three sizes for `base/bundles/farm/base-key-corridor`, whose labeling defines four of the five (no `target_room_entered`). The labelings generated from the earlier rows, written for 6x6 rooms (column `width - 6`, rows every 5 cells), turned `target_room_entered` true outside the room before the locked door opened in 155 of 300 random S4R3 episodes and crashed on an off-grid `env.grid.get` in 144; the S6R3 FARM labelings of `cx-sequence` and `base-key-corridor` and the ARM-FM labeling of `cx-sequence` give the same counts [run: `check/room_size_check.py`, 2026-11-20].
- Reading the target room and door by place: one key, one ball and one locked door in 500 of 500 layouts; the locked door lies in column `width - S` and has the key's color; the ball lies in the same room row; the room's `S` x `S` block holds that one door and no other. Column `width - S` holds more than one door in 500 of 500 layouts, and another unlocked door of the key's color in 117 of 500 (126 of 500 on S4R3), so neither the column nor the color alone finds the target door [code: keycorridor.py:KeyCorridorEnv._gen_grid, roomgrid.py:RoomGrid.add_door, connect_all; run: `check/layout_facts.py`, seeds 1 to 500, S6R3 and S4R3].
- Reading the rows through the sandbox: the rows above (the key in hand tested against the target door's color), copied into a labeling and run through the runtime against the reference labeler, on layouts 1 to 50 and four plans (key, unlock, drop, ball; key, unlock, wait 1000; key, wait 1000; key, unlock, drop, stand in the room facing the ball, wait 20): 107,646 steps, 51,800 of them after the unlock and 50 of them the pickup step, 0 errors and 0 differences in all five propositions. The rows before this change differ from the unlock toggle on, in all 50 layouts of the three plans that unlock. Thirty random actions after the pickup, which belong to no episode, also give 0 differences [run: `check/fresh_layouts.py`].
- Constraints, `has_matching_key` after `key_found`: [code: minigrid_env.py:step, gen_obs; run: `minigrid_family.py keycorridor explore`, 0 of 300 random episodes, 204 reached it, under the earlier box reading; and the solving plan on seeds 1 to 50, key held before `key_found` in 0 of 50 with the view reading, `check/card-fix-2-after-key-view-check.py`].
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
- `env.room_size`: the side of one room in cells, its wall ring included (6 on S6R3, 4 on S4R3).
- Layout for lookups: neighbouring rooms share their wall, so room rows start every `env.room_size - 1` cells (room row `y // (env.room_size - 1)`). The target room is the right-column room that holds the ball, so the ball's row gives its room row. That room's left wall, column `env.width - env.room_size`, holds its only door, the door that starts locked. Unlocking clears `is_locked` and labeling code keeps no memory, so find this door by place, not by `is_locked`.

Object classes cannot be imported. To scan the grid, guard empty cells with
`cell is not None` before reading an attribute. This expression checks whether any cell holds
a given object type:

    any(cell is not None and cell.type == "<type>" for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
