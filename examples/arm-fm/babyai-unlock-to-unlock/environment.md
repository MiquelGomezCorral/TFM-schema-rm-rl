# BabyAI UnlockToUnlock

## Environment

Three rooms form a chain. The target ball is in the goal-side room. The door into that room
requires one colored key, but that key is itself behind another locked door with a different
matching key. The two colors are sampled by the environment, so task semantics must use
prerequisite/target roles rather than fixed color names.

Layout: three 6x6 rooms in a row (grid 16 wide, 6 high). The agent starts in the middle room.
The ball lies in the left room. Door A, between left and middle, is locked and has its key A in
the right room. Door B, between middle and right, is locked and has its key B in the middle
room, with the agent. The two colors differ. The mission is exactly `pick up the ball`. Names in
the propositions: the prerequisite door is door B and its key is key B; the target door is door
A and its key is key A.

Actions are seven discrete keys: `left`, `right`, `forward`, `pickup`, `drop`, `toggle`, `done`;
`done` does nothing.

## Objective and episode boundary

The mission is to pick up the ball by resolving both key-door dependencies. The environment
terminates when the ball is picked up and truncates at its step limit of 1080 steps.

## Proposition semantics

"Prerequisite" identifies the first key and door that must be handled to gain access to the key
for the target-side door. "Target-side" identifies the second dependency.

| id | kind | true when |
|---|---|---|
| `has_prerequisite_key` | condition | the agent carries a key of door B's color |
| `prerequisite_door_open` | condition | door B is open; false again if toggled shut |
| `has_target_door_key` | condition | the agent carries a key of door A's color |
| `target_door_open` | condition | door A is open; false again if toggled shut |
| `target_ball_picked_up` | condition, final step only | the agent carries the ball |
| `required_key_lost` | event, reading | key B was carried at the previous step, is not carried now, and door B is not open now; or the same for key A and door A; false on every other step |

Reading of `required_key_lost`: the description does not say whether it is an event or lingers.
This file reads it as an event, per key; a
lingering "true until picked up again" form would need to know which key was lost.

## Constraints

- `prerequisite_door_open` cannot become true before `has_prerequisite_key`: only `toggle` with the matching key unlocks a door.
- `target_door_open` cannot become true before `has_target_door_key`: same rule for door A.
- `has_target_door_key` cannot become true before `prerequisite_door_open`: key A lies in the right room, behind door B.
- `target_ball_picked_up` cannot become true before `target_door_open`: the ball lies in the left room, behind door A.
- `has_prerequisite_key` and `has_target_door_key` never hold together: the agent holds one object. Key B must be dropped before key A is picked up.
- `has_prerequisite_key` and `target_ball_picked_up` never hold together: same rule.
- `has_target_door_key` and `target_ball_picked_up` never hold together: key A must be dropped before the ball is picked up.
- `required_key_lost` and `has_prerequisite_key` never hold together: the step a key leaves the hands is a `drop`, and the hands are empty after it.
- `required_key_lost` and `has_target_door_key` never hold together: same reason.
- `required_key_lost` and `target_ball_picked_up` never hold together: same reason.

## What the agent can and cannot do

- Can: turn; `forward` onto an empty cell or an open door; `pickup` a key or the ball with empty hands; `drop` onto an empty cell in front; `toggle` the door in front.
- Cannot: open a door without its own key in hand; carry two objects; reach key A before door B is open or the ball before door A is open; drop onto an occupied cell.
- A dropped key can block a doorway. It can be picked up again, so the task stays solvable.
- Dropping a key after its own door is open does not fire `required_key_lost`: key B must go before key A is picked up, key A before the ball, and both can be done after the door is open.
- Dropping key B while door B is closed fires `required_key_lost`. The key can be picked up again.
- Doors can be toggled shut again and are never relocked.

## Example trace

A real episode. 39 steps, reward 0.968.

1. 4 turns and moves, no proposition changes
2. `pickup` (step 5): `has_prerequisite_key` true
3. 5 turns and moves, no proposition changes
4. `toggle` (step 11): `prerequisite_door_open` true
5. 1 turn or move, no proposition changes
6. `drop` (step 13): `has_prerequisite_key` false
7. 4 turns and moves, no proposition changes
8. `pickup` (step 18): `has_target_door_key` true
9. 9 turns and moves, no proposition changes
10. `toggle` (step 28): `target_door_open` true
11. 1 turn or move, no proposition changes
12. `drop` (step 30): `has_target_door_key` false
13. 8 turns and moves, no proposition changes
14. `pickup` (step 39): `target_ball_picked_up` true [episode terminated]

## Propositions
- `has_prerequisite_key`: The agent is carrying the key for the prerequisite door.
- `prerequisite_door_open`: The prerequisite door is currently open.
- `has_target_door_key`: The agent is carrying the key for the door guarding the target ball.
- `target_door_open`: The door guarding the target ball is currently open.
- `target_ball_picked_up`: The agent is currently carrying the mission's ball.
- `required_key_lost`: A currently required key was acquired and then lost before its door was opened.

## Example tasks

- Eventually pick up the target ball.
- Open the prerequisite door before acquiring the target-door key.
- Open the target-side door before picking up the ball.
