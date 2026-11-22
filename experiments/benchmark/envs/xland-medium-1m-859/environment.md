# XLand-MiniGrid ruleset 859

## Environment

A 13 x 13 grid with a grey wall border and a wall cross on row 6 and column 6, so four rooms of 5 x 5 free cells. Each of the four wall arms has one door at a random place along the arm, closed and not locked, of a random color among red, green, blue, purple, yellow and grey. Every initial object lands on its own random floor cell in any room; so does the agent, with a random facing and an empty pocket. All free cells connect through the four doors. The layout, the doors and the start change with every reset; the ruleset does not.

This world's ruleset:
- Goal: a `forward` with a blue ball on any of the four cells beside the agent.
- Rules, in the order they run after every action:
  1. An agent-side rule: a `forward` or `putdown` with a brown pyramid on the cell below the agent turns it into a blue ball, also when the action does nothing else.
  2. An agent-side rule: a `forward` or `putdown` with a green pyramid on the cell below the agent turns it into a brown pyramid, also when the action does nothing else.
  3. An agent-side rule: a `forward` or `putdown` with a brown key on the cell above the agent turns it into a yellow hex, also when the action does nothing else.
- Initial objects: a green pyramid, a brown star, a pink goal tile, a brown key.

Actions: `forward`, `turn_right` (clockwise), `turn_left`, `pickup`, `putdown`, `toggle`; there is no `done`. The agent sees the 5 x 5 cells in front of it (walls hide nothing), what it carries and which way it faces; it never sees the rules or the goal.

## Objective and episode boundary

The episode ends on the step the goal fires: a `forward` with a blue ball on any of the four cells beside the agent. The reward is then `1 - 0.9 * (steps taken / 507)`, otherwise 0. The step limit is 507 steps; at step 507 without the goal the episode ends with reward 0. No step follows the goal.

## Proposition semantics

| id | kind | true when |
|---|---|---|
| `blue_ball_made` | event | a rule turned a tile into a blue ball on this step |
| `brown_pyramid_made` | event | a rule turned a tile into a brown pyramid on this step |
| `yellow_hex_made` | event | a rule turned a tile into a yellow hex on this step |
| `blue_ball_reached` | event | the goal fired on this step: a `forward` with a blue ball on any of the four cells beside the agent; the episode ends on this step |

Every proposition is an event: true only on the step its action fires, false on every other step, also while the made tile stays in the world. This file reads "made" as the step a rule changes a tile, so a rule that fires again makes its event true again, and "picked up" as the step the tile leaves the grid for the pocket. Up, right, down and left are sides of the grid (up is the row above), whatever way the agent faces.

## Constraints

- `blue_ball_made` cannot become true before `brown_pyramid_made`: the rule needs a brown pyramid, which only exists once a rule makes it.
- `blue_ball_reached` cannot become true before `blue_ball_made`: a blue ball only exists once a rule makes it.

## What the agent can and cannot do

- Forward: onto floor, goal tiles and open doors only; a wall, a closed door or any object blocks it and the agent stays, but the step still counts as `forward` for rules and the goal. Turns change only the facing and fire no rule and no goal.
- Pickup: the facing cell must hold a ball, square, pyramid, key, hex or star, and the pocket must be empty; the cell becomes floor. Goal tiles, doors and walls cannot be picked up. The pocket holds one tile.
- Putdown: needs a full pocket and floor in the facing cell; a goal tile, a door, a wall or an object blocks it.
- Toggle: opens a closed door and closes an open one. No door is locked.
- Rules run after every action, in the order listed, each on the grid the one before left, so two rules can fire in one step. A tile a rule uses up comes back only if a rule makes it again, so a rule can make the goal unreachable.
- A `forward` that makes a blue ball beside the agent fires the goal on the same step, so `blue_ball_made` and `blue_ball_reached` come together then.

## Example trace

One real episode that reaches the goal: 10 steps, reward 0.9822.

1. 7 steps of turning and moving
2. `forward` (step 8): `brown_pyramid_made` true
3. 1 step of turning and moving
4. `forward` (step 10): `blue_ball_made`, `blue_ball_reached` true [episode terminated]

## Propositions
- `blue_ball_made`: A rule turned a tile into a blue ball on this step.
- `brown_pyramid_made`: A rule turned a tile into a brown pyramid on this step.
- `yellow_hex_made`: A rule turned a tile into a yellow hex on this step.
- `blue_ball_reached`: The goal fired on this step (step forward with the blue ball next to you).

## Example tasks

- Step forward with the blue ball next to you.
- Stand directly above the green pyramid, facing it, and step forward to turn it into a brown pyramid, then reach the goal.
