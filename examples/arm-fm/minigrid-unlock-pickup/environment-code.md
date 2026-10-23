# MiniGrid UnlockPickup: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- Gymnasium ID: `MiniGrid-UnlockPickup-v0`.
- Paper status: named in the ARM-FM human-intervention table, but no finalized RM is published in the paper repository.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`). `[run: script]` is a scripted run or check on the real environment, with `minigrid_family.py unlockpickup`, `layout_checks.py` or `mechanics_check.py`.

## Truth conditions in code

`prev` is `env.episode_memory["previous_valuation"]`. `K` and `D` stand for the `has_door_key` and `door_open` expressions. There is one door, so a scan by type finds it.

| id | expression |
|---|---|
| `has_door_key` | `env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])` |
| `door_open` | `any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])` |
| `target_picked_up` | `env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"` |
| `key_lost` | `prev["has_door_key"] and not K and not D` (event: previous step against the current state) |

## Evidence

Layout and mission text [code: unlockpickup.py:UnlockPickupEnv._gen_grid, roomgrid.py; run: `layout_checks.py`, 300 seeds]. The seven actions and `done` doing nothing [code: minigrid_env.py:step].

- Objective: step limit `8 * 6**2 = 288` [code: UnlockPickupEnv.__init__]. Only the mission's box ends the episode [code: UnlockPickupEnv.step].
- Proposition semantics, `key_lost` reading: read as an event because the labeling code sees one step of memory and the project's labeling prompt treats `key_lost` as an event. Fired in 166 of 300 random episodes [run: `minigrid_family.py unlockpickup explore`].
- Constraints, `door_open` after `has_door_key`: [code: world_object.py:Door.toggle; run: `minigrid_family.py unlockpickup explore`, 0 of 300 random episodes, 257 reached `door_open`].
- Constraints, `target_picked_up` after `door_open`: [code: roomgrid.py:RoomGrid._gen_grid, unlockpickup.py:_gen_grid; run: `layout_checks.py`, box unreachable without the door in 300/300 seeds].
- Constraints, `has_door_key` with `target_picked_up`: [code: minigrid_env.py:step; run: `mechanics_check.py`, 0 of 300 random episodes].
- Constraints, `key_lost` with `has_door_key` and `door_open`: follow from the `key_lost` definition in the table of `environment.md`.
- Constraints, `key_lost` with `target_picked_up`: [code: minigrid_env.py:step; run: 0 of 300].
- Can: [code: minigrid_env.py:step].
- Cannot: [run: `mechanics_check.py`].
- Last step is the mission's box [code: UnlockPickupEnv.step].
- `door_open` turns false by toggle and is never relocked [code: Door.toggle].
- Example trace: seed 0, `MiniGrid-UnlockPickup-v0`, scripted solver [run: `minigrid_family.py unlockpickup 0`, log `unlockpickup_trace_seed0.jsonl`].

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
