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
- `has_door_key`: The agent is currently carrying the key whose color matches the locked door.
- `door_open`: The locked door leading to the target room is currently open.
- `target_picked_up`: The agent is currently carrying the mission's designated box.
- `key_lost`: The agent previously acquired the matching key but is no longer carrying it before opening the door.

## Example tasks

- Eventually pick up the target box.
- Acquire the matching key before opening the door.
- Open the door before picking up the target box.
