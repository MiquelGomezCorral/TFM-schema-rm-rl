# MiniGrid BlockedUnlockPickup

## Environment

Two rooms are connected by a locked door. A ball initially blocks access to the door, a matching key is in the starting room, and the mission's target box is in the other room. The ball must be moved away, the key acquired, and the door unlocked before the target can be collected. Colors and positions vary between resets. The agent has seven actions: turn left, turn right, move forward, pick up, drop, toggle, and done. Done does nothing.

Layout: two 6x6 rooms, one locked door of random color in the shared wall. A ball of random color sits on the cell directly in front of the door on the start side. Before the door is first open, that cell is the only reachable cell the agent can toggle the door from. The key, in the door's color, lies in the start room and is reachable without moving the ball. One box of random color lies in the right room. The mission names the box: "pick up the <color> box".

## Objective and episode boundary

The mission is complete when the agent picks up the designated target box. The environment ends the episode on that pickup and cuts it at the step limit.

The step limit is 16 times 6 squared, 576 steps. Only picking up the mission's box ends the episode.

## Proposition semantics

The propositions denote observable task progress, independent of the raw action used to cause it.

| id | kind | true when |
|---|---|---|
| `blocker_moved` | condition, reading | the cell in front of the door holds no ball; a ball in the agent's hand counts as moved; false again if the ball is dropped back there |
| `has_door_key` | condition | the agent carries a key whose color equals the door's color |
| `door_open` | condition | the door is open; false again if toggled shut |
| `target_picked_up` | condition, last step only | the agent carries the box the mission names |
| `key_lost` | event, reading | `has_door_key` was true at the previous step, is false now, and `door_open` is false now; false on every other step |

Readings: the descriptions of `blocker_moved` and `key_lost` leave open how they behave over time.

- `blocker_moved` is a condition, not a latch: it is false again if the ball is dropped back on that cell.
- `key_lost` is an event. It differs from a lingering reading only after the key is dropped: the event is true for that one step, not until the key is picked up again.

## Constraints

- `door_open` cannot become true before `blocker_moved`: before the door is first open, the ball's cell is the only reachable cell the agent can toggle it from.
- `door_open` cannot become true before `has_door_key`: only toggling with the matching key unlocks the door.
- `target_picked_up` cannot become true before `door_open`: the box room has no other entrance.
- `has_door_key` and `target_picked_up` never hold together: the agent holds one object, so pick up does nothing with the key in hand.
- `key_lost` and `has_door_key` never hold together: the event requires the key not carried.
- `key_lost` and `door_open` never hold together: the event requires the door not open.
- `key_lost` and `target_picked_up` never hold together: `key_lost` needs a drop step and `target_picked_up` a pick-up step.

## What the agent can and cannot do

- Can: turn; move forward onto an empty cell or an open door; pick up the ball, key or box with empty hands; drop onto an empty cell in front; toggle the door in front.
- Cannot: push or walk through the ball; unlock without the matching key; carry two objects; drop onto an occupied cell; relock a door.
- Only pick up and drop move the ball: toggle and move forward leave it in place. `blocker_moved` turns true on the pick up of the ball. With the ball in hand, picking up the key does nothing, so the ball must be dropped before the key is picked up.
- The key may be picked up first. It must then be dropped to pick up the ball, and that drop fires `key_lost` while the door is closed.
- `blocker_moved` can turn false again when the ball is dropped back in front of the door.

## Example trace

A real episode, mission "pick up the purple box": 28 steps, reward 0.956.

1. 3 turns and moves, no proposition changes
2. `pickup` (step 4): `blocker_moved` true
3. 1 turn or move, no proposition changes
4. `drop` (step 6): no proposition changes
5. 5 turns and moves, no proposition changes
6. `pickup` (step 12): `has_door_key` true
7. 4 turns and moves, no proposition changes
8. `toggle` (step 17): `door_open` true
9. 1 turn or move, no proposition changes
10. `drop` (step 19): `has_door_key` false
11. 8 turns and moves, no proposition changes
12. `pickup` (step 28): `target_picked_up` true [episode terminated]

The `drop` at step 6 puts the ball down away from the door; it changes no proposition. The `drop` at step 19 frees the hands for the box; `key_lost` stays false because the door is open.

## Propositions
- `blocker_moved`: The blocking ball no longer prevents access to the locked door.
- `has_door_key`: The agent is currently carrying the key matching the locked door.
- `door_open`: The door leading to the target room is currently unlocked and open.
- `target_picked_up`: The agent is currently carrying the mission's designated box.
- `key_lost`: The matching key was acquired and then lost before the door was opened.

## Example tasks

- Eventually pick up the target box.
- Move the blocker before opening the door.
- Acquire the matching key before opening the door.
