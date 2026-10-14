# MiniGrid KeyCorridor S6R3

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/KeyCorridorS6R3>
- Gymnasium ID: `MiniGrid-KeyCorridorS6R3-v0`.
- Reproduction note: the paper's human-intervention table says S3R3, while its released
  code and artifacts use S6R3. This example follows the released artifact.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- Evidence tags: `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`); `[run]` is a scripted run or check on the real environment with `minigrid_family.py keycorridor`, `layout_checks.py`, `mechanics_check.py` ; `unknown` means no source says.

## Environment

The agent begins in a central corridor connected to several rooms. The mission's target
object is behind a locked door, while the matching key is hidden in another randomly
selected room. The mission reveals the target object's color and type but not the key's
location.

Layout [code: keycorridor.py:KeyCorridorEnv._gen_grid, roomgrid.py; run: `layout_checks.py`, 300 seeds]: 3x3 rooms of 6x6 (grid 16x16). The three rooms of the middle column form a hallway, where the agent starts. `connect_all` adds unlocked doors of random color between neighbouring rooms, side room to hallway or side room to the room above or below, until every room is reachable; a side room may open only onto another side room (215 of 300 layouts have at least one unlocked side room without a door onto the hallway) [code: roomgrid.py:RoomGrid.connect_all]. Those doors start closed and unlocked, and `toggle` opens them without a key. One door is locked: it is on the left wall of one right-column room (random row), and the target lies in that room. The matching key lies in one of the three left-column rooms (random room and cell). The target is always a ball in this id, so the mission reads `pick up the <color> ball`. In 200 of 300 layouts another door has the locked door's color, so color alone does not identify the locked door; `is_locked` does. Rooms are opaque: the agent sees through no wall or closed door [code: roomgrid.py:RoomGrid.__init__]. Actions are seven discrete keys: `left`, `right`, `forward`, `pickup`, `drop`, `toggle`, `done`; `done` does nothing [code: minigrid_env.py:step].

## Objective and episode boundary

The mission is complete when the designated target object is picked up. The stock
environment terminates on that pickup and truncates at its step limit.

Step limit `30 * 6**2 = 1080` [code: KeyCorridorEnv.__init__]. Only picking up the mission's ball ends the episode [code: KeyCorridorEnv.step].

## Proposition semantics

The target and matching key are determined from the current randomized mission and
layout, not hard-coded colors. The mission names only the target object. The matching
key and the locked door share one color that is independent of the target's color.
Exactly one door starts locked, and it guards the target's room.

| id | kind | true when |
|---|---|---|
| `key_found` | latch, reading | the matching key's cell lies in the 7x7 box in front of the agent now (the agent's row or column and the 6 cells ahead, 3 cells to each side), walls ignored; or `key_found` was true at the previous step |
| `has_matching_key` | condition | `env.carrying` is a key of the locked door's color |
| `target_door_open` | condition | the locked door's `is_open` is true; false again if toggled shut |
| `target_room_entered` | latch, reading | the agent stands on the locked doorway or on a cell inside the target room now (`Room.pos_inside`: the room's 6x6 block, door cell included); or `target_room_entered` was true at the previous step |
| `target_picked_up` | condition, final step only | `env.carrying` is the mission's ball |

Readings, both choices of this file:

- `key_found`: the description does not say what "located" means. The labeling API has no visibility mask, so a key behind a closed door or a wall inside the box counts; occlusion is unknown to the API. In 39 of 300 layouts the key is already inside the box at reset, so `key_found` can be true at the first step [run: `layout_checks.py`]. The hand-written benchmark labeling (`armfm-wave3/manual-bundles/KeyCorridor-1/labeling.py:6-14`) reads the occluded view through `env.gen_obs()`, which the documented API does not offer, so the two can differ.
- `target_room_entered`: the description does not say whether the doorway is inside. The table counts it. MiniGrid's own room test counts the room's wall ring, door cell included, as inside [code: roomgrid.py:Room.pos_inside], and the benchmark labeling counts it too (`labeling.py:31`, validated on 300 layouts per size in `armfm-wave3/manual-bundles/REPORT.md`). The ball lies next to the doorway in 23 of 300 layouts [run: `layout_checks.py`], so picking it up from the doorway is a regular case.

## Constraints

- `has_matching_key` cannot become true before `key_found`: the agent picks the key up from the cell in front of it, which lies in the box [code: minigrid_env.py:step, get_view_exts; run: `minigrid_family.py keycorridor explore`, 0 of 300 random episodes, 204 reached it].
- `target_door_open` cannot become true before `has_matching_key`: only `toggle` with the matching key unlocks the door [code: world_object.py:Door.toggle; run: same, 0 of 300, 57 reached it].
- `target_room_entered` cannot become true before `target_door_open`: the locked door is the room's only way in, because `connect_all` adds no door to a locked room [code: roomgrid.py:RoomGrid.connect_all, keycorridor.py:_gen_grid; run: `layout_checks.py`, wall ring holds only the locked door and walls, target unreachable without it, 300/300 seeds; `minigrid_family.py keycorridor explore`, 0 of 300, 43 reached it].
- `target_picked_up` cannot become true before `target_door_open`: same reason [code and run as above; 0 of 300, 17 reached it].
- `target_picked_up` cannot become true before `target_room_entered`: the ball lies inside the room, and the only cells that face it are inside cells or the doorway, which count as entered [code: keycorridor.py:_gen_grid, roomgrid.py:Room.pos_inside; run: same, 0 of 300, 17 reached it].
- `has_matching_key` and `target_picked_up` never hold together: the agent holds one object [code: minigrid_env.py:step; run: `mechanics_check.py`, 0 of 300 random episodes].
- `key_found` cannot become false once true: it is a latch [definition above].
- `target_room_entered` cannot become false once true: it is a latch [definition above].

## What the agent can and cannot do

- Can: turn; `forward` onto an empty cell or an open door; `toggle` any closed unlocked door open; `pickup` the key or the ball with empty hands; `drop` onto an empty cell in front [code: minigrid_env.py:step].
- Cannot: walk through a closed door before toggling it; open the locked door without the matching key; carry the key and the ball at once [code: minigrid_env.py:step, Door.toggle; run: `mechanics_check.py`].
- The agent's own view stops at walls and closed doors [code: roomgrid.py:RoomGrid.__init__]; `key_found` ignores that (reading above).
- `key_found` turns true only on a turn or a move: the key does not move on its own, and `toggle`, `pickup` and `drop` leave the agent's cell and direction unchanged [code: minigrid_env.py:step]. Opening a door does not change the box.
- After `target_door_open` the key must be dropped before the ball can be picked up.
- `has_matching_key` and `target_door_open` can turn false again: the agent can drop the key and shut the door [code: Door.toggle, `drop`].
- Unknown: which left-column room and cell holds the key. The mission gives no hint; the left column is known [code: keycorridor.py:_gen_grid; run: `layout_checks.py`, 300/300].

## Example trace

`MiniGrid-KeyCorridorS6R3-v0`, seed 0, mission `pick up the yellow ball`, scripted solver with privileged grid access [run: `minigrid_family.py keycorridor 0`, log `keycorridor_trace_seed0.jsonl`]. 40 steps, reward 0.967.

1. 3 turns and moves, no proposition changes
2. `forward` (step 4): `key_found` true
3. 1 turn or move, no proposition changes
4. `toggle` (step 6): no proposition changes (the door between the hallway and a left-column room opens)
5. 8 turns and moves, no proposition changes
6. `pickup` (step 15): `has_matching_key` true
7. 13 turns and moves, no proposition changes
8. `toggle` (step 29): `target_door_open` true
9. 1 turn or move, no proposition changes
10. `drop` (step 31): `has_matching_key` false
11. 1 turn or move, no proposition changes
12. `forward` (step 33): `target_room_entered` true (the agent stands on the doorway)
13. 6 turns and moves, no proposition changes
14. `pickup` (step 40): `target_picked_up` true [episode terminated]

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

## Propositions
- `key_found`: The agent has located the key matching the target room's locked door.
- `has_matching_key`: The agent is currently carrying that matching key.
- `target_door_open`: The locked door guarding the mission target is currently open.
- `target_room_entered`: The agent has entered the room containing the mission target.
- `target_picked_up`: The agent is currently carrying the mission's designated object.

## Example tasks

- Eventually pick up the target object.
- Find the matching key before opening the target door.
- Open the target door before picking up the target object.
