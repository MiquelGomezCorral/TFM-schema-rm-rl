# XLand-MiniGrid ruleset 197

## Environment

A 13 x 13 grid with a grey wall border and a wall cross on row 6 and column 6, so four rooms of 5 x 5 free cells. Each of the four wall arms has one door at a random place along the arm, closed and not locked, of a random color among red, green, blue, purple, yellow and grey. Every initial object lands on its own random floor cell in any room; so does the agent, with a random facing and an empty pocket. All free cells connect through the four doors. The layout, the doors and the start change with every reset; the ruleset does not.

This world's ruleset:
- Goal: a `forward` or `putdown` with a blue pyramid on the cell to the right of the agent.
- Rules, in the order they run after every action:
  1. A holding rule: a `pickup` while the pocket holds a purple star turns it into a blue pyramid in the pocket. Picking up a purple star fires it at once, so the pocket never shows a purple star.
  2. An agent-side rule: a `forward` or `putdown` with a yellow pyramid on the cell below the agent turns it into a purple star, also when the action does nothing else.
  3. An agent-next-to rule: a `forward` with a brown star on any of the four cells beside the agent turns each such brown star into a red hex, also when the move is blocked.
- Initial objects: a yellow pyramid, a red goal tile, a brown ball, a brown star.

Actions: `forward`, `turn_right` (clockwise), `turn_left`, `pickup`, `putdown`, `toggle`; there is no `done`. The agent sees the 5 x 5 cells in front of it (walls hide nothing), what it carries and which way it faces; it never sees the rules or the goal.

## Objective and episode boundary

The episode ends on the step the goal fires: a `forward` or `putdown` with a blue pyramid on the cell to the right of the agent. The reward is then `1 - 0.9 * (steps taken / 507)`, otherwise 0. The step limit is 507 steps; at step 507 without the goal the episode ends with reward 0. No step follows the goal.

## Proposition semantics

| id | kind | true when |
|---|---|---|
| `blue_pyramid_made` | event | a rule turned a tile into a blue pyramid on this step |
| `purple_star_made` | event | a rule turned a tile into a purple star on this step |
| `red_hex_made` | event | a rule turned a tile into a red hex on this step |
| `purple_star_picked_up` | event | this step's `pickup` took a purple star from the grid into the empty pocket |
| `blue_pyramid_on_right` | event | the goal fired on this step: a `forward` or `putdown` with a blue pyramid on the cell to the right of the agent; the episode ends on this step |

Every proposition is an event: true only on the step its action fires, false on every other step, also while the made tile stays in the world. This file reads "made" as the step a rule changes a tile, so a rule that fires again makes its event true again, and "picked up" as the step the tile leaves the grid for the pocket. Up, right, down and left are sides of the grid (up is the row above), whatever way the agent faces.

## Constraints

- `blue_pyramid_made` cannot become true before `purple_star_made`: the rule needs a purple star, which only exists once a rule makes it.
- `purple_star_picked_up` cannot become true before `purple_star_made`: a purple star only exists once a rule makes it.
- `blue_pyramid_on_right` cannot become true before `blue_pyramid_made`: a blue pyramid only exists once a rule makes it.

## What the agent can and cannot do

- Forward: onto floor, goal tiles and open doors only; a wall, a closed door or any object blocks it and the agent stays, but the step still counts as `forward` for rules and the goal. Turns change only the facing and fire no rule and no goal.
- Pickup: the facing cell must hold a ball, square, pyramid, key, hex or star, and the pocket must be empty; the cell becomes floor. Goal tiles, doors and walls cannot be picked up. The pocket holds one tile.
- Putdown: needs a full pocket and floor in the facing cell; a goal tile, a door, a wall or an object blocks it.
- Toggle: opens a closed door and closes an open one. No door is locked.
- Rules run after every action, in the order listed, each on the grid the one before left, so two rules can fire in one step. A tile a rule uses up comes back only if a rule makes it again, so a rule can make the goal unreachable.
- `purple_star_picked_up` and `blue_pyramid_made` are true on the same step: the holding rule fires on the pickup itself.

## Example trace

One real episode that reaches the goal: 17 steps, reward 0.9698.

1. 9 steps of turning and moving
2. `forward` (step 10): `purple_star_made` true
3. 1 step of turning and moving
4. `pickup` (step 12): `blue_pyramid_made`, `purple_star_picked_up` true
5. 4 steps of turning and moving
6. `putdown` (step 17): `blue_pyramid_on_right` true [episode terminated]

## Propositions
- `blue_pyramid_made`: A rule turned a tile into a blue pyramid on this step.
- `purple_star_made`: A rule turned a tile into a purple star on this step.
- `red_hex_made`: A rule turned a tile into a red hex on this step.
- `purple_star_picked_up`: The agent picked up a purple star from the grid on this step.
- `blue_pyramid_on_right`: The goal fired on this step (stand so that the blue pyramid is one tile to your right on the map).

## Example tasks

- Stand so that the blue pyramid is one tile to your right on the map.
- Stand directly above the yellow pyramid, facing it, and step forward to turn it into a purple star, then reach the goal.
