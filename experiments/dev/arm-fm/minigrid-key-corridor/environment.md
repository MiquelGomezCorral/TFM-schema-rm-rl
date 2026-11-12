# MiniGrid KeyCorridor S6R3

## Environment

The agent begins in a central corridor connected to several rooms. The mission's target object is behind a locked door, while the matching key is hidden in another randomly selected room. The mission reveals the target object's color and type but not the key's location. The agent has seven actions: turn left, turn right, move forward, pick up, drop, toggle, and done. Done does nothing.

Layout: 3x3 rooms of 6x6 cells (a 16x16 grid). The three rooms of the middle column form a hallway, where the agent starts. Unlocked doors of random color join neighbouring rooms (side room to hallway, or side room to the room above or below) until every room is reachable. A side room may open only onto another side room: most layouts have at least one unlocked side room without a door onto the hallway. Those doors start closed and unlocked, and toggle opens them without a key. One door is locked: it is on the left wall of one right-column room (random row), and the target lies in that room. The matching key lies in one of the three left-column rooms (random room and cell). The target is always a ball, so the mission reads "pick up the <color> ball". In most layouts another door has the locked door's color, so color alone does not identify the locked door; being locked does. Rooms are opaque: the agent sees through no wall or closed door.

## Objective and episode boundary

The mission is complete when the designated target object is picked up. The environment ends the episode on that pickup and cuts it at the step limit.

The step limit is 30 times 6 squared, 1080 steps. Only picking up the mission's ball ends the episode.

## Proposition semantics

The target and matching key are determined from the current randomized mission and layout, not hard-coded colors. The mission names only the target object. The matching key and the locked door share one color that is independent of the target's color. Exactly one door starts locked, and it guards the target's room.

| id | kind | true when |
|---|---|---|
| `key_found` | latch, reading | the matching key's cell lies in the 7x7 box in front of the agent now (the agent's row or column and the 6 cells ahead, 3 cells to each side), walls ignored; or `key_found` was true at the previous step |
| `has_matching_key` | condition | the agent carries a key of the locked door's color |
| `target_door_open` | condition | the locked door is open; false again if toggled shut |
| `target_room_entered` | latch, reading | the agent stands on the locked doorway or on a cell inside the target room now (the room's 6x6 block, door cell included); or `target_room_entered` was true at the previous step |
| `target_picked_up` | condition, last step only | the agent carries the mission's ball |

Readings:

- `key_found`: the description does not say what "located" means. Walls are ignored: a key behind a closed door or a wall inside the box counts. In some layouts the key is already inside the box at reset, so `key_found` can be true at the first step.
- `target_room_entered`: the description does not say whether the doorway is inside. The doorway counts as inside. The ball lies next to the doorway in some layouts, so picking it up from the doorway is a regular case.

## Constraints

- `has_matching_key` cannot become true before `key_found`: the agent picks the key up from the cell in front of it, which lies in the box.
- `target_door_open` cannot become true before `has_matching_key`: only toggling with the matching key unlocks the door.
- `target_room_entered` cannot become true before `target_door_open`: the locked door is the room's only way in, because no door is added to a locked room.
- `target_picked_up` cannot become true before `target_door_open`: same reason.
- `target_picked_up` cannot become true before `target_room_entered`: the ball lies inside the room, and the only cells that face it are inside cells or the doorway, which count as entered.
- `has_matching_key` and `target_picked_up` never hold together: the agent holds one object.
- `key_found` cannot become false once true: it is a latch.
- `target_room_entered` cannot become false once true: it is a latch.

## What the agent can and cannot do

- Can: turn; move forward onto an empty cell or an open door; toggle any closed unlocked door open; pick up the key or the ball with empty hands; drop onto an empty cell in front.
- Cannot: walk through a closed door before toggling it; open the locked door without the matching key; carry the key and the ball at once.
- The agent's own view stops at walls and closed doors; `key_found` ignores that (reading above).
- `key_found` turns true only on a turn or a move: the key does not move on its own, and toggle, pick up and drop leave the agent's cell and direction unchanged. Opening a door does not change the box.
- After `target_door_open` the key must be dropped before the ball can be picked up.
- `has_matching_key` and `target_door_open` can turn false again: the agent can drop the key and shut the door.
- It is not known which left-column room and cell holds the key: the mission gives no hint. That the key is in the left column is known.

## Example trace

A real episode, mission "pick up the yellow ball": 40 steps, reward 0.967.

1. 3 turns and moves, no proposition changes
2. `forward` (step 4): `key_found` true
3. 1 turn or move, no proposition changes
4. `toggle` (step 6): no proposition changes (the door between the hallway and a left-column room opens)
5. 8 turns and moves, no proposition changes
6. `pickup` (step 15): `has_matching_key` true
7. 13 turns and moves, no proposition changes
8. `toggle` (step 29): `target_door_open` true
9. 1 turn or move, no proposition changes
10. `drop` (step 31): `has_matching_key` false
11. 1 turn or move, no proposition changes
12. `forward` (step 33): `target_room_entered` true (the agent stands on the doorway)
13. 6 turns and moves, no proposition changes
14. `pickup` (step 40): `target_picked_up` true [episode terminated]

## Propositions
- `key_found`: The agent has located the key matching the target room's locked door.
- `has_matching_key`: The agent is currently carrying that matching key.
- `target_door_open`: The locked door guarding the mission target is currently open.
- `target_room_entered`: The agent has entered the room containing the mission target.
- `target_picked_up`: The agent is currently carrying the mission's designated object.

## Example tasks

- Eventually pick up the target object.
- Find the matching key before opening the target door.
- Open the target door before picking up the target object.
