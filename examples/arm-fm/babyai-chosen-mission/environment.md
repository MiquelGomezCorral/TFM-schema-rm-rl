# BabyAI ChosenMission

## Environment

Two 8x8 rooms side by side, counting the wall they share, are joined by one green door in that
wall. The grid is 15 cells wide and 8 high. The door starts closed and is never locked, so
`toggle` opens it without a key. The level holds exactly four objects: a yellow ball, a red key,
a blue box and a purple box. Their positions and the agent's start room and position are random
in every episode, every object is reachable in the sampled layout, and a layout that already
satisfies mission 1 or 3 is never used. The mission text is chosen per run.

The agent has seven actions: turn left, turn right, move forward, `pickup`, `drop`, `toggle` and
`done`; `done` does nothing. It carries at most one object. A drop puts the carried object on the
cell in front of the agent when that cell is empty. Toggling a door opens or closes it; toggling
a box removes it. An episode lasts at most 400 steps.

## Objective and episode boundary

The three missions are listed under "Example tasks".

- "put the yellow ball next to the red key" and "open the green door, then pick up the blue
  box" are judged by the environment, which terminates on success and truncates at the step
  limit. Mission 1 terminates on the very step of the event. In mission 2 the blue box starts in
  the room the agent does not start in, so the door must be opened first.
- "move the purple box to a corner, then put the yellow ball next to the red key" has no judge:
  the environment never terminates by itself and only truncates at the step limit. The Reward
  Machine's acceptance ends the episode.

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
| `green_door_open` | condition | the green door is open; false again if toggled shut |
| `carrying_yellow_ball`, `carrying_blue_box`, `carrying_purple_box` | condition | the agent carries that object |
| `yellow_ball_placed_next_to_red_key` | event | as defined above: carried at the previous step, not carried now, on the grid orthogonally next to the red key |
| `purple_box_placed_in_corner` | event | as defined above: carried at the previous step, not carried now, on the grid in a corner cell |

## Constraints

- `carrying_yellow_ball` and `carrying_blue_box` never hold together: the agent holds one object.
- `carrying_yellow_ball` and `carrying_purple_box` never hold together: same reason.
- `carrying_blue_box` and `carrying_purple_box` never hold together: same reason.
- `yellow_ball_placed_next_to_red_key` cannot become true before `carrying_yellow_ball`: the event needs the ball carried at the previous step.
- `purple_box_placed_in_corner` cannot become true before `carrying_purple_box`: the event needs the box carried at the previous step.
- `yellow_ball_placed_next_to_red_key` and `carrying_yellow_ball` never hold together: the event is true on the step the ball leaves the hand, and an object leaves the hand only by `drop`.
- `purple_box_placed_in_corner` and `carrying_purple_box` never hold together: same reason.
- `yellow_ball_placed_next_to_red_key` and `purple_box_placed_in_corner` never hold together: one `drop` moves one object.
- `carrying_blue_box` cannot become true before `green_door_open`: mission 2 only, because the blue box starts in the room the agent does not start in.

## What the agent can and cannot do

- Can: turn; `forward` onto an empty cell or an open door; `pickup` the ball, key or a box with empty hands; `drop` onto an empty cell in front; `toggle` the door (open or shut) or a box (destroys it).
- Cannot: walk through a closed door; carry two objects; drop onto an occupied cell, a door cell included; make an event true without dropping the object.
- An event is true only on a `drop` step, never on two steps in a row, and needs the matching `carrying_*` true on the step before.
- No event is true at the first step: an event needs the previous valuation, and the first step has none.
- Events can repeat: pick the object up again and drop it again.
- In missions 1 and 3 any object may start in either room, so no order with `green_door_open` is forced: `carrying_blue_box` can come before `green_door_open`.
- `toggle` on a box removes it for good (the box holds nothing). After that its `carrying_*` and event can never become true, and a mission that needs that box can no longer succeed.
- `green_door_open` can turn false again (toggle).

## Example trace

Mission 3, a real episode. 34 steps. The yellow ball started in the other room, so the door is opened on the way. The environment did not terminate: the Reward Machine would end the episode at step 34.

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

Mission 2, another real episode: 10 turns and moves, `toggle` (step 11): `green_door_open` true, 4 turns and moves, `pickup` (step 16): `carrying_blue_box` true, the environment terminates (reward 0.964).

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
