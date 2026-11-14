# Service Room, carrying start: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them. It is the `carry=True` option of the service room in `../service-room/`; the rest of that folder's notes (layout, siren, drop and pickup rules) apply, except that drop does nothing before the first fall and every fall turns the agent (both below).

## Source and runtime

- Source: `app/src/arm_fm/service_room.py`, the same environment as `../service-room/environment-code.md`. Importing `src.arm_fm.environments` registers it.
- Gymnasium ID: `MiniGrid-ServiceRoom-v0`, with the keyword `carry=True` and `box=True` (`carry` without `box` raises `ValueError`). Other keywords: `siren`, `require`, `max_steps`, as in `../service-room/`. `carry` defaults to `False`, which is the plain service room.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `[run: check_service_room_carry.py]` is `experiments/benchmark/scripts/check_service_room_carry.py` on the real environment, reset seeds 1 to 50, over two setups (box only, siren and box).

## Truth conditions in code

All five read the state after the step, as in `../service-room/environment-code.md`.

| id | expression |
|---|---|
| `siren_ringing` | `env.siren_ringing` |
| `switch_toggled` | `"toggle" in env.events_this_step` |
| `holding_box` | `env.carrying is not None and env.carrying.type == "box"` |
| `box_fell` | `"fall" in env.events_this_step` |
| `at_exit` | `env.grid.get(*env.agent_pos) is not None and env.grid.get(*env.agent_pos).type == "goal"` |

## Evidence

- Environment, the agent starts holding the box and no box lies on the floor [code: `reset` puts a `ClosedBox` in `carrying` after MiniGrid's reset, `_gen_grid` places the floor box only without `carry`; run: check_service_room_carry.py, start check, 50 of 50 episodes on each setup]. `holding_box` is true at the first step [code: `step` does not touch `carrying` on a non-pickup action].
- Environment, the first fall comes 2 to 8 steps after the start, whatever the agent does [code: `_plan_events` draws `carry_fall` from `CARRY_FALL_FIRST` to `CARRY_FALL_LAST` and, with `carry`, uses it as the first fall delay; `reset` calls `_schedule_fall` at step 0, the start counting as the first pickup; run: check_service_room_carry.py, do-nothing check, an agent that only plays `done` sees the first fall at step 2 to 8 in 50 of 50 episodes on each setup].
- Environment, the box cannot be put down before the first fall: `drop` becomes `done` while carrying and no fall has fired or been skipped [code: `step`, `_first_fall_pending`; run: check_service_room_carry.py, drop check, an agent that plays `drop` on every step holds the box until the first fall in 50 of 50 episodes on each setup].
- Environment, the fall turns the agent to face the landing cell [code: `_fall` sets `agent_dir` to the direction of the landing cell when `carry`; run: check_service_room_carry.py, pickup check, an idle agent that plays `pickup` on the step after each fall holds the box again after every fall (1 or 2 falls per episode) in 50 of 50 episodes on each setup, also after turning to face the wall at step 1].
- Environment, same seed, same fall [run: check_service_room_carry.py, replay check, 50 of 50 per setup].
- Environment, the second fall: 2 to 6 steps after the next pickup, in half of the episodes [code: `_schedule_fall` takes the second delay at the second pickup; the first one was scheduled by the start]. The ring steps and the second fall delay are the draws of the same seed without `carry` [code: the `carry_fall` draw comes last in `_plan_events`; run: check_service_room_carry.py, schedule check, 50 of 50 per setup].
- Objective, the scripted policy still exits with reward above 0, waiting in place for each fall and picking the box up [run: check_service_room_carry.py, exit-reward check, 50 of 50 per setup; code: `scripted_policy`, `_fall_pending`].
- Everything else (switch, siren, where the box lands, drop after the first fall, pickup, no ring or fall on the last step, constraints) is the code of the plain service room [code: `service_room.py`, not touched by `carry`; evidence in `../service-room/environment-code.md`].
- Example trace: box only, seed 2, scripted policy [run: `run_episode` of `check_service_room.py` with `carry=True` replays it: 23 steps, reward 0.8965; the fall delays are 4 and 6].

## Labeling API

- `env.siren_ringing`: `True` while the siren is ringing, `False` otherwise. Siren state comes from it.
- `env.events_this_step`: list of strings for the step that just ended, empty when nothing happened. It can hold `"ring"` (the siren started), `"toggle"` (the agent toggled the switch) and `"fall"` (the box left the agent's hands). Event propositions come from it.
- `env.event_counts`: dict with the kinds `"ring"` and `"fall"`; each holds the integers `"planned"`, `"fired"` and `"skipped"` (the last two so far in the episode).
- `env.carrying`: the carried object, or `None`; it exposes `type` and `color`. The box has `type == "box"`. Carry state comes from it.
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- Object attributes: `type` (`wall`, `box`, `goal`) and `color`. The exit has `type == "goal"`.
- `env.width`, `env.height`: grid size.

Object classes cannot be imported. Guard empty cells with `cell is not None` before reading an attribute.
