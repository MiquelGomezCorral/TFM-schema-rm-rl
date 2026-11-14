# MiniGrid UnlockPickup, key already held

## Environment

Two rooms are connected by a locked door. The target box is in the second room. The agent starts holding the key that matches the door, so it does not have to look for it. Object color and placement change between resets. The agent has seven actions: turn left, turn right, move forward, pick up, drop, toggle, and done. Done does nothing.

Layout: two 6x6 rooms side by side (an 11x6 grid) share one wall. Its one door is locked and has a random color. The agent starts in the left room already holding the key, which has the door's color, so `has_door_key` is true at the first step. There is no key on the floor. One box of random color lies in the right room. Nothing else is in the grid. The mission names the box: "pick up the <color> box".

## Objective and episode boundary

The mission is to unlock the door and pick up the designated box. The environment ends the episode when the correct box is picked up and cuts it at the step limit.

The step limit is 8 times 6 squared, 288 steps. Only picking up the mission's box ends the episode.

## Proposition semantics

The target is the box named by the current mission, not any box that may be present.

| id | kind | true when |
|---|---|---|
| `has_door_key` | condition | the agent carries a key whose color equals the door's color; true at the first step, because the agent starts holding it |
| `door_open` | condition | the door is open; false again if the door is toggled shut |
| `target_picked_up` | condition, last step only | the agent carries the box the mission names (the only box) |
| `key_lost` | event, reading | `has_door_key` was true at the previous step, is false now, and `door_open` is false now; false on every other step |

`key_lost` reading: the description does not say whether it is an event or lingers. This file reads it as an event. It differs from a lingering reading only after the key is dropped: the event is true for that one step, not until the key is picked up again.

## Constraints

- `door_open` cannot become true before `has_door_key`: only toggling with the matching key unlocks the door, and the agent starts holding it.
- `target_picked_up` cannot become true before `door_open`: the box room has no other entrance.
- `has_door_key` and `target_picked_up` never hold together: the agent holds one object, so pick up does nothing with the key in hand.
- `key_lost` and `has_door_key` never hold together: the event requires the key not carried.
- `key_lost` and `door_open` never hold together: the event requires the door not open.
- `key_lost` and `target_picked_up` never hold together: `key_lost` needs a drop step and `target_picked_up` a pick-up step.

## What the agent can and cannot do

- Can: turn; move forward onto an empty cell or an open door; pick up the key or the box with empty hands; drop onto an empty cell in front; toggle the door in front.
- Cannot: walk through a closed or locked door; unlock without the matching key in hand; pick up a second object; drop onto an occupied cell; relock a door.
- The first step always shows the key in hand: `drop` does nothing on the first step. From the second step on every action works as usual.
- The key can be dropped later, and picked up again with empty hands. Dropping it while the door is closed fires `key_lost`.
- After `door_open` the key must be dropped before the box can be picked up. That drop is not `key_lost`, because the door is already open.
- `target_picked_up` is the last step: only the mission's box ends the episode.
- `door_open` can turn false again (toggle) and is never relocked.

## Example trace

A real episode, mission "pick up the purple box": 10 steps, reward 0.969.

1. 1 move (step 1): `has_door_key` true, already true at the first step
2. 1 turn, no proposition changes
3. `toggle` (step 3): `door_open` true
4. 1 turn, no proposition changes
5. `drop` (step 5): `has_door_key` false
6. 4 turns and moves, no proposition changes
7. `pickup` (step 10): `target_picked_up` true [episode terminated]

The agent never picks up the key. The `drop` at step 5 frees the hands for the box; `key_lost` stays false because the door is open.

## Propositions
- `has_door_key`: The agent is currently carrying the key whose color matches the locked door.
- `door_open`: The locked door leading to the target room is currently open.
- `target_picked_up`: The agent is currently carrying the mission's designated box.
- `key_lost`: The agent previously acquired the matching key but is no longer carrying it before opening the door.

## Example tasks

- Eventually pick up the target box.
- Acquire the matching key before opening the door.
- Open the door before picking up the target box.
