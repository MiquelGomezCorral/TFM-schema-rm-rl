# MiniGrid UnlockPickup

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- Gymnasium ID: `MiniGrid-UnlockPickup-v0`.
- Paper status: named in the ARM-FM human-intervention table, but no finalized RM is
  published in the paper repository.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- Evidence tags: `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`); `[run]` is a scripted run or check on the real environment with `minigrid_family.py unlockpickup`, `layout_checks.py`, `mechanics_check.py` ; `unknown` means no source says.

## Environment

Two rooms are connected by a locked door. The target box is in the second room. A key
matching the door is available in the starting room. Object color and placement may
change between resets. The agent can turn, move, pick up or drop objects, and toggle
the door.

Layout [code: unlockpickup.py:UnlockPickupEnv._gen_grid, roomgrid.py; run: `layout_checks.py`, 300 seeds]: two 6x6 rooms side by side (grid 11x6) share one wall. Its one door is locked and has a random color. The agent starts in the left room with the key, which has the door's color. One box of random color lies in the right room. Nothing else is in the grid. The mission names the box: `pick up the <color> box`. Actions are seven discrete keys: `left`, `right`, `forward`, `pickup`, `drop`, `toggle`, `done`; `done` does nothing [code: minigrid_env.py:step].

## Objective and episode boundary

The mission is to unlock the door and pick up the designated box. The stock environment
terminates when the correct box is picked up and truncates at its step limit.

Step limit `8 * 6**2 = 288` [code: UnlockPickupEnv.__init__]. Only picking up the mission's box ends the episode [code: UnlockPickupEnv.step].

## Proposition semantics

The target is the box named by the current mission, not any box that may be present.

| id | kind | true when |
|---|---|---|
| `has_door_key` | condition | `env.carrying` is a key whose color equals the door's color |
| `door_open` | condition | the door's `is_open` is true; false again if the door is toggled shut |
| `target_picked_up` | condition, final step only | `env.carrying` is the box the mission names (the only box) |
| `key_lost` | event, reading | `has_door_key` was true at the previous step, is false now, and `door_open` is false now; false on every other step |

`key_lost` reading: the description does not say whether it is an event or lingers. The table makes it an event: the labeling code reads one step of memory (`previous_valuation`) and the project's labeling prompt treats `key_lost` as an event. It differs from a lingering reading only after the key is dropped: the event is true for that one step, not until the key is picked up again. Fired in 166 of 300 random episodes [run: `minigrid_family.py unlockpickup explore`].

## Constraints

- `door_open` cannot become true before `has_door_key`: only `toggle` with the matching key unlocks the door [code: world_object.py:Door.toggle; run: `minigrid_family.py unlockpickup explore`, 0 of 300 random episodes, 257 reached `door_open`].
- `target_picked_up` cannot become true before `door_open`: the box room has no other entrance [code: roomgrid.py:RoomGrid._gen_grid, unlockpickup.py:_gen_grid; run: `layout_checks.py`, box unreachable without the door in 300/300 seeds].
- `has_door_key` and `target_picked_up` never hold together: the agent holds one object, so `pickup` does nothing with the key in hand [code: minigrid_env.py:step; run: `mechanics_check.py`, 0 of 300 random episodes].
- `key_lost` and `has_door_key` never hold together: the event requires the key not carried [definition above].
- `key_lost` and `door_open` never hold together: the event requires the door not open [definition above].
- `key_lost` and `target_picked_up` never hold together: `key_lost` needs a `drop` step and `target_picked_up` a `pickup` step [code: minigrid_env.py:step; run: 0 of 300].

## What the agent can and cannot do

- Can: turn; `forward` onto an empty cell or an open door; `pickup` the key or the box with empty hands; `drop` onto an empty cell in front; `toggle` the door in front [code: minigrid_env.py:step].
- Cannot: walk through a closed or locked door; unlock without the matching key in hand; pick up a second object; drop onto an occupied cell; relock a door [run: `mechanics_check.py`].
- After `door_open` the key must be dropped before the box can be picked up. That drop is not `key_lost`, because the door is already open.
- `target_picked_up` is the last step: only the mission's box ends the episode [code: UnlockPickupEnv.step].
- `door_open` can turn false again (toggle) and is never relocked [code: Door.toggle].

## Example trace

`MiniGrid-UnlockPickup-v0`, seed 0, mission `pick up the purple box`, scripted solver [run: `minigrid_family.py unlockpickup 0`, log `unlockpickup_trace_seed0.jsonl`]. 18 steps, reward 0.944.

1. 1 turn or move, no proposition changes
2. `pickup` (step 2): `has_door_key` true
3. 4 turns and moves, no proposition changes
4. `toggle` (step 7): `door_open` true
5. 1 turn or move, no proposition changes
6. `drop` (step 9): `has_door_key` false
7. 8 turns and moves, no proposition changes
8. `pickup` (step 18): `target_picked_up` true [episode terminated]

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
- `has_door_key`: The agent is currently carrying the key whose color matches the locked door.
- `door_open`: The locked door leading to the target room is currently open.
- `target_picked_up`: The agent is currently carrying the mission's designated box.
- `key_lost`: The agent previously acquired the matching key but is no longer carrying it before opening the door.

## Example tasks

- Eventually pick up the target box.
- Acquire the matching key before opening the door.
- Open the door before picking up the target box.
