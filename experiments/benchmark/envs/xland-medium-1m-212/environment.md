# XLand-MiniGrid ruleset 212

## Environment

A 13 x 13 grid with a grey wall border and a wall cross on row 6 and column 6, so four rooms of 5 x 5 free cells. Each of the four wall arms has one door at a random place along the arm, closed and not locked, of a random color among red, green, blue, purple, yellow and grey. Every initial object lands on its own random floor cell in any room; so does the agent, with a random facing and an empty pocket. All free cells connect through the four doors. The layout, the doors and the start change with every reset; the ruleset does not.

This world's ruleset:
- Goal: a `forward` or `putdown` with a grey star on the cell to the right of the agent.
- Rules, in the order they run after every action:
  1. An agent-side rule: a `forward` or `putdown` with a white key on the cell to the left of the agent turns it into a grey star, also when the action does nothing else.
  2. An agent-next-to rule: a `forward` with a purple ball on any of the four cells beside the agent turns each such purple ball into a white key, also when the move is blocked.
  3. An agent-side rule: a `forward` or `putdown` with a yellow star on the cell to the left of the agent turns it into a grey square, also when the action does nothing else.
  4. An agent-side rule: a `forward` or `putdown` with a grey square on the cell below the agent turns it into a yellow hex, also when the action does nothing else.
  5. A tile-pair rule: a `putdown` that leaves a green ball beside a white pyramid, or a white pyramid beside a green ball, turns the neighbour into a green key and leaves floor where the tile was put; both inputs are used up.
- Initial objects: a purple ball, a pink pyramid, a yellow pyramid, a yellow star, a grey square, a green ball, a white pyramid.

Actions: `forward`, `turn_right` (clockwise), `turn_left`, `pickup`, `putdown`, `toggle`; there is no `done`. The agent sees the 5 x 5 cells in front of it (walls hide nothing), what it carries and which way it faces; it never sees the rules or the goal.

## Objective and episode boundary

The episode ends on the step the goal fires: a `forward` or `putdown` with a grey star on the cell to the right of the agent. The reward is then `1 - 0.9 * (steps taken / 507)`, otherwise 0. The step limit is 507 steps; at step 507 without the goal the episode ends with reward 0. No step follows the goal.

## Proposition semantics

| id | kind | true when |
|---|---|---|
| `grey_star_made` | event | a rule turned a tile into a grey star on this step |
| `white_key_made` | event | a rule turned a tile into a white key on this step |
| `grey_square_made` | event | a rule turned a tile into a grey square on this step |
| `yellow_hex_made` | event | a rule turned a tile into a yellow hex on this step |
| `green_key_made` | event | a rule turned a tile into a green key on this step |
| `green_ball_picked_up` | event | this step's `pickup` took a green ball from the grid into the empty pocket |
| `white_pyramid_picked_up` | event | this step's `pickup` took a white pyramid from the grid into the empty pocket |
| `grey_star_on_right` | event | the goal fired on this step: a `forward` or `putdown` with a grey star on the cell to the right of the agent; the episode ends on this step |

Every proposition is an event: true only on the step its action fires, false on every other step, also while the made tile stays in the world. This file reads "made" as the step a rule changes a tile, so a rule that fires again makes its event true again, and "picked up" as the step the tile leaves the grid for the pocket. Up, right, down and left are sides of the grid (up is the row above), whatever way the agent faces.

## Constraints

- `grey_star_made` cannot become true before `white_key_made`: the rule needs a white key, which only exists once a rule makes it.
- `grey_star_on_right` cannot become true before `grey_star_made`: a grey star only exists once a rule makes it.

## What the agent can and cannot do

- Forward: onto floor, goal tiles and open doors only; a wall, a closed door or any object blocks it and the agent stays, but the step still counts as `forward` for rules and the goal. Turns change only the facing and fire no rule and no goal.
- Pickup: the facing cell must hold a ball, square, pyramid, key, hex or star, and the pocket must be empty; the cell becomes floor. Goal tiles, doors and walls cannot be picked up. The pocket holds one tile.
- Putdown: needs a full pocket and floor in the facing cell; a goal tile, a door, a wall or an object blocks it.
- Toggle: opens a closed door and closes an open one. No door is locked.
- Rules run after every action, in the order listed, each on the grid the one before left, so two rules can fire in one step. A tile a rule uses up comes back only if a rule makes it again, so a rule can make the goal unreachable.

## Example trace

One real episode that reaches the goal: 65 steps, reward 0.8846.

1. 5 steps of turning and moving
2. `forward` (step 6): `white_key_made` true
3. 31 steps of turning and moving
4. `forward` (step 38): `grey_star_made` true
5. 26 steps of turning and moving
6. `forward` (step 65): `grey_star_on_right` true [episode terminated]

## Propositions
- `grey_star_made`: A rule turned a tile into a grey star on this step.
- `white_key_made`: A rule turned a tile into a white key on this step.
- `grey_square_made`: A rule turned a tile into a grey square on this step.
- `yellow_hex_made`: A rule turned a tile into a yellow hex on this step.
- `green_key_made`: A rule turned a tile into a green key on this step.
- `green_ball_picked_up`: The agent picked up a green ball from the grid on this step.
- `white_pyramid_picked_up`: The agent picked up a white pyramid from the grid on this step.
- `grey_star_on_right`: The goal fired on this step (stand so that the grey star is one tile to your right on the map).

## Example tasks

- Stand so that the grey star is one tile to your right on the map.
- Face the purple ball and step forward to turn it into a white key, then reach the goal.
