# MiniGrid BlockedUnlockPickup

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/BlockedUnlockPickup>
- Gymnasium ID: `MiniGrid-BlockedUnlockPickup-v0`.

## Environment

Two rooms are connected by a locked door. A ball initially blocks access to the door,
a matching key is in the starting room, and the mission's target box is in the other
room. The ball must be moved away, the key acquired, and the door unlocked before the
target can be collected. Colors and positions may vary between resets.

## Objective and episode boundary

The mission is complete when the agent picks up the designated target box. The stock
environment terminates on that pickup and truncates at its step limit.

## Proposition semantics

The propositions denote observable task progress, independent of the raw action used
to cause it.

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

