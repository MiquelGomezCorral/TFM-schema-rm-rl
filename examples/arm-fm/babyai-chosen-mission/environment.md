# BabyAI ChosenMission

## Source and runtime

- Gymnasium ID: `BabyAI-ChosenMission-v0`, a level of this repository
  (`app/src/arm_fm/custom_envs/babyai_mission.py`) built on MiniGrid's BabyAI `RoomGridLevel`.
  It is a reconstructed level of our own, not a published ARM-FM or BabyAI level.
- The mission is chosen with `env_kwargs: {mission: "<mission text>"}`. The text is kept
  unchanged as `env.mission`.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`. Level code last changed in commit `5beea9b`.
- Evidence tags: `[code: file:function]` is MiniGrid 3.1.0 source or this level's code; `[run]` is a scripted run or check on the real environment with `chosen_mission.py`, `layout_checks.py`, `mechanics_check.py`; `unknown` means no source says.

## Environment

Two 8x8 rooms side by side are joined by one green door in the wall they share. The door starts
closed and unlocked. The level holds exactly four objects: a yellow ball, a red key, a blue box
and a purple box. Their positions and the agent's start room and position are random in every
episode, and a layout that already satisfies the mission is never used. The agent can turn
left or right, move forward, pick up, drop, toggle and `done`. It carries at most one object.
A drop puts the carried object on the cell in front of the agent when that cell is empty;
toggling a door opens or closes it, and toggling a box removes it. An episode lasts at most 400 steps.

Grid [run: `layout_checks.py`, 300 seeds per mission]: 15 wide and 8 high; the rooms are 8x8 counting the shared wall. The door is closed and never locked, so `toggle` opens it without a key [code: babyai_mission.py:ChosenMission.gen_mission]. Every object is reachable in the sampled layout [code: `check_objs_reachable`]. The agent has the seven MiniGrid actions; `done` does nothing [code: minigrid_env.py:step].

## Objective and episode boundary

The three missions are listed under "Example tasks".

- "put the yellow ball next to the red key" and "open the green door, then pick up the blue
  box" are judged by BabyAI. The environment terminates on success and truncates at the step
  limit. In the second mission the blue box starts in the room the agent does not start in, so
  the door must be opened first.
- "move the purple box to a corner, then put the yellow ball next to the red key" has no BabyAI
  judge: the environment never terminates by itself and only truncates at the step limit. The
  Reward Machine's acceptance ends the episode.

## Proposition semantics

All propositions are computed from the live environment and the previous valuation, once per
step. `green_door_open` and the `carrying_*` propositions are persistent conditions. The two
`*_placed_*` propositions are one-step events: each is true only on the step where the agent
dropped the named object, and false on every other step, including the first.

Two objects or cells are next to each other when they are horizontally or vertically adjacent;
diagonal cells are not. A corner is a cell touching two walls of a room: a wall cell beside it
horizontally and a wall cell above or below it. A door is not a wall. A carried object is not
on the grid.

An event holds when the previous valuation has the matching `carrying_*` proposition true,
the object is no longer carried now, and the object lies on the grid in the required place.
Moving any other object, or leaving the object where it already was, does not make it true.

| id | kind | true when |
|---|---|---|
| `green_door_open` | condition | the green door's `is_open` is true; false again if toggled shut |
| `carrying_yellow_ball`, `carrying_blue_box`, `carrying_purple_box` | condition | `env.carrying` is that object |
| `yellow_ball_placed_next_to_red_key` | event | as defined above: carried at the previous step, not carried now, on the grid orthogonally next to the red key |
| `purple_box_placed_in_corner` | event | as defined above: carried at the previous step, not carried now, on the grid in a corner cell |

## Constraints

- `carrying_yellow_ball` and `carrying_blue_box` never hold together: the agent holds one object [code: minigrid_env.py:step; run: `mechanics_check.py`, 0 of 600 random episodes].
- `carrying_yellow_ball` and `carrying_purple_box` never hold together: same reason [code: minigrid_env.py:step; run: same].
- `carrying_blue_box` and `carrying_purple_box` never hold together: same reason [code: minigrid_env.py:step; run: same].
- `yellow_ball_placed_next_to_red_key` cannot become true before `carrying_yellow_ball`: the event needs the ball carried at the previous step [definition above].
- `purple_box_placed_in_corner` cannot become true before `carrying_purple_box`: the event needs the box carried at the previous step [definition above].
- `yellow_ball_placed_next_to_red_key` and `carrying_yellow_ball` never hold together: the event is true on the step the ball leaves the hand, and an object leaves the hand only by `drop` [code: minigrid_env.py:step].
- `purple_box_placed_in_corner` and `carrying_purple_box` never hold together: same reason [code: minigrid_env.py:step].
- `yellow_ball_placed_next_to_red_key` and `purple_box_placed_in_corner` never hold together: one `drop` moves one object [code: minigrid_env.py:step; run: `chosen_events_repeat.py`, 0 of 200 episodes of mission 3; `mechanics_check.py`, 0 of 600].
- `carrying_blue_box` cannot become true before `green_door_open`: mission 2 only, because the blue box starts in the room the agent does not start in [code: babyai_mission.py:_place_objects; run: `layout_checks.py`, 300/300].

## What the agent can and cannot do

- Can: turn; `forward` onto an empty cell or an open door; `pickup` the ball, key or a box with empty hands; `drop` onto an empty cell in front; `toggle` the door (open or shut) or a box (destroys it) [code: minigrid_env.py:step, Box.toggle].
- Cannot: walk through a closed door; carry two objects; drop onto an occupied cell, a door cell included; make an event true without dropping the object [code: minigrid_env.py:step; the event definition needs a drop].
- Mission 3 has no native judge: the stock environment never terminates on it [run: `mechanics_check.py`, 20 more steps]. Missions 1 and 2 terminate natively; mission 1 on the event step itself [run: `chosen_mission.py`].
- An event is true only on a `drop` step, never on two steps in a row, and needs the matching `carrying_*` true on the step before [code: minigrid_env.py:step].
- No event is true at the first step: an event needs the previous valuation, and the first step has none. Layouts that already satisfy missions 1 and 3 are also sampled again [code: babyai_mission.py:_starts_solved].
- Events can repeat: pick the object up again and drop it again [code: minigrid_env.py:step]. A repeat was seen for `purple_box_placed_in_corner` in 1 of 200 random episodes of mission 3 and not for `yellow_ball_placed_next_to_red_key` (11 episodes had one event, none two) [run: `chosen_events_repeat.py`, log `chosen_events_repeat.log`].
- In missions 1 and 3 any object may start in either room, so no order with `green_door_open` is forced: `carrying_blue_box` came before `green_door_open` in 13 of 55 random episodes of mission 1 that reached it [code: `_place_objects`; run: `chosen_mission_m1_explore_stats.json`].
- `toggle` on a box removes it for good (the box holds nothing) [code: world_object.py:Box.toggle; run: `mechanics_check.py`]. After that its `carrying_*` and event can never become true, and a mission that needs that box can no longer succeed.
- `green_door_open` can turn false again (toggle) [code: Door.toggle].

## Example trace

Mission 3, `BabyAI-ChosenMission-v0`, seed 0, scripted solver [run: `chosen_mission.py`, log `chosen_mission_m3_trace_seed0.jsonl`]. 34 steps. The yellow ball started in the other room, so the door is opened on the way. The environment did not terminate: the Reward Machine would end the episode at step 34.

1. 4 turns and moves, no proposition changes
2. `pickup` (step 5): `carrying_purple_box` true
3. 4 turns and moves, no proposition changes
4. `drop` (step 10): `carrying_purple_box` false, `purple_box_placed_in_corner` true
5. `left` (step 11): `purple_box_placed_in_corner` false
6. 8 turns and moves, no proposition changes
7. `pickup` (step 20): `carrying_yellow_ball` true
8. 7 turns and moves, no proposition changes
9. `toggle` (step 28): `green_door_open` true
10. 5 turns and moves, no proposition changes
11. `drop` (step 34): `carrying_yellow_ball` false, `yellow_ball_placed_next_to_red_key` true

Mission 2, same seed [run: `chosen_mission_m2_trace_seed0.jsonl`]: 10 turns and moves, `toggle` (step 11): `green_door_open` true, 4 turns and moves, `pickup` (step 16): `carrying_blue_box` true, the environment terminates (reward 0.964).

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

## Propositions
- `green_door_open`: The green door is currently open.
- `carrying_yellow_ball`: The agent is currently carrying the yellow ball.
- `carrying_blue_box`: The agent is currently carrying the blue box.
- `carrying_purple_box`: The agent is currently carrying the purple box.
- `yellow_ball_placed_next_to_red_key`: Event: on this step the agent dropped the yellow ball, which was carried at the previous step and now lies next to the red key.
- `purple_box_placed_in_corner`: Event: on this step the agent dropped the purple box, which was carried at the previous step and now lies in a corner.

## Example tasks

- Put the yellow ball next to the red key.
- Open the green door, then pick up the blue box.
- Move the purple box to a corner, then put the yellow ball next to the red key.
