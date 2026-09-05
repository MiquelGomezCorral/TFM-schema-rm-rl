# MiniGrid DoorKey

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/DoorKey>
- Gymnasium IDs: `MiniGrid-DoorKey-5x5-v0`, `MiniGrid-DoorKey-6x6-v0`,
  `MiniGrid-DoorKey-8x8-v0`, and `MiniGrid-DoorKey-16x16-v0`.
- Recommended default: `MiniGrid-DoorKey-8x8-v0`.

## Environment

The agent starts on one side of a wall. A locked yellow door separates it from
the green goal, and a matching yellow key is accessible on the starting side.
The agent can turn, move forward, pick up or drop an object, and toggle a door.
The layout and initial pose may change between resets.

## Objective and episode boundary

The task is complete when the agent reaches the goal after using the key to unlock
and open the door. The stock environment terminates on reaching the goal and truncates
at its step limit. Its sparse success reward is
`1 - 0.9 * (step_count / max_steps)`.

## Proposition semantics

These are state conditions evaluated at every time point. They are specifications for
RM generation; this project does not implement their environment adapters.

## Propositions
- `has_key`: The agent is currently carrying the yellow key that opens the locked door.
- `door_open`: The separating yellow door is currently open.
- `at_goal`: The agent is currently on the green goal tile.
- `key_lost`: The agent previously acquired the yellow key but is no longer carrying it before opening the door.

## Example tasks

- Eventually acquire the key.
- Open the door after acquiring the key.
- Reach the goal after opening the door.

