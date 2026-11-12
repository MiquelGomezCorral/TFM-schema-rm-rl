# MiniGrid DoorKey: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/DoorKey>
- Gymnasium IDs: `MiniGrid-DoorKey-5x5-v0`, `MiniGrid-DoorKey-6x6-v0`, `MiniGrid-DoorKey-8x8-v0`, and `MiniGrid-DoorKey-16x16-v0`. Recommended default: `MiniGrid-DoorKey-8x8-v0`.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`). `[run: script]` is a scripted run or check on the real environment, with `doorkey.py`, `layout_checks.py` or `mechanics_check.py`.

## Truth conditions in code

`prev` is `env.episode_memory["previous_valuation"]`. `H` and `D` stand for the `has_key` and `door_open` expressions. There is one door, so a scan by type finds it.

| id | expression |
|---|---|
| `has_key` | `env.carrying is not None and env.carrying.type == "key" and env.carrying.color == "yellow"` |
| `door_open` | `any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])` |
| `at_goal` | `any(c is not None and c.type == "goal" for c in [env.grid.get(*env.agent_pos)])` |
| `key_lost` | `prev["has_key"] and not H and not D` (event: previous step against the current state) |

## Evidence

Layout and mission text [code: doorkey.py:DoorKeyEnv._gen_grid; run: `layout_checks.py`, 300 seeds]. The seven actions and `done` doing nothing [code: minigrid_env.py:step].

- Environment, objective: step limit `10 * size**2` [code: doorkey.py:DoorKeyEnv.__init__]. Reward `1 - 0.9 * (step_count / max_steps)`: stock environment behavior, untagged in the previous file.
- Objective, `at_goal` is last: the step onto the goal ends the episode [code: minigrid_env.py:step; run: `mechanics_check.py`].
- Proposition semantics, `key_lost` reading: read as an event because the labeling code sees one step of memory and the project's labeling prompt treats `key_lost` as an event. The published RM uses it only from the has-key state [`task-rm-pairs.md:15`]. Fired in 94 of 300 random episodes [run: `doorkey.py`].
- Constraints, `door_open` after `has_key`: [code: world_object.py:Door.toggle; run: `doorkey.py`, 0 of 300 random episodes, 207 reached `door_open`].
- Constraints, `at_goal` after `door_open`: [code: doorkey.py:_gen_grid; run: `layout_checks.py`, goal unreachable without the door in 300/300 seeds].
- Constraints, `key_lost` with `door_open` and `has_key`: follow from the `key_lost` definition in the table of `environment.md`.
- Constraints, `key_lost` with `at_goal`: [code: minigrid_env.py:step; run: `doorkey.py`, 0 of 300].
- Can: [code: minigrid_env.py:step].
- Cannot: pick up the door, walls or goal [code: world_object.py:can_pickup]; drop onto an occupied cell, relock a door [run: `mechanics_check.py`]. Closed door and unlocking without the key: untagged in the previous file.
- Goal is the last step [code: minigrid_env.py:step].
- `door_open` can turn false again [code: Door.toggle; run: `mechanics_check.py`]. Nothing relocks it [code: Door sets `is_locked` only in `__init__` and `toggle`, and `toggle` only clears it].
- Key kept after unlocking, dropping it is not `key_lost` [run: `mechanics_check.py`].
- `key_lost` can repeat [code: `pickup`, `drop` in minigrid_env.py:step].
- Example trace: seed 0, `MiniGrid-DoorKey-8x8-v0`, scripted solver with privileged grid access [run: `doorkey.py`, log `doorkey_trace_seed0.jsonl`]. Variant: seed 1 [run: `doorkey.py`, log `doorkey_keylost_seed1.jsonl`].

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
