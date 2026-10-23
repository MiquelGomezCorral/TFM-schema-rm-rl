# Craftium Diamond Gathering: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/mikelma/craftium>
- Gymnasium ID `Craftium/Diamond-v0`, registered by this repository (`app/src/arm_fm/custom_envs/craftium_diamond.py`) on top of Craftium's `OpenWorld-v0`.
- Reproduction status: ARM-FM describes a custom sparse-reward diamond task but does not publish its Craftium configuration. `Craftium/Diamond-v0` is a reconstruction (stock OpenWorld cut down to the wood-stone-iron-diamond chain), not an exact reproduction.
- Runtime: Craftium built from commit `8eb8707cb756df47e76131a0058ab724d2383c76` (`requirements.txt`); the installed package reports version 0.0.1. The task code is `DiamondEnv` and the Lua mod in `app/src/arm_fm/custom_envs/craftium_diamond/`.
- `[code: file:function]` is that mod or class. `[run]` is a run of the real engine with `craftium_debug_route.py`. `unknown` means no source says.

## Truth conditions in code

Each milestone is already cumulative, so no previous valuation is needed.

- `wood_acquired`: `env.milestones["wood"]`
- `stone_acquired`: `env.milestones["stone"]`
- `iron_acquired`: `env.milestones["iron"]`
- `diamond_acquired`: `env.milestones["diamond"]`

The dug-node count is `env.inventory[<kind>]` with kinds `wood`, `stone`, `iron`, `diamond`.

## Evidence

Environment
- Start at x 120, y 16.5, z 92 (y is height) at midday; day cycle of 5000 engine steps: [code: init.lua `register_on_joinplayer`, `TIMEOFDAY_STEP`].
- 18 discrete keys (no-op, `forward`, `backward`, `left`, `right`, `jump`, `sneak`, `dig`, `place`, `slot_1` to `slot_5`, four mouse moves): [code: craftium_diamond.py:KEYS].
- Grayscale 320x180 observations: [code: craftium_diamond.py:register kwargs].
- A node counts by name containing `diamond`, `iron`, `stone` or `tree`, in that order: [code: init.lua:`MATCH_ORDER`].
- Only the next milestone's kind advances; the count restarts at each milestone: [code: init.lua:`record_dig`].
- Milestone tools go to slot 1: [code: init.lua:`grant_tool`].
- Same world every episode, reset restores world, inventory and milestones, milestone thresholds (2, 3, 3, 1): no tag in the old file.

Objective and episode boundary
- Reward 1.0 and termination come on the step whose snapshot first shows the diamond milestone: [code: craftium_diamond_env.py:DiamondEnv.step; run: `craftium_debug_route.py`].
- Death ends the episode without reward; truncation after `max_steps` (10,000 by default): death is [code: init.lua `register_on_dieplayer`]; the default has no tag in the old file.

Constraints
- Order wood, stone, iron, diamond: [code: init.lua:`record_dig`; run: `craftium_debug_route.py`, order wood, stone, iron, diamond].
- No milestone goes back to false, the environment raises an error: [code: craftium_diamond_env.py:`_read_snapshot`].

What the agent can and cannot do
- Can list: [code: craftium_diamond.py:KEYS].
- Cannot craft, the mod grants tools: [code: KEYS, `grant_tool`].
- Not known (tool needed for stone, iron ore and diamond ore; agent steps of a real run; two nodes in one step): `unknown`.
- Digs before a milestone is next do not count: [code: init.lua:`record_dig`].
- `diamond_acquired` is the last step: [code: craftium_diamond_env.py:DiamondEnv.step; run: `craftium_debug_route.py`].
- Death: [code: init.lua:`register_on_dieplayer`].

Example trace
- The mod grants each milestone at a fixed engine step: [code: init.lua `craftium_debug_route`; run: `craftium_debug_route.py`, log `craftium_debug_route_log.json`, no-op agent].
- Agent steps differ by a step or two between runs: two runs here gave 94, 124, 154 and 184; a reviewer's rerun gave 95, 125, 155 and 185. The engine runs some frames before the first observation: [run: `craftium_debug_route.py`, two runs, plus a reviewer's rerun].
- A real digging run: `unknown`, no scripted route exists.

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
