# MiniGrid KeyCorridor S6R3

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/KeyCorridorS6R3>
- Gymnasium ID: `MiniGrid-KeyCorridorS6R3-v0`.
- Reproduction note: the paper's human-intervention table says S3R3, while its released
  code and artifacts use S6R3. This example follows the released artifact.

## Environment

The agent begins in a central corridor connected to several rooms. The mission's target
object is behind a locked door, while the matching key is hidden in another randomly
selected room. The mission reveals the target object's color and type but not the key's
location.

## Objective and episode boundary

The mission is complete when the designated target object is picked up. The stock
environment terminates on that pickup and truncates at its step limit.

## Proposition semantics

The target and matching key are determined from the current randomized mission and
layout, not hard-coded colors.

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

