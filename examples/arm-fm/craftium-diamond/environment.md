# Craftium Diamond Gathering

## Source and runtime

- Official source: <https://github.com/mikelma/craftium>
- Gymnasium ID: `Craftium/Diamond-v0`, registered by this repository
  (`app/src/arm_fm/custom_envs/craftium_diamond.py`) on top of Craftium's `OpenWorld-v0`.
- Reproduction status: ARM-FM describes a custom sparse-reward diamond task but does
  not publish its Craftium configuration. `Craftium/Diamond-v0` is a reconstruction (stock
  OpenWorld cut down to the wood-stone-iron-diamond chain), not an exact reproduction.
- Runtime: Craftium built from commit `8eb8707cb756df47e76131a0058ab724d2383c76` (`requirements.txt`); the installed package reports version 0.0.1. The task code is `DiamondEnv` and the Lua mod in `app/src/arm_fm/custom_envs/craftium_diamond/`.
- Evidence tags: `[code: file:function]` is that mod or class; `[run]` is a run of the real engine with `craftium_debug_route.py`; `unknown` means no source says.

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

The agent starts at x 120, y 16.5, z 92 (y is height) at midday; the day cycle lasts 5000 engine steps [code: init.lua `register_on_joinplayer`, `TIMEOFDAY_STEP`]. Actions are 18 discrete keys: a leading no-op, `forward`, `backward`, `left`, `right`, `jump`, `sneak`, `dig`, `place`, `slot_1` to `slot_5`, and four mouse moves [code: craftium_diamond.py:KEYS]. Observations are grayscale 320x180 frames [code: craftium_diamond.py:register kwargs]. A node counts for a milestone when its name contains `diamond`, `iron`, `stone` or `tree`, checked in that order [code: init.lua:`MATCH_ORDER`]. Only digs of the next milestone's kind move it forward; other digs raise `inventory` only, and the count restarts at each milestone [code: init.lua:`record_dig`]. The milestone tools go to slot 1 [code: init.lua:`grant_tool`].

## Objective and episode boundary

The ARM-FM task gives sparse success only for obtaining a diamond. Its intended
progression is wood, stone, iron, then diamond. The environment pays reward 1.0 once, when
the diamond milestone is reached, and terminates then. Death terminates the episode without
reward, and the episode is truncated after `max_steps` agent steps (10,000 by default).

Reward 1.0 and termination come on the step whose snapshot first shows the diamond milestone [code: craftium_diamond_env.py:DiamondEnv.step; run: `craftium_debug_route.py`].

## Proposition semantics

Each proposition is the status of one milestone: it becomes true on the first transition
in which the agent reaches that milestone and stays true for the rest of the episode. It is
read from the cumulative `env.milestones`, so it never repeats and no acquisition is lost
when several happen within one action. It does not read the RM state.

| id | kind | true when |
|---|---|---|
| `wood_acquired` | latch | `env.milestones["wood"]` is true |
| `stone_acquired` | latch | `env.milestones["stone"]` is true |
| `iron_acquired` | latch | `env.milestones["iron"]` is true |
| `diamond_acquired` | latch, final step | `env.milestones["diamond"]` is true; the episode ends on the same step |

## Constraints

- `stone_acquired` cannot become true before `wood_acquired`: only the next milestone's kind advances the chain [code: init.lua:`record_dig`; run: `craftium_debug_route.py`, order wood, stone, iron, diamond].
- `iron_acquired` cannot become true before `stone_acquired`: same rule [code: `record_dig`; run: same].
- `diamond_acquired` cannot become true before `iron_acquired`: same rule [code: `record_dig`; run: same].
- `wood_acquired` cannot become false once true: the environment raises an error if a milestone flag goes back [code: craftium_diamond_env.py:`_read_snapshot`].
- `stone_acquired` cannot become false once true: same reason [code: `_read_snapshot`].
- `iron_acquired` cannot become false once true: same reason [code: `_read_snapshot`].
- `diamond_acquired` cannot become false once true: same reason [code: `_read_snapshot`].

## What the agent can and cannot do

- Can: move, jump, sneak, turn the camera, `dig`, `place`, pick inventory slots 1 to 5 [code: craftium_diamond.py:KEYS].
- Cannot: craft, since the action set has no crafting or menu action; the mod grants tools instead [code: KEYS, `grant_tool`].
- Unknown: which tool the game requires to dig stone, iron ore or diamond ore, how many agent steps a real run takes, and whether one agent step can dig two nodes.
- Digs made before a milestone is next do not count toward it: iron ore dug before `stone_acquired` raises `inventory["iron"]` but not the iron milestone [code: init.lua:`record_dig`].
- `diamond_acquired` is the last step of a successful episode [code: craftium_diamond_env.py:DiamondEnv.step; run: `craftium_debug_route.py`].
- Death ends the episode with reward 0, so any proposition still false then stays false [code: init.lua:`register_on_dieplayer`].

## Example trace

Debug route, not a real dig. The mod grants each milestone at a fixed engine step as if the agent had dug the nodes [code: init.lua `craftium_debug_route`; run: `craftium_debug_route.py`, log `craftium_debug_route_log.json`, no-op agent]. The engine steps are fixed; the agent step differs by a step or two between runs (two runs here gave 94, 124, 154 and 184; a reviewer's rerun gave 95, 125, 155 and 185) because the engine runs some frames before the first observation [run: `craftium_debug_route.py`, two runs, plus a reviewer's rerun]. A real digging run: `unknown`, no scripted route exists.

1. About 93 agent steps of no-op: no proposition changes.
2. Engine step 300 (agent step about 94): `wood_acquired` true; `inventory` wood 2.
3. Engine step 330 (agent step about 124): `stone_acquired` true; stone 3.
4. Engine step 360 (agent step about 154): `iron_acquired` true; iron 3.
5. Engine step 390 (agent step about 184): `diamond_acquired` true; reward 1.0; the episode terminates.

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
