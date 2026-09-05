# MiniGrid UnlockPickup

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- Gymnasium ID: `MiniGrid-UnlockPickup-v0`.
- Paper status: named in the ARM-FM human-intervention table, but no finalized RM is
  published in the paper repository.

## Environment

Two rooms are connected by a locked door. The target box is in the second room. A key
matching the door is available in the starting room. Object color and placement may
change between resets. The agent can turn, move, pick up or drop objects, and toggle
the door.

## Objective and episode boundary

The mission is to unlock the door and pick up the designated box. The stock environment
terminates when the correct box is picked up and truncates at its step limit.

## Proposition semantics

The target is the box named by the current mission, not any box that may be present.

## Propositions
- `has_door_key`: The agent is currently carrying the key whose color matches the locked door.
- `door_open`: The locked door leading to the target room is currently open.
- `target_picked_up`: The agent is currently carrying the mission's designated box.
- `key_lost`: The agent previously acquired the matching key but is no longer carrying it before opening the door.

## Example tasks

- Eventually pick up the target box.
- Acquire the matching key before opening the door.
- Open the door before picking up the target box.

