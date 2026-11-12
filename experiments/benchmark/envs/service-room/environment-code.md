# Service Room: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Source: `app/src/arm_fm/service_room.py`, a MiniGrid environment written for this project on the Farama base <https://github.com/Farama-Foundation/Minigrid>. Importing `src.arm_fm.environments` registers it.
- Gymnasium ID: `MiniGrid-ServiceRoom-v0`. Keyword arguments: `siren` (bool), `box` (bool), `require` (list from `siren_silent`, `holding_box`), `max_steps` (int, default 200). All defaults give the plain room: no siren, no box, nothing required.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `reset(seed=s)` seeds only the event schedule. Without a seed it draws one from the environment's own random stream. Either way `reset` returns the seed it used as `info["event_seed"]`, beside `info["events"]`. Trace records store it as `reset_seed`, so an unseeded episode replays with `reset(seed=info["event_seed"])`.
- `[code: file:function]` is `service_room.py` unless a MiniGrid path is given. `[run: script]` is `experiments/benchmark/scripts/check_service_room.py` on the real environment, event seeds 1 to 50 over four setups (siren only, box only, both, neither).

## Truth conditions in code

All five read the state after the step. `events_this_step` is reset at the start of every step and filled by the action and the due events.

| id | expression |
|---|---|
| `siren_ringing` | `env.siren_ringing` |
| `switch_toggled` | `"toggle" in env.events_this_step` |
| `holding_box` | `env.carrying is not None and env.carrying.type == "box"` |
| `box_fell` | `"fall" in env.events_this_step` |
| `at_exit` | `env.grid.get(*env.agent_pos) is not None and env.grid.get(*env.agent_pos).type == "goal"` |

## Evidence

Layout, start, box, switch and exit cells [code: `_gen_grid`, constants `START`, `BOX_POS`, `SWITCH_POS`, `EXIT_POS`]. Exit at least 6 moves from the start [run: shortest scripted path in the plain room, 10 forward moves, pinned to exactly 10 so a layout change shows up].

- Environment, colours and positions: exit green [code: MiniGrid `Goal`], box purple [code: `BOX_COLOR`], switch blue and red while ringing [code: `SILENT_COLOR`, `RINGING_COLOR`, `_set_siren`]. Start in the top-left floor corner facing right, exit in the bottom-right floor corner, box in the upper part, switch in the left wall low down [code: `START`, `START_DIR`, `EXIT_POS`, `BOX_POS`, `SWITCH_POS`]. A toggle acts on the cell in front of the agent [code: MiniGrid `minigrid_env.py:step`, `toggle` branch].
- Environment, the seven actions and `done` doing nothing [code: MiniGrid `core/actions.py:Actions` has seven members; `minigrid_env.py:step`, the `done` branch is `pass`].
- Environment, schedule: all draws are made at reset from a generator seeded with the reset seed [code: `reset`, `_plan_events`]. Same seed twice gives the same actions and labels [run: 200 of 200 episodes].
- Environment, siren starts 1 to 4, second start 8 to 30 later with probability 0.5 [code: `_plan_events`]. Box falls 2 to 6 steps after the first pickup, second fall with probability 0.5 after the second pickup [code: `_plan_events`, `_schedule_fall`].
- Environment, no siren means `siren_ringing` is never true [code: `_plan_events` plans no ring without `siren`, `_ring` is the only place that turns the siren on, and `_gen_grid` places no switch without `siren`].
- Environment, the siren and the box are independent, including on the same step [code: `_fire_due_events` fires the ring and then every due fall; `_ring` touches only the siren state and `_fall` only the hands and the box, and neither reads the other's].
- Events do fire [run: 50 seeds per setup; siren only 60 rings fired of 74 planned, 1 skipped; box only 59 falls of 77 planned, 0 skipped; both 67 rings of 74 (3 skipped) and 61 falls of 77]. A planned event that neither fired nor was skipped did not come up before the episode ended: a ring or a fall was due on or after the last step, or a fall was never scheduled because the pickup that starts it never happened (the first fall needs a first pickup; the second fall is counted as planned at reset but scheduled only at the second pickup).
- Environment, event seed in the reset info: `info["event_seed"]` is the seed used, also when `seed` is given [code: `reset`]. An unseeded reset gives an integer, and `reset(seed=that)` replays the same actions and events [run: 5 of 5 unseeded episodes on the setup with both].
- Objective, reward at the exit [code: `_reward`, MiniGrid `MiniGridEnv._reward`]. The scripted policy exits with reward above 0 in 200 of 200 episodes. Reward 0 when a required condition fails [run: ignoring the siren, 50 of 50 episodes on siren only and on both end at the exit with reward 0; ignoring the fall, a fall fired in 50 of 50 episodes on box only and on both, each with reward 0].
- Objective, no ring or fall on the last step [code: `step`, `_fire_due_events` runs only when neither `terminated` nor `truncated`]. The last action still applies, so a toggle on the step at the step limit still gives `switch_toggled` [code: `step` runs the action before that test; `press_switch` records the toggle].
- `switch_toggled` on every toggle, also when silent [code: `Switch.toggle`, `press_switch`].
- Constraints, `box_fell` with `holding_box` [code: `_fall` sets `carrying` to None; run: every fall checked, hands empty and the box on a cell next to the agent].
- Constraints, `box_fell` with `at_exit`: no fall on the last step [code: `step`]. `switch_toggled` with `at_exit`: the exit is reached only by moving forward, and a toggle does not move the agent [code: MiniGrid `minigrid_env.py:step`].
- Can and cannot: walls, the switch panel and the box block movement [code: `Switch` is a `Wall`; MiniGrid `WorldObj.can_overlap`]. Only the box is pickable [code: `Switch.can_pickup` is False, `Goal` and walls inherit False]. Toggling the box does nothing [code: `ClosedBox.toggle`; MiniGrid's own `Box.toggle` would remove the box].
- Siren stops only on a toggle; a second start while ringing is skipped and counted [code: `_ring`, `press_switch`].
- Fall needs the box in hands, lands front, right, back, left, else skipped and counted [code: `_fall`, `_landing_cell`].
- Fall on the due step after a re-pickup: a box picked up, dropped and picked up again on the due step falls on that step, because the action applies before the events [run: pick-up probe, fall on the due step; code: `step`].
- Fall dodge: a box dropped and kept down past the due step does not fall; the fall is skipped, counted, and does not come back [code: `_fall` skips when `carrying` is `None`; run: pick-up probe, skipped 1, fired 0]. The n-th pickup schedules the n-th fall, after a fall or after a drop [code: `_schedule_fall`].
- Drop and pickup: drop works onto an empty cell in front with the box in the hands; pickup needs empty hands and a pickable object in front [code: MiniGrid `minigrid_env.py:step`, `drop` branch needs `not fwd_cell and self.carrying`, `pickup` branch needs `fwd_cell.can_pickup()` and `self.carrying is None`].
- Example trace: seed 1, setup with siren and box, both required, scripted policy with privileged grid access [run: `run_episode(CONFIGS["both"], 1)` in `check_service_room.py` plays `scripted_policy` and returns each step's action, labels and events; `summary.json` keeps no per-step lists]. Variant: the same call with seed 2.

## Labeling API

- `env.siren_ringing`: `True` while the siren is ringing, `False` otherwise. Siren state comes from it.
- `env.events_this_step`: list of strings for the step that just ended, empty when nothing happened. It can hold `"ring"` (the siren started), `"toggle"` (the agent toggled the switch) and `"fall"` (the box left the agent's hands). Event propositions come from it.
- `env.event_counts`: dict with the kinds `"ring"` and `"fall"`; each holds the integers `"planned"` (drawn at reset; the second fall counts here but is scheduled only at the second pickup), `"fired"` and `"skipped"` (both so far in the episode).
- `env.carrying`: the carried object, or `None`; it exposes `type` and `color`. The box has `type == "box"`. Carry state comes from it.
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- Object attributes: `type` (`wall`, `box`, `goal`) and `color`. The exit has `type == "goal"`.
- `env.width`, `env.height`: grid size.

Object classes cannot be imported. Guard empty cells with `cell is not None` before reading an attribute.
