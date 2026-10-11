# BabyAI ChosenMission

## Source and runtime

- Gymnasium ID: `BabyAI-ChosenMission-v0`, a level of this repository
  (`app/src/arm_fm/custom_envs/babyai_mission.py`) built on MiniGrid's BabyAI `RoomGridLevel`.
  It is a reconstructed level of our own, not a published ARM-FM or BabyAI level.
- The mission is chosen with `env_kwargs: {mission: "<mission text>"}`. The text is kept
  unchanged as `env.mission`.

## Environment

Two 8x8 rooms side by side are joined by one green door in the wall they share. The door starts
closed and unlocked. The level holds exactly four objects: a yellow ball, a red key, a blue box
and a purple box. Their positions and the agent's start room and position are random in every
episode, and a layout that already satisfies the mission is never used. The agent can turn
left or right, move forward, pick up, drop, toggle and `done`. It carries at most one object.
A drop puts the carried object on the cell in front of the agent when that cell is empty;
toggling a door opens or closes it, and toggling a box removes it. An episode lasts at most 400 steps.

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
