# XLand-MiniGrid ruleset 594

## Environment

A 13 x 13 grid with a grey wall border and a wall cross on row 6 and column 6, so four rooms of 5 x 5 free cells. Each of the four wall arms has one door at a random place along the arm, closed and not locked, of a random color among red, green, blue, purple, yellow and grey. Every initial object lands on its own random floor cell in any room; so does the agent, with a random facing and an empty pocket. All free cells connect through the four doors. The layout, the doors and the start change with every reset; the ruleset does not.

This world's ruleset:
- Goal: a `forward` or `putdown` with a pink ball on the cell to the right of the agent.
- Rules, in the order they run after every action:
  1. An agent-side rule: a `forward` or `putdown` with a brown key on the cell above the agent turns it into a pink ball, also when the action does nothing else.
  2. A side tile-pair rule: a `putdown` that leaves a brown hex directly to the left of a brown pyramid (either one put down) turns the other into an orange square and leaves floor where the tile was put; both inputs are used up.
  3. An agent-next-to rule: a `forward` with a grey key on any of the four cells beside the agent turns each such grey key into a purple square, also when the move is blocked.
- Initial objects: a brown key, a brown ball, a yellow ball, a brown pyramid, a brown hex, a grey key.

Actions: `forward`, `turn_right` (clockwise), `turn_left`, `pickup`, `putdown`, `toggle`; there is no `done`. The agent sees the 5 x 5 cells in front of it (walls hide nothing), what it carries and which way it faces; it never sees the rules or the goal.

## Objective and episode boundary

The episode ends on the step the goal fires: a `forward` or `putdown` with a pink ball on the cell to the right of the agent. The reward is then `1 - 0.9 * (steps taken / 507)`, otherwise 0. The step limit is 507 steps; at step 507 without the goal the episode ends with reward 0. No step follows the goal.

## Proposition semantics

| id | kind | true when |
|---|---|---|
| `pink_ball_made` | event | a rule turned a tile into a pink ball on this step |
| `orange_square_made` | event | a rule turned a tile into an orange square on this step |
| `purple_square_made` | event | a rule turned a tile into a purple square on this step |
| `brown_pyramid_picked_up` | event | this step's `pickup` took a brown pyramid from the grid into the empty pocket |
| `brown_hex_picked_up` | event | this step's `pickup` took a brown hex from the grid into the empty pocket |
| `pink_ball_on_right` | event | the goal fired on this step: a `forward` or `putdown` with a pink ball on the cell to the right of the agent; the episode ends on this step |

Every proposition is an event: true only on the step its action fires, false on every other step, also while the made tile stays in the world. This file reads "made" as the step a rule changes a tile, so a rule that fires again makes its event true again, and "picked up" as the step the tile leaves the grid for the pocket. Up, right, down and left are sides of the grid (up is the row above), whatever way the agent faces.

## Constraints

- `pink_ball_on_right` cannot become true before `pink_ball_made`: a pink ball only exists once a rule makes it.

## What the agent can and cannot do

- Forward: onto floor, goal tiles and open doors only; a wall, a closed door or any object blocks it and the agent stays, but the step still counts as `forward` for rules and the goal. Turns change only the facing and fire no rule and no goal.
- Pickup: the facing cell must hold a ball, square, pyramid, key, hex or star, and the pocket must be empty; the cell becomes floor. Goal tiles, doors and walls cannot be picked up. The pocket holds one tile.
- Putdown: needs a full pocket and floor in the facing cell; a goal tile, a door, a wall or an object blocks it.
- Toggle: opens a closed door and closes an open one. No door is locked.
- Rules run after every action, in the order listed, each on the grid the one before left, so two rules can fire in one step. A tile a rule uses up comes back only if a rule makes it again, so a rule can make the goal unreachable.

## Example trace

One real episode that reaches the goal: 11 steps, reward 0.9805.

1. 5 steps of turning and moving
2. `forward` (step 6): `pink_ball_made` true
3. 4 steps of turning and moving
4. `forward` (step 11): `pink_ball_on_right` true [episode terminated]

## Propositions
- `pink_ball_made`: A rule turned a tile into a pink ball on this step.
- `orange_square_made`: A rule turned a tile into an orange square on this step.
- `purple_square_made`: A rule turned a tile into a purple square on this step.
- `brown_pyramid_picked_up`: The agent picked up a brown pyramid from the grid on this step.
- `brown_hex_picked_up`: The agent picked up a brown hex from the grid on this step.
- `pink_ball_on_right`: The goal fired on this step (stand so that the pink ball is one tile to your right on the map).

## Example tasks

- Stand so that the pink ball is one tile to your right on the map.
- Stand directly below the brown key, facing it, and step forward to turn it into a pink ball, then reach the goal.
