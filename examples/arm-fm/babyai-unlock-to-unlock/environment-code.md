# BabyAI UnlockToUnlock: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/UnlockToUnlock>
- Gymnasium ID: `BabyAI-UnlockToUnlock-v0`.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`). `[run]` is a scripted run or check on the real environment with `minigrid_family.py unlocktounlock`, `layout_checks.py`, `mechanics_check.py`. `unknown` means no source says.

## Truth conditions in code

`prev = env.episode_memory["previous_valuation"]`. The grid is 16x6 with walls at x=5 and x=10, so door A is at x=5 and door B at x=10, at any y. The x positions follow from three 6x6 rooms in a row and were read once on seed 0 (doors at (5, 4) and (10, 3)).

- `has_prerequisite_key`: `any(d is not None and d.type == "door" and env.carrying is not None and env.carrying.type == "key" and env.carrying.color == d.color for y in range(env.height) for d in [env.grid.get(10, y)])`
- `prerequisite_door_open`: `any(d is not None and d.type == "door" and d.is_open for y in range(env.height) for d in [env.grid.get(10, y)])`
- `has_target_door_key`: as `has_prerequisite_key` with `env.grid.get(5, y)`.
- `target_door_open`: as `prerequisite_door_open` with `env.grid.get(5, y)`.
- `target_ball_picked_up`: `env.carrying is not None and env.carrying.type == "ball"`
- `required_key_lost`: `env.carrying is None and ((prev["has_prerequisite_key"] and not <prerequisite_door_open expression>) or (prev["has_target_door_key"] and not <target_door_open expression>))`. `env.carrying is None` is enough for "not carried now": a key leaves the hands only by `drop`, and the hands are then empty.

These expressions are derived from the definitions in `environment.md`; they were not run as labeling code.

## Evidence

Environment and objective
- Layout (three 6x6 rooms, grid 16x6, agent in the middle room, ball left, door A and key A, door B and key B, colors differ, mission `pick up the ball`): [code: babyai/unlock.py:UnlockToUnlock.gen_mission; run: `layout_checks.py`, 300 seeds].
- Seven actions, `done` does nothing: [code: minigrid_env.py:step].
- Step limit `30 * 6**2 = 1080`: [code: UnlockToUnlock.__init__].
- Picking up the ball ends the episode: [run: `minigrid_family.py unlocktounlock`, terminated at the pickup].

Proposition semantics
- `required_key_lost` as an event: labeling reads one step of memory (`previous_valuation`) and the project's labeling prompt treats `key_lost` as an event. The published RM maps `lost_y_key` to it "in the prerequisite stage" and `lost_r_key` "in the target-door stage" [`task-rm-pairs.md:17,20`]. Fired in 135 of 300 random episodes [run: `minigrid_family.py unlocktounlock explore`].

Constraints
- `prerequisite_door_open` after `has_prerequisite_key`: [code: world_object.py:Door.toggle; run: `minigrid_family.py unlocktounlock explore`, 0 of 300 random episodes, 186 reached it].
- `target_door_open` after `has_target_door_key`: [code: Door.toggle; run: same, 0 of 300, 38 reached it].
- `has_target_door_key` after `prerequisite_door_open`: [code: unlock.py:gen_mission; run: `layout_checks.py`, key A unreachable before door B opens in 300/300 seeds].
- `target_ball_picked_up` after `target_door_open`: [code: unlock.py:gen_mission; run: `layout_checks.py`, 300/300 seeds].
- `has_prerequisite_key` and `has_target_door_key` never together: [code: minigrid_env.py:step; run: `mechanics_check.py`, 0 of 300 random episodes].
- `has_prerequisite_key` and `target_ball_picked_up`; `has_target_door_key` and `target_ball_picked_up`: [code: minigrid_env.py:step; run: same].
- `required_key_lost` with each of `has_prerequisite_key`, `has_target_door_key`, `target_ball_picked_up`: [code: minigrid_env.py:step; run: `unlocktounlock_explore_stats.json`, 0 of 300].

What the agent can and cannot do
- Can list: [code: minigrid_env.py:step].
- Cannot list (door without key, two objects, key A or ball behind closed doors, occupied cell): [run: `mechanics_check.py`, `layout_checks.py`].
- A dropped key can block a doorway and can be picked up again: [run: seen while writing `minigrid_family.py`].
- Dropping a key after its own door is open does not fire `required_key_lost`: no tag in the old file; follows from the event definition.
- Dropping key B while door B is closed fires `required_key_lost`, 135 of 300 random episodes had a firing: [run: `unlocktounlock_explore_stats.json`].
- Doors can be toggled shut and are never relocked: [code: Door.toggle].

Example trace
- `BabyAI-UnlockToUnlock-v0`, seed 0, scripted solver, 39 steps, reward 0.968: [run: `minigrid_family.py unlocktounlock 0`, log `unlocktounlock_trace_seed0.jsonl`].

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
