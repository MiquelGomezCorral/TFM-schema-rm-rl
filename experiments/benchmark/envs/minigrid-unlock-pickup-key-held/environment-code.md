# MiniGrid UnlockPickup, key already held: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them. It is the plain level of `../minigrid-unlock-pickup/` with one change: the agent starts holding the key. The rest of that folder's notes (rules, constraints, evidence) apply.

## Source and runtime

- Source: `app/src/arm_fm/forced_starts.py:UnlockPickupKeyHeldEnv`, a subclass of MiniGrid's `UnlockPickupEnv`. Importing `src.arm_fm.environments` registers the id.
- Gymnasium ID: `MiniGrid-UnlockPickup-KeyHeld-v0`. The plain id `MiniGrid-UnlockPickup-v0` is untouched.
- At reset the key leaves the floor and goes into the hands (`env.carrying`); the layout is the plain level's for the same seed. `drop` becomes `done` on the first step (`env.step_count == 0`), so the first labels always see the key; the key can be put down from the second step.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`) or `forced_starts.py`. `[run: check_forced_starts.py]` is `experiments/benchmark/scripts/check_forced_starts.py` on the real environment, reset seeds 1 to 20, and a scripted solve over seeds 1 to 300.

## Truth conditions in code

`prev` is `env.episode_memory["previous_valuation"]`; at the first step every proposition is false in it. `K` and `D` stand for the `has_door_key` and `door_open` expressions. There is one door, so a scan by type finds it.

| id | expression |
|---|---|
| `has_door_key` | `env.carrying is not None and env.carrying.type == "key" and any(c is not None and c.type == "door" and c.color == env.carrying.color for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])` |
| `door_open` | `any(c is not None and c.type == "door" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])` |
| `target_picked_up` | `env.carrying is not None and env.carrying.type == "box" and env.mission == f"pick up the {env.carrying.color} box"` |
| `key_lost` | `prev["has_door_key"] and not K and not D` (event: previous step against the current state) |

## Evidence

What this level changes, against the plain level for the same reset seed [run: check_forced_starts.py, seeds 1 to 20, 20/20 on every line]:

- Layout and mission text: equal to the plain level's (agent cell and direction, door, box, mission) except the key, which is in the hands and not on the floor. The key has the door's color and the door is locked [code: forced_starts.py:UnlockPickupKeyHeldEnv.reset].
- `has_door_key` start: true at the first step, and true on every one of 100 idle steps; the rule `RespondedExistence(has_door_key, door_open)` fails on that idle episode.
- `drop` on the first step keeps the key (`drop` becomes `done`); with turns, a later `drop` puts the key down [code: forced_starts.py:UnlockPickupKeyHeldEnv.step].
- Box reachable: a scripted agent that opens the door, drops the key and takes the box ends with reward above 0 on seeds 1 to 300.
- Example trace: seed 1, scripted solver (`toggle` door, `drop`, `pickup` box) [run: check_forced_starts.py].

Everything else is the plain level's code, with the evidence in `../minigrid-unlock-pickup/environment-code.md`: the `key_lost` reading, the constraints (`door_open` after `has_door_key`, `target_picked_up` after `door_open`, the pairs that never hold together), what the agent can and cannot do, `door_open` turning false by toggle, the last step being the mission's box, and the step limit `8 * 6**2 = 288` [code: UnlockPickupEnv.__init__, minigrid_env.py:step].

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
