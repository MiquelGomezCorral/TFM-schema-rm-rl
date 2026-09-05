# XLand-MiniGrid Medium-1M

## Source and runtime

- Official source: <https://github.com/corl-team/xland-minigrid>
- Benchmark data: <https://huggingface.co/datasets/Howuhh/xland_minigrid>
- Benchmark: `xminigrid.load_benchmark("medium-1m")`.
- Rulesets used by ARM-FM: the first 1,000 benchmark entries.
- Practical carrier default: `xminigrid.make("XLand-MiniGrid-R4-13x13")`.
- Reproduction note: the paper does not report its exact grid carrier; R4 13x13 is a
  documented official default, not a claimed paper setting.

## Environment

XLand-MiniGrid is a JAX environment with procedurally composed goals, transformation
rules, and initial object placements. A ruleset may require holding an object, reaching
or approaching a tile, arranging relative positions, or applying one or more object
transformation rules before satisfying the final goal. Object shape and color are part
of the task definition.

## Objective and episode boundary

Each `medium-1m` ruleset defines its own goal and world rules. Success means satisfying
that ruleset's encoded goal before the carrier environment's time limit. ARM-FM treats
each ruleset as a separate task with its own RM.

## Proposition semantics

This benchmark cannot have one concrete proposition vocabulary for all one million
rulesets. These role-based propositions are a reusable template. Before generating an
RM for a particular ruleset, append its decoded goal, rules, objects, and concrete
role bindings to the user prompt.

## Propositions
- `required_object_held`: The agent holds the object required by the active ruleset.
- `required_object_reached`: The agent occupies or reaches the tile required by the active ruleset.
- `required_relation_satisfied`: The active directional or adjacency relation between required entities is satisfied.
- `intermediate_object_created`: A transformation rule has produced an object required by a later rule or the final goal.
- `goal_satisfied`: The complete goal encoded by the active ruleset is currently satisfied.

## Example tasks

- Eventually satisfy the active ruleset's goal.
- Create the required intermediate object before satisfying the final goal.
- Establish the required relation before satisfying the final goal.
