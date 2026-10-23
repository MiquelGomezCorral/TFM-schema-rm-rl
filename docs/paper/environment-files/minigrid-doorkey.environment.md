# MiniGrid DoorKey

## Environment

The agent starts on one side of a wall. A locked yellow door separates it from the green goal, and a matching yellow key is accessible on the starting side. The agent has seven actions: turn left, turn right, move forward, pick up, drop, toggle, and done. Done does nothing. The layout and initial pose change between resets.

Layout: a square grid of N x N cells with an outer wall; N is 5, 6, 8 or 16 depending on the variant. A wall spans the full height at a random column and has one gap, the locked yellow door, at a random row. The agent starts left of the wall, the yellow key lies on the left side, and the goal sits in the bottom-right inner corner. Nothing else is in the grid. The mission text is always "use the key to open the door and then get to the goal".

## Objective and episode boundary

The task is complete when the agent reaches the goal after using the key to unlock and open the door. The environment ends the episode on reaching the goal and cuts it at the step limit. Its success reward is 1 minus 0.9 times the fraction of the step limit used.

The step limit is 10 times N squared (640 for N = 8). The step that moves the agent onto the goal ends the episode, so no step follows `at_goal`.

## Proposition semantics

These are state conditions evaluated at every time point.

| id | kind | true when |
|---|---|---|
| `has_key` | condition | the agent carries the yellow key |
| `door_open` | condition | the door is open; false again if the door is toggled shut |
| `at_goal` | condition, last step only | the agent stands on the goal cell |
| `key_lost` | event, reading | `has_key` was true at the previous step, is false now, and `door_open` is false now; false on every other step |

`key_lost` reading: the description does not say whether it is an event or lingers. This file reads it as an event. Both readings agree while the agent holds the key. They differ only after the key is dropped: the event is true for that one step, not until the key is picked up again.

## Constraints

- `door_open` cannot become true before `has_key`: only toggling with the yellow key in hand unlocks the door.
- `at_goal` cannot become true before `door_open`: the wall has no other gap.
- `key_lost` and `door_open` never hold together: the event requires the door not open.
- `key_lost` and `has_key` never hold together: the event requires the key not carried.
- `key_lost` and `at_goal` never hold together: `key_lost` needs a drop step and `at_goal` a forward step.

## What the agent can and cannot do

- Can: turn; move forward onto an empty cell, an open door or the goal; pick up the key with empty hands; drop onto an empty cell in front; toggle the door in front.
- Cannot: walk through a closed or locked door; unlock without the yellow key in hand (toggle then does nothing); pick up the door, walls or goal; drop onto an occupied cell; relock a door.
- Reaching the goal does not require dropping the key. The step onto the goal ends the episode, so `at_goal` is the last step.
- `door_open` can turn false again: toggling an unlocked door shuts it. Nothing relocks it.
- Unlocking does not use up the key, so `has_key` stays true after `door_open` unless the agent drops it. Dropping it then is not `key_lost`, because the door is open.
- `key_lost` can fire more than once while the door stays closed: pick the key up, drop it, pick it up, drop it.

## Example trace

A real episode on the 8 x 8 grid: 17 steps, reward 0.976.

1. 2 turns and moves, no proposition changes
2. `pickup` (step 3): `has_key` true
3. 6 turns and moves, no proposition changes
4. `toggle` (step 10): `door_open` true
5. 6 turns and moves, no proposition changes
6. `forward` (step 17): `at_goal` true [episode terminated]

Variant, a second real episode: `pickup` (step 7): `has_key` true. `drop` (step 8): `has_key` false, `key_lost` true. `pickup` (step 9): `has_key` true, `key_lost` false.

## Propositions
- `has_key`: The agent is currently carrying the yellow key that opens the locked door.
- `door_open`: The separating yellow door is currently open.
- `at_goal`: The agent is currently on the green goal tile.
- `key_lost`: The agent previously acquired the yellow key but is no longer carrying it before opening the door.

## Example tasks

- Eventually acquire the key.
- Open the door after acquiring the key.
- Reach the goal after opening the door.
