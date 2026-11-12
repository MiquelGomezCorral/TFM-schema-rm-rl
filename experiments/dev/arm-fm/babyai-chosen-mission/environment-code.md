# BabyAI ChosenMission: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Gymnasium ID `BabyAI-ChosenMission-v0`, a level of this repository (`app/src/arm_fm/custom_envs/babyai_mission.py`) built on MiniGrid's BabyAI `RoomGridLevel`. It is a reconstructed level of our own, not a published ARM-FM or BabyAI level.
- The mission is chosen with `env_kwargs: {mission: "<mission text>"}`. The text is kept unchanged as `env.mission`.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`. Level code last changed in commit `5beea9b`.
- `[code: file:function]` is MiniGrid 3.1.0 source or this level's code. `[run]` is a scripted run or check on the real environment with `chosen_mission.py`, `layout_checks.py`, `mechanics_check.py`, `chosen_events_repeat.py`. `unknown` means no source says.

## Truth conditions in code

`prev = env.episode_memory["previous_valuation"]`; it is empty at the first step, so an event is false there. Objects and cells are `env.grid.get(x, y)`; scans guard `None`. An object found on the grid is not carried. Objects sit inside the border wall, so neighbor reads stay in range.

- `green_door_open`: `any(c is not None and c.type == "door" and c.color == "green" and c.is_open for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)])`
- `carrying_yellow_ball`: `env.carrying is not None and env.carrying.type == "ball" and env.carrying.color == "yellow"`. `carrying_blue_box` and `carrying_purple_box` are the same with `box` and `blue` or `purple`.
- `yellow_ball_placed_next_to_red_key`: `prev["carrying_yellow_ball"] and any(b is not None and b.type == "ball" and b.color == "yellow" and any(k is not None and k.type == "key" and k.color == "red" for k in [env.grid.get(x+1, y), env.grid.get(x-1, y), env.grid.get(x, y+1), env.grid.get(x, y-1)]) for x in range(env.width) for y in range(env.height) for b in [env.grid.get(x, y)])`
- `purple_box_placed_in_corner`: `prev["carrying_purple_box"] and any(b is not None and b.type == "box" and b.color == "purple" and any(n is not None and n.type == "wall" for n in [env.grid.get(x-1, y), env.grid.get(x+1, y)]) and any(n is not None and n.type == "wall" for n in [env.grid.get(x, y-1), env.grid.get(x, y+1)]) for x in range(env.width) for y in range(env.height) for b in [env.grid.get(x, y)])`

These expressions are derived from the definitions in `environment.md`; they were not run as labeling code.

## Evidence

Source and layout
- Environment, grid 15 wide and 8 high, rooms 8x8 counting the shared wall: [run: `layout_checks.py`, 300 seeds per mission].
- Environment, door closed and never locked, `toggle` opens it without a key: [code: babyai_mission.py:ChosenMission.gen_mission].
- Environment, every object reachable: [code: `check_objs_reachable`].
- Environment, seven actions, `done` does nothing: [code: minigrid_env.py:step].
- Environment, positions random, and layouts that already satisfy mission 1 or 3 sampled again: [code: babyai_mission.py:_starts_solved].
- Environment, the 400-step limit and the drop, toggle and carry rules: no tag in the old file; the drop and carry rules are [code: minigrid_env.py:step, Box.toggle].

Objective and episode boundary
- Missions 1 and 2 terminate natively, mission 1 on the event step itself: [run: `chosen_mission.py`].
- Mission 3 has no native judge, the stock environment never terminates on it: [run: `mechanics_check.py`, 20 more steps].
- Mission 2, the blue box starts in the other room: [code: babyai_mission.py:_place_objects; run: `layout_checks.py`, 300/300].

Constraints
- The three `carrying_*` pairs never hold together: [code: minigrid_env.py:step; run: `mechanics_check.py`, 0 of 600 random episodes].
- Each event cannot come before its `carrying_*`: follows from the event definition in `environment.md`, no run.
- Each event and its own `carrying_*` never hold together: [code: minigrid_env.py:step].
- `yellow_ball_placed_next_to_red_key` and `purple_box_placed_in_corner` never hold together: [code: minigrid_env.py:step; run: `chosen_events_repeat.py`, 0 of 200 episodes of mission 3; `mechanics_check.py`, 0 of 600].
- `carrying_blue_box` cannot come before `green_door_open` (mission 2): [code: babyai_mission.py:_place_objects; run: `layout_checks.py`, 300/300].

What the agent can and cannot do
- Can and cannot list (turn, forward, pickup, drop, toggle, closed door, two objects, occupied cell, event needs a drop): [code: minigrid_env.py:step, Box.toggle].
- An event is true only on a `drop` step, never twice in a row, needs `carrying_*` the step before: [code: minigrid_env.py:step].
- No event at the first step: needs the previous valuation; layouts that already satisfy missions 1 and 3 are sampled again: [code: babyai_mission.py:_starts_solved].
- Events can repeat: [code: minigrid_env.py:step]. Observed: a repeat of `purple_box_placed_in_corner` in 1 of 200 random episodes of mission 3, none for `yellow_ball_placed_next_to_red_key` (11 episodes had one event, none two): [run: `chosen_events_repeat.py`, log `chosen_events_repeat.log`].
- No order with `green_door_open` in missions 1 and 3: `carrying_blue_box` came before `green_door_open` in 13 of 55 random episodes of mission 1 that reached it: [code: `_place_objects`; run: `chosen_mission_m1_explore_stats.json`].
- `toggle` on a box removes it for good: [code: world_object.py:Box.toggle; run: `mechanics_check.py`].
- `green_door_open` can turn false again: [code: Door.toggle].

Example trace
- Mission 3, `BabyAI-ChosenMission-v0`, seed 0, scripted solver: [run: `chosen_mission.py`, log `chosen_mission_m3_trace_seed0.jsonl`].
- Mission 2, same seed: [run: log `chosen_mission_m2_trace_seed0.jsonl`].

## Labeling API

- `env.mission`: the mission string, for example `put the yellow ball next to the red key`.
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid
  coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- Object attributes: `type` (`ball`, `key`, `box`, `door` or `wall`), `color`, and `is_open`
  and `is_locked` on doors.
- `env.carrying`: the carried object, or `None`; it exposes `type` and `color`.
- `env.width`, `env.height`: grid size.
