# Craftium Diamond Gathering

## Source and runtime

- Official source: <https://github.com/mikelma/craftium>
- Gymnasium ID: `Craftium/Diamond-v0`, registered by this repository
  (`app/src/arm_fm/custom_envs/craftium_diamond.py`) on top of Craftium's `OpenWorld-v0`.
- Reproduction status: ARM-FM describes a custom sparse-reward diamond task but does
  not publish its Craftium configuration. `Craftium/Diamond-v0` is a reconstruction (stock
  OpenWorld cut down to the wood-stone-iron-diamond chain), not an exact reproduction.

## Environment

Craftium exposes a 3D voxel world (VoxeLibre) through Gymnasium. The agent plays in first
person with movement, camera, digging, placement, and inventory-slot actions. The world is
the same every episode: the agent starts in a birch forest above a stone layer with iron
below it, and every reset restores the whole world, the inventory, and the milestones.

The game grants tools; there is no crafting. Milestones must be reached in order, and each
one counts only nodes dug after the previous one:

1. Wood: digging 2 tree trunks grants a wooden pickaxe.
2. Stone: digging 3 stone nodes grants a stone pickaxe.
3. Iron: digging 3 iron ore nodes grants an iron pickaxe.
4. Diamond: digging 1 diamond ore node pays the only reward and ends the episode.

## Objective and episode boundary

The ARM-FM task gives sparse success only for obtaining a diamond. Its intended
progression is wood, stone, iron, then diamond. The environment pays reward 1.0 once, when
the diamond milestone is reached, and terminates then. Death terminates the episode without
reward, and the episode is truncated after `max_steps` agent steps (10,000 by default).

## Proposition semantics

Each proposition is the status of one milestone: it becomes true on the first transition
in which the agent reaches that milestone and stays true for the rest of the episode. It is
read from the cumulative `env.milestones`, so it never repeats and no acquisition is lost
when several happen within one action. It does not read the RM state.

## Labeling API
- `env.milestones`: a read-only mapping `str -> bool` with exactly the keys `"wood"`,
  `"stone"`, `"iron"` and `"diamond"`. A value turns `True` the first time the agent reaches
  that milestone in the episode and never turns back; the milestones are reached in this order.
- `env.inventory`: a read-only mapping `str -> int` with exactly the keys `"wood"`, `"stone"`,
  `"iron"` and `"diamond"`: how many tree, stone, iron ore and diamond ore nodes the agent has
  dug so far in the episode. The counts only grow and also include digs that happen before the
  matching milestone is next in line.

A milestone stays `True` after it is reached, so a predicate that reads `env.milestones` is a
status that remains true for the rest of the episode, not a one-step event. This keeps every
acquisition visible even when several milestones are reached within one action.

## Propositions
- `wood_acquired`: The agent has reached the wood milestone (dug 2 tree trunks and received the wooden pickaxe); stays true for the rest of the episode.
- `stone_acquired`: The agent has reached the stone milestone (after wood, dug 3 stone nodes and received the stone pickaxe); stays true for the rest of the episode.
- `iron_acquired`: The agent has reached the iron milestone (after stone, dug 3 iron ore nodes and received the iron pickaxe); stays true for the rest of the episode.
- `diamond_acquired`: The agent has reached the diamond milestone (after iron, dug a diamond ore node), which ends the episode; stays true until then.

## Example tasks

- Eventually acquire a diamond.
- Acquire wood before stone.
- Acquire stone before iron.
- Acquire iron before a diamond.
