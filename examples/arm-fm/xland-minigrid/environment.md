# XLand-MiniGrid Medium-1M

## Environment

XLand-MiniGrid is a grid world where a ruleset defines the task: one goal, up to 9 transformation rules and up to 16 initial objects. A ruleset index picks the ruleset, so it does not change between resets of one task.

The rulesets used are the first 1,000 of the medium set, read as indices 0 to 999.

Layout: a 13x13 grid with a grey wall border and a wall cross on row 6 and column 6, so four rooms of 5x5 free cells. Each of the four wall arms has one door (offset 1 to 5 along the arm), closed and not locked, of a random color among red, green, blue, purple, yellow, grey. No locked or open door is ever generated, so keys are plain objects here. Every initial object lands on a distinct random floor cell of any room; so does the agent, with a random direction and an empty pocket. Door and wall cells never hold objects. All free cells connect through the four doors. The agent can start in any of the four rooms.

Ruleset contents in the first 1,000: goals say that the agent holds a tile, that the agent is next to a tile, that two tiles are next to each other, that one tile is on a given side of another, or that a tile is on a given side of the agent; no goal says that the agent stands on a tile or is at a position, and none is empty. Rules per ruleset: 0 to 9. Initial objects are goal, ball, square, pyramid, key, hex and star tiles in several colors, 3 to 15 per ruleset. A rule product is one of those kinds, or rarely a floor tile. Most goal tiles name a tile that only a rule can create; the rest are initial objects.

Actions are six: forward, turn clockwise, turn counterclockwise, pickup, putdown, toggle; there is no `done`. The observation is a 5x5 window of `(tile, color)` ahead of the agent with no occlusion; it carries neither the goal nor the rules.

## Objective and episode boundary

The episode ends when the ruleset goal check passes after the action and the rules of that step. The reward is then `1 - 0.9 * (steps taken / step limit)`, otherwise 0. The step limit is `3 * 13 * 13 = 507`; at step 507 without the goal the episode ends with reward 0. No step follows the goal.

The goal check also needs a specific action: "the agent holds `a`" fires on pickup when the pocket holds `a`; "the agent is next to `a`" on forward when a neighbour of the agent is `a`; "`a` is next to `b`" on putdown when the put cell holds `a` or `b` and a neighbour holds the other; "`a` is on a given side of the agent" on forward or putdown when the neighbour on that grid side is `a`; "`b` is on a given side of `a`" on putdown with `b` on that side of `a`. It is not known whether each of the 1,000 rulesets is solvable; a distractor rule can make a task unsolvable.

## Proposition semantics

The five ids are roles. Each is bound to concrete `(tile, color)` pairs of one ruleset. Conditions read the grid cells (tile and color), the agent's position and pocket, and the previous valuation. Up, right, down, left are grid sides (up is the row above), not relative to the agent's facing.

| id | kind | true when |
|---|---|---|
| `required_object_held` | condition | the agent's pocket holds the bound tile |
| `required_object_reached` | condition, reading | the bound tile is at the agent's cell or at one of its four orthogonal neighbours |
| `required_relation_satisfied` | condition, reading | two bound tiles are orthogonal neighbours, or `b` is on the named grid side of `a`, or the neighbour on the named grid side of the agent is the bound tile |
| `intermediate_object_created` | latch, reading | a bound rule's product tile is in some grid cell or in the pocket now, or this proposition was true at the previous step |
| `goal_satisfied` | condition, reading | the ruleset goal predicate holds on the current grid, agent position and pocket, whatever action was taken |

Readings:
- `reached` against `relation`: the descriptions leave the split open. The goals "the agent is next to `a`" and "the agent stands on `a`" (not in the first 1,000) go to `reached`; "`a` is next to `b`", "`b` is on a given side of `a`" and "`a` is on a given side of the agent" go to `relation`.
- `intermediate_object_created` is a latch. It is true from step 0 when the product is also an initial object. A product made by a holding rule exists only in the pocket, so the pocket counts.
- `goal_satisfied` ignores the action. It can be true while the episode goes on: with an agent-next-to goal and the tile already adjacent, turn, pickup and toggle do not end the episode. It can also be true at reset. Termination implies the predicate; the predicate does not imply termination.

## Constraints

- `goal_satisfied` cannot become true before `intermediate_object_created` when the goal tile is not an initial object: object tiles come only from the initial objects and rule products; pickup, putdown and toggle move or relabel existing tiles. It holds only in rulesets where the goal tile is a product.
- `intermediate_object_created` cannot become false once true: by the latch reading's definition. The object itself can vanish; a later rule or a pickup can consume it.
- Any other order between the roles depends on the bound rules; the roles themselves fix no further order. Derive it from the ruleset.

## What the agent can and cannot do

- Forward: onto floor, goal and open-door cells only; a wall, a closed door or any object blocks it and the agent stays, but the step still counts as `forward` for rules and goals. Turns change only the direction and trigger no rule or goal.
- Pickup: the facing cell must hold a ball, square, pyramid, key, hex or star, and the pocket must be empty; the cell becomes black floor. Goal tiles, doors and walls cannot be picked up. The pocket holds one tile.
- Putdown: the pocket must be full and the facing cell must be floor; a goal tile, door, wall or object blocks it.
- Toggle: a closed door opens, an open door closes; a locked door opens only with a key of its color in the pocket, and the key stays. No locked door exists in this layout.
- Rules run after every action, in listed order, each on the grid the previous rule left; two rules can chain inside one step. Each rule kind fires on fixed actions only:
  - Holding rule (`a -> c`): on pickup, if the pocket holds `a` it becomes `c`. Picking up `a` therefore leaves `c` in the pocket at once, and `a` is never seen there. It also fires when the pickup failed.
  - Agent-next-to rule (`a -> c`): on forward, every neighbour of the agent holding `a` becomes `c`, also when forward is blocked.
  - Agent-side rule (`a -> c`): on forward or putdown, only the neighbour on that grid side.
  - Tile-pair rule (`a, b -> c`) and its side variant: on putdown only, when the put cell holds one input and a neighbour (for the side variant, the one on the named side) holds the other. The neighbour's cell becomes `c` and the put cell becomes black floor, so both inputs are consumed and `c` is not in the pocket. It also fires after a failed putdown when the facing cell already holds an input with the other beside it.
- Nothing recreates a consumed tile except another rule, so a rule can make the goal unreachable. Pocket, adjacency and relation conditions can turn false again when the agent drops, moves or a rule consumes the tile.

## Example trace

One real episode. Ruleset index 197, first reset. Goal: a blue pyramid on the right side of the agent. Rules: a holding rule (purple star -> blue pyramid), an agent-side rule for the down side (yellow pyramid -> purple star), an agent-next-to rule (brown star -> red hex). Initial objects yellow pyramid, red goal, brown ball, brown star. 15 steps, reward 0.9734. Bindings: held = blue pyramid; relation = blue pyramid on the agent's right; created = purple star; `reached` unbound (false); `goal_satisfied` = the relation.

1. turn counterclockwise, 3 forward, `toggle` the closed door ahead (step 5), 4 forward, turn clockwise: no proposition changes
2. `forward` (step 11) to a cell directly above the yellow pyramid: the agent-side rule (down) makes a purple star, `intermediate_object_created` true
3. `pickup` (step 12): the holding rule turns the star into a blue pyramid in the pocket, `required_object_held` true
4. `forward` onto the emptied cell, turn counterclockwise to face right (steps 13 and 14): no changes
5. `putdown` (step 15): `required_object_held` false, `required_relation_satisfied` true, `goal_satisfied` true [episode terminated]

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
