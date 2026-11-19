# MiniGrid KeyGift

## Environment

One small room with a locked door. A key sometimes lands in the agent's empty hands by itself, and the only thing the key is good for is opening that door. The agent has seven actions: turn left, turn right, move forward, pick up, drop, toggle, and done. Done does nothing; pick up does nothing, because there is nothing to pick up; drop does nothing, because the key cannot be dropped.

Layout: a square room of 7 x 7 cells with an outer wall, so 5 x 5 cells of floor. The door is yellow and sits in the top wall, in the middle. The agent starts in the middle of the room facing up. It opens the door from the floor cell below it, facing up. Nothing else is in the room: no key on the floor, no box, no switch. The layout is the same in every episode and only the gifts change. The agent has the standard MiniGrid view of 7 x 7 cells in front of it, which shows the whole room from the middle; the key it holds shows in its own cell of the view.

The door starts shut and locked. While the agent's hands are empty and the door is shut, a yellow key lands in its hands at any step with chance 1 in 30. The agent cannot drop it. Toggling the door with the key in hand opens the door and uses the key up: the hands are empty again. The door shuts and locks again 10 steps after it opened, and from then on a new key can come. A key never comes while the door is open, while the agent already holds one, or in the last 20 steps of the episode. All draws are made at the start of the episode from the reset seed.

## Objective and episode boundary

The task is to open the door whenever the agent holds the key. The environment never ends the episode on its own: it cuts it at the step limit, 300 steps.

The environment pays 1 for every gift answered by opening the door, nothing else. The episode counts as a success when every key that landed in the hands was answered by an open door. The environment's reward does not depend on the rules of any task.

## Proposition semantics

| id | kind | true when |
|---|---|---|
| `has_door_key` | condition | the agent carries the key; it turns true at the step the key lands and false at the step the door opens |
| `door_open` | condition | the door is open; true from the opening step through the next 9 steps, false when it shuts again |

## Constraints

- `door_open` cannot become true before `has_door_key`: the door opens only for a key in the hands.
- `has_door_key` and `door_open` never hold together: the opening uses the key up, and no key lands while the door is open.

## What the agent can and cannot do

- Can: turn; move forward onto an empty floor cell; toggle the door when it stands in front of the door facing it with the key in hand.
- Cannot: walk through the door, shut or locked or open, because it is in the outer wall and nothing lies behind it; open it without the key; shut it by hand; drop the key; hold two keys.
- Toggling the open door, or toggling the shut door without the key, does nothing.
- The key is the only way to open the door. An agent that does nothing keeps the key it got first and never opens the door.
- The door shuts by itself 10 steps after it opened, also when the agent stands in front of it. A new key can then land, at the shutting step or later.
- A gift can land at any step in the first 280, including the first one. The door is at most 10 actions away from any floor cell and facing, so every gift can be answered before the episode ends.
- How many gifts come in an episode depends on the seed and on how fast the agent answers: 3 to 13 in 40 episodes of an agent that answers each gift at once.

## Example trace

A real episode: 300 steps, 8 keys landed, every one answered, reward 8.

1. steps 1 to 9, the agent waits: no changes
2. step 10, a key lands (the agent is in the middle of the room): `has_door_key` true
3. 2 moves up, no proposition changes
4. `toggle` (step 13): `has_door_key` false, `door_open` true
5. steps 14 to 22, the agent waits in front of the door: no changes
6. step 23, the door shuts: `door_open` false
7. step 62, a key lands: `has_door_key` true; `toggle` (step 63): `has_door_key` false, `door_open` true
8. steps 64 to 258, six more gifts (steps 76, 94, 177, 195, 240 and 257), each answered by a `toggle` on the next step

The episode shows that an agent that waits next to the door answers each gift with one toggle.

## Propositions
- `has_door_key`: The agent is currently holding the key that opens the locked door.
- `door_open`: The locked door is currently open.

## Example tasks

- Whenever you are holding the key, open the door.
- Whenever you are holding the key, try to open the door.
