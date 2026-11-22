# XLand-MiniGrid ruleset Figure 10 B

## Environment

A 13 x 13 grid with a grey wall border and a wall cross on row 6 and column 6, so four rooms of 5 x 5 free cells. Each of the four wall arms has one door at a random place along the arm, closed and not locked, of a random color among red, green, blue, purple, yellow and grey. Every initial object lands on its own random floor cell in any room; so does the agent, with a random facing and an empty pocket. All free cells connect through the four doors. The layout, the doors and the start change with every reset; the ruleset does not.

This world's ruleset:
- Goal: a `forward` or `putdown` with a blue pyramid on the cell to the right of the agent.
- Rules, in the order they run after every action:
  1. A holding rule: a `pickup` while the pocket holds a blue star turns it into a blue pyramid in the pocket. Picking up a blue star fires it at once, so the pocket never shows a blue star.
- Initial objects: a blue star, a purple ball, an orange pyramid.

Actions: `forward`, `turn_right` (clockwise), `turn_left`, `pickup`, `putdown`, `toggle`; there is no `done`. The agent sees the 5 x 5 cells in front of it (walls hide nothing), what it carries and which way it faces; it never sees the rules or the goal.

## Objective and episode boundary

The episode ends on the step the goal fires: a `forward` or `putdown` with a blue pyramid on the cell to the right of the agent. The reward is then `1 - 0.9 * (steps taken / 507)`, otherwise 0. The step limit is 507 steps; at step 507 without the goal the episode ends with reward 0. No step follows the goal.

## Proposition semantics

| id | kind | true when |
|---|---|---|
| `blue_pyramid_made` | event | a rule turned a tile into a blue pyramid on this step |
| `blue_star_picked_up` | event | this step's `pickup` took a blue star from the grid into the empty pocket |
| `blue_pyramid_on_right` | event | the goal fired on this step: a `forward` or `putdown` with a blue pyramid on the cell to the right of the agent; the episode ends on this step |

Every proposition is an event: true only on the step its action fires, false on every other step, also while the made tile stays in the world. This file reads "made" as the step a rule changes a tile, so a rule that fires again makes its event true again, and "picked up" as the step the tile leaves the grid for the pocket. Up, right, down and left are sides of the grid (up is the row above), whatever way the agent faces.

## Constraints

- `blue_pyramid_on_right` cannot become true before `blue_pyramid_made`: a blue pyramid only exists once a rule makes it.

## What the agent can and cannot do

- Forward: onto floor, goal tiles and open doors only; a wall, a closed door or any object blocks it and the agent stays, but the step still counts as `forward` for rules and the goal. Turns change only the facing and fire no rule and no goal.
- Pickup: the facing cell must hold a ball, square, pyramid, key, hex or star, and the pocket must be empty; the cell becomes floor. Goal tiles, doors and walls cannot be picked up. The pocket holds one tile.
- Putdown: needs a full pocket and floor in the facing cell; a goal tile, a door, a wall or an object blocks it.
- Toggle: opens a closed door and closes an open one. No door is locked.
- Rules run after every action, in the order listed, each on the grid the one before left, so two rules can fire in one step. A tile a rule uses up comes back only if a rule makes it again, so a rule can make the goal unreachable.
- `blue_star_picked_up` and `blue_pyramid_made` are true on the same step: the holding rule fires on the pickup itself.

## Example trace

One real episode that reaches the goal: 18 steps, reward 0.9680.

1. 14 steps of turning and moving
2. `pickup` (step 15): `blue_pyramid_made`, `blue_star_picked_up` true
3. 2 steps of turning and moving
4. `putdown` (step 18): `blue_pyramid_on_right` true [episode terminated]

## Propositions
- `blue_pyramid_made`: A rule turned a tile into a blue pyramid on this step.
- `blue_star_picked_up`: The agent picked up a blue star from the grid on this step.
- `blue_pyramid_on_right`: The goal fired on this step (stand so that the blue pyramid is one tile to your right on the map).

## Example tasks

- Stand so that the blue pyramid is one tile to your right on the map.
- Pick up the blue star to turn it into a blue pyramid, then reach the goal.
