# Craftium Diamond Gathering

## Source and runtime

- Official source: <https://github.com/mikelma/craftium>
- Closest stock Gymnasium ID: `Craftium/OpenWorld-v0`.
- Reproduction status: ARM-FM describes a custom sparse-reward diamond task but does
  not publish its Craftium configuration. The stock OpenWorld environment is a usable
  carrier, not an exact reproduction.

## Environment

Craftium exposes a procedurally generated 3D voxel world through Gymnasium. The agent
uses first-person movement, camera, digging, placement, and inventory-slot actions.
Mining higher-tier resources requires collecting materials and obtaining suitable tools
in a dependency chain. World layout and resource locations vary between episodes.

## Objective and episode boundary

The ARM-FM task gives sparse success only for obtaining a diamond. Its intended
progression is wood, stone, iron, then diamond. The exact episode termination and
sparse-reward configuration must be supplied when recreating the unpublished task.

## Proposition semantics

Each proposition is a one-time inventory acquisition event: it becomes true on the
first transition where the resource appears in the agent's inventory. Later inventory
loss does not cause the acquisition event to repeat.

## Propositions
- `wood_acquired`: The agent acquires the wood required to begin the tool progression.
- `stone_acquired`: The agent acquires stone after obtaining the required wooden equipment.
- `iron_acquired`: The agent acquires iron after obtaining the required stone equipment.
- `diamond_acquired`: The agent acquires a diamond after obtaining the required iron equipment.

## Example tasks

- Eventually acquire a diamond.
- Acquire wood before stone.
- Acquire stone before iron.
- Acquire iron before a diamond.

