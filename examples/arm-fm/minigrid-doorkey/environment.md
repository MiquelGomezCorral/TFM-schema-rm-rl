# MiniGrid DoorKey

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/DoorKey>
- Gymnasium IDs: `MiniGrid-DoorKey-5x5-v0`, `MiniGrid-DoorKey-6x6-v0`,
  `MiniGrid-DoorKey-8x8-v0`, and `MiniGrid-DoorKey-16x16-v0`.
- Recommended default: `MiniGrid-DoorKey-8x8-v0`.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- Evidence tags: `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`); `[run]` is a scripted run or check on the real environment with `doorkey.py`, `layout_checks.py`, `mechanics_check.py` ; `unknown` means no source says.

## Environment

The agent starts on one side of a wall. A locked yellow door separates it from
the green goal, and a matching yellow key is accessible on the starting side.
The agent can turn, move forward, pick up or drop an object, and toggle a door.
The layout and initial pose may change between resets.

Layout [code: doorkey.py:DoorKeyEnv._gen_grid; run: `layout_checks.py`, 300 seeds]: a `size` x `size` grid with an outer wall. A wall spans the full height at a random column and has one gap, the locked yellow door, at a random row. The agent starts left of the wall, the yellow key lies on the left side, the goal sits at `(size-2, size-2)`. Nothing else is in the grid. The mission string is always `use the key to open the door and then get to the goal`. Actions are seven discrete keys: `left`, `right`, `forward`, `pickup`, `drop`, `toggle`, `done`; `done` does nothing [code: minigrid_env.py:step].

## Objective and episode boundary

The task is complete when the agent reaches the goal after using the key to unlock
and open the door. The stock environment terminates on reaching the goal and truncates
at its step limit. Its sparse success reward is
`1 - 0.9 * (step_count / max_steps)`.

Step limit: `10 * size**2`, 640 for 8x8 [code: doorkey.py:DoorKeyEnv.__init__]. The step that moves the agent onto the goal ends the episode, so no step follows `at_goal` [code: minigrid_env.py:step; run: `mechanics_check.py`].

## Proposition semantics

These are state conditions evaluated at every time point. They are specifications for
RM generation.

| id | kind | true when |
|---|---|---|
| `has_key` | condition | `env.carrying` is a key of color yellow |
| `door_open` | condition | the door's `is_open` is true; false again if the door is toggled shut |
| `at_goal` | condition, final step only | the cell under the agent holds the goal |
| `key_lost` | event, reading | `has_key` was true at the previous step, is false now, and `door_open` is false now; false on every other step |

`key_lost` reading: the description does not say whether it is an event or lingers. The table makes it an event: the labeling code reads one step of memory (`previous_valuation`) and the project's labeling prompt treats `key_lost` as an event; the published RM reads it only from the has-key state, where event and lingering condition agree [`task-rm-pairs.md:15`]. It differs from a lingering reading only after the key is dropped: the event is true for that one step, not until the key is picked up again. Fired in 94 of 300 random episodes [run: `doorkey.py`].

## Constraints

- `door_open` cannot become true before `has_key`: only `toggle` with a yellow key in hand unlocks the door [code: world_object.py:Door.toggle; run: `doorkey.py`, 0 of 300 random episodes, 207 reached `door_open`].
- `at_goal` cannot become true before `door_open`: the wall has no other gap [code: doorkey.py:_gen_grid; run: `layout_checks.py`, goal unreachable without the door in 300/300 seeds].
- `key_lost` and `door_open` never hold together: the event requires the door not open [definition above].
- `key_lost` and `has_key` never hold together: the event requires the key not carried [definition above].
- `key_lost` and `at_goal` never hold together: `key_lost` needs a `drop` step and `at_goal` a `forward` step [code: minigrid_env.py:step; run: `doorkey.py`, 0 of 300].

## What the agent can and cannot do

- Can: turn; `forward` onto an empty cell, an open door or the goal; `pickup` the key with empty hands; `drop` onto an empty cell in front; `toggle` the door in front [code: minigrid_env.py:step].
- Cannot: walk through a closed or locked door; unlock without the yellow key in hand (`toggle` then does nothing); pick up the door, walls or goal [code: world_object.py:can_pickup]; drop onto an occupied cell; relock a door [run: `mechanics_check.py`].
- Reaching the goal does not require dropping the key. The step onto the goal ends the episode, so `at_goal` is the last step [code: minigrid_env.py:step].
- `door_open` can turn false again: toggling an unlocked door shuts it [code: Door.toggle; run: `mechanics_check.py`]. Nothing relocks it [code: Door sets `is_locked` only in `__init__` and `toggle`, and `toggle` only clears it].
- Unlocking does not use up the key, so `has_key` stays true after `door_open` unless the agent drops it. Dropping it then is not `key_lost`, because the door is open [run: `mechanics_check.py`].
- `key_lost` can fire more than once while the door stays closed: pick the key up, drop it, pick it up, drop it [code: `pickup`, `drop`].

## Example trace

`MiniGrid-DoorKey-8x8-v0`, seed 0, scripted solver with privileged grid access [run: `doorkey.py`, log `doorkey_trace_seed0.jsonl`]. 17 steps, reward 0.976.

1. 2 turns and moves, no proposition changes
2. `pickup` (step 3): `has_key` true
3. 6 turns and moves, no proposition changes
4. `toggle` (step 10): `door_open` true
5. 6 turns and moves, no proposition changes
6. `forward` (step 17): `at_goal` true [episode terminated]

Variant, seed 1 [run: `doorkey.py`, log `doorkey_keylost_seed1.jsonl`]: `pickup` (step 7): `has_key` true. `drop` (step 8): `has_key` false, `key_lost` true. `pickup` (step 9): `has_key` true, `key_lost` false.

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
- `has_key`: The agent is currently carrying the yellow key that opens the locked door.
- `door_open`: The separating yellow door is currently open.
- `at_goal`: The agent is currently on the green goal tile.
- `key_lost`: The agent previously acquired the yellow key but is no longer carrying it before opening the door.

## Example tasks

- Eventually acquire the key.
- Open the door after acquiring the key.
- Reach the goal after opening the door.
