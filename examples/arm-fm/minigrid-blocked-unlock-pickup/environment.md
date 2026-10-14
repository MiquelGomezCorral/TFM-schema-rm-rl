# MiniGrid BlockedUnlockPickup

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/BlockedUnlockPickup>
- Gymnasium ID: `MiniGrid-BlockedUnlockPickup-v0`.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- Evidence tags: `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`); `[run]` is a scripted run or check on the real environment with `minigrid_family.py blocked`, `layout_checks.py`, `mechanics_check.py` ; `unknown` means no source says.

## Environment

Two rooms are connected by a locked door. A ball initially blocks access to the door,
a matching key is in the starting room, and the mission's target box is in the other
room. The ball must be moved away, the key acquired, and the door unlocked before the
target can be collected. Colors and positions may vary between resets.

Layout [code: blockedunlockpickup.py:BlockedUnlockPickupEnv._gen_grid; run: `layout_checks.py`, 300 seeds]: two 6x6 rooms, one locked door of random color in the shared wall. A ball of random color sits on the cell directly in front of the door on the start side. Before the door is first open, that cell is the only reachable cell the agent can toggle the door from. The key, in the door's color, lies in the start room and is reachable without moving the ball. One box of random color lies in the right room. The mission names the box: `pick up the <color> box`. Actions are seven discrete keys: `left`, `right`, `forward`, `pickup`, `drop`, `toggle`, `done`; `done` does nothing [code: minigrid_env.py:step].

## Objective and episode boundary

The mission is complete when the agent picks up the designated target box. The stock
environment terminates on that pickup and truncates at its step limit.

Step limit `16 * 6**2 = 576` [code: BlockedUnlockPickupEnv.__init__]. Only picking up the mission's box ends the episode [code: BlockedUnlockPickupEnv.step].

## Proposition semantics

The propositions denote observable task progress, independent of the raw action used
to cause it.

| id | kind | true when |
|---|---|---|
| `blocker_moved` | condition, reading | the cell in front of the door holds no ball; a ball in the agent's hand counts as moved; false again if the ball is dropped back there |
| `has_door_key` | condition | `env.carrying` is a key whose color equals the door's color |
| `door_open` | condition | the door's `is_open` is true; false again if toggled shut |
| `target_picked_up` | condition, final step only | `env.carrying` is the box the mission names |
| `key_lost` | event, reading | `has_door_key` was true at the previous step, is false now, and `door_open` is false now; false on every other step |

Readings: the descriptions of `blocker_moved` and `key_lost` leave open how they behave over time.

- `blocker_moved` is a condition, not a latch: it is false again if the ball is dropped back on that cell (13 of 300 random episodes [run: `blocked_explore_stats.json`]). The published RM used `has_ball` (carrying the ball), which is stricter [`task-rm-pairs.md`]; do not expect carrying here.
- `key_lost` is an event: the labeling code reads one step of memory (`previous_valuation`) and the project's labeling prompt treats `key_lost` as an event. It differs from a lingering reading only after the key is dropped: the event is true for that one step, not until the key is picked up again. Fired in 181 of 300 random episodes [run: `minigrid_family.py blocked explore`].

## Constraints

- `door_open` cannot become true before `blocker_moved`: before the door is first open, the ball's cell is the only reachable cell the agent can toggle it from [code: blockedunlockpickup.py:_gen_grid; run: `layout_checks.py`, that cell unreachable while the ball stays in 300/300 seeds; `blocked_explore_stats.json`, 0 of 300 random episodes, 67 reached `door_open`].
- `door_open` cannot become true before `has_door_key`: only `toggle` with the matching key unlocks the door [code: world_object.py:Door.toggle].
- `target_picked_up` cannot become true before `door_open`: the box room has no other entrance [run: `layout_checks.py`, 300/300 seeds].
- `has_door_key` and `target_picked_up` never hold together: the agent holds one object, so `pickup` does nothing with the key in hand [code: minigrid_env.py:step; run: `mechanics_check.py`].
- `key_lost` and `has_door_key` never hold together: the event requires the key not carried [definition above].
- `key_lost` and `door_open` never hold together: the event requires the door not open [definition above].
- `key_lost` and `target_picked_up` never hold together: `key_lost` needs a `drop` step and `target_picked_up` a `pickup` step [code: minigrid_env.py:step; run: `blocked_explore_stats.json`, 0 of 300].

## What the agent can and cannot do

- Can: turn; `forward` onto an empty cell or an open door; `pickup` the ball, key or box with empty hands; `drop` onto an empty cell in front; `toggle` the door in front [code: minigrid_env.py:step].
- Cannot: push or walk through the ball; unlock without the matching key; carry two objects; drop onto an occupied cell; relock a door [run: `mechanics_check.py`].
- Only `pickup` and `drop` move the ball: `toggle` and `forward` leave it in place [run: `mechanics_check.py`]. `blocker_moved` turns true on the `pickup` of the ball. With the ball in hand `pickup` of the key does nothing, so the ball must be dropped before the key is picked up.
- The key may be picked up first (149 of 300 random episodes had `has_door_key` before `blocker_moved` [run: `blocked_explore_stats.json`]). It must then be dropped to pick up the ball, and that drop fires `key_lost` while the door is closed.
- `blocker_moved` can turn false again when the ball is dropped back in front of the door.

## Example trace

`MiniGrid-BlockedUnlockPickup-v0`, seed 0, mission `pick up the purple box`, scripted solver [run: `minigrid_family.py blocked 0`, log `blocked_trace_seed0.jsonl`]. 28 steps, reward 0.956.

1. 3 turns and moves, no proposition changes
2. `pickup` (step 4): `blocker_moved` true
3. 1 turn or move, no proposition changes
4. `drop` (step 6): no proposition changes
5. 5 turns and moves, no proposition changes
6. `pickup` (step 12): `has_door_key` true
7. 4 turns and moves, no proposition changes
8. `toggle` (step 17): `door_open` true
9. 1 turn or move, no proposition changes
10. `drop` (step 19): `has_door_key` false
11. 8 turns and moves, no proposition changes
12. `pickup` (step 28): `target_picked_up` true [episode terminated]

The `drop` at step 6 puts the ball down away from the door; it changes no proposition. The `drop` at step 19 frees the hands for the box; `key_lost` stays false because the door is open.

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
- `blocker_moved`: The blocking ball no longer prevents access to the locked door.
- `has_door_key`: The agent is currently carrying the key matching the locked door.
- `door_open`: The door leading to the target room is currently unlocked and open.
- `target_picked_up`: The agent is currently carrying the mission's designated box.
- `key_lost`: The matching key was acquired and then lost before the door was opened.

## Example tasks

- Eventually pick up the target box.
- Move the blocker before opening the door.
- Acquire the matching key before opening the door.
