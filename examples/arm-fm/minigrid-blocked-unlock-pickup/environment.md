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

## Labeling API

- `env.mission`: the mission string, for example `pick up the grey box`. Mission targets
  come from it: do not assume a fixed color or object, match the designated one.
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid
  coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- Object attributes: `type` (for example `key`, `door`, `box`, `ball`, `wall`, `goal`),
  `color`, and `is_open` and `is_locked` on doors. Door openness and lock state come from
  them.
- `env.carrying`: the carried object, or `None`; it exposes `type` and `color`. Carry state
  comes from it.
- `env.width`, `env.height`: grid size.

Object classes cannot be imported. To scan the grid, guard empty cells with
`cell is not None` before reading an attribute. This expression checks whether any cell holds
a given object type:

    any(cell is not None and cell.type == "<type>" for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

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
