# XLand-MiniGrid ruleset Figure 10 A

## Environment

A 13 x 13 grid with a grey wall border and a wall cross on row 6 and column 6, so four rooms of 5 x 5 free cells. Each of the four wall arms has one door at a random place along the arm, closed and not locked, of a random color among red, green, blue, purple, yellow and grey. Every initial object lands on its own random floor cell in any room; so does the agent, with a random facing and an empty pocket. All free cells connect through the four doors. The layout, the doors and the start change with every reset; the ruleset does not.

This world's ruleset:
- Goal: a `pickup` while the pocket holds an orange star (also when the pickup takes nothing).
- Rules, in the order they run after every action:
  1. A tile-pair rule: a `putdown` that leaves a blue key beside a purple ball, or a purple ball beside a blue key, turns the neighbour into an orange star and leaves floor where the tile was put; both inputs are used up.
- Initial objects: a blue key, a purple ball, an orange pyramid.

Actions: `forward`, `turn_right` (clockwise), `turn_left`, `pickup`, `putdown`, `toggle`; there is no `done`. The agent sees the 5 x 5 cells in front of it (walls hide nothing), what it carries and which way it faces; it never sees the rules or the goal.

## Objective and episode boundary

The episode ends on the step the goal fires: a `pickup` while the pocket holds an orange star (also when the pickup takes nothing). The reward is then `1 - 0.9 * (steps taken / 507)`, otherwise 0. The step limit is 507 steps; at step 507 without the goal the episode ends with reward 0. No step follows the goal.

## Proposition semantics

| id | kind | true when |
|---|---|---|
| `orange_star_made` | event | a rule turned a tile into an orange star on this step |
| `blue_key_picked_up` | event | this step's `pickup` took a blue key from the grid into the empty pocket |
| `purple_ball_picked_up` | event | this step's `pickup` took a purple ball from the grid into the empty pocket |
| `orange_star_held` | event | the goal fired on this step: a `pickup` while the pocket holds an orange star (also when the pickup takes nothing); the episode ends on this step |

Every proposition is an event: true only on the step its action fires, false on every other step, also while the made tile stays in the world. This file reads "made" as the step a rule changes a tile, so a rule that fires again makes its event true again, and "picked up" as the step the tile leaves the grid for the pocket. Up, right, down and left are sides of the grid (up is the row above), whatever way the agent faces.

## Constraints

- `orange_star_held` cannot become true before `orange_star_made`: an orange star only exists once a rule makes it.

## What the agent can and cannot do

- Forward: onto floor, goal tiles and open doors only; a wall, a closed door or any object blocks it and the agent stays, but the step still counts as `forward` for rules and the goal. Turns change only the facing and fire no rule and no goal.
- Pickup: the facing cell must hold a ball, square, pyramid, key, hex or star, and the pocket must be empty; the cell becomes floor. Goal tiles, doors and walls cannot be picked up. The pocket holds one tile.
- Putdown: needs a full pocket and floor in the facing cell; a goal tile, a door, a wall or an object blocks it.
- Toggle: opens a closed door and closes an open one. No door is locked.
- Rules run after every action, in the order listed, each on the grid the one before left, so two rules can fire in one step. A tile a rule uses up comes back only if a rule makes it again, so a rule can make the goal unreachable.

## Example trace

One real episode that reaches the goal: 23 steps, reward 0.9592.

1. 14 steps of turning and moving
2. `pickup` (step 15): `blue_key_picked_up` true
3. 4 steps of turning and moving
4. `putdown` (step 20): `orange_star_made` true
5. 2 steps of turning and moving
6. `pickup` (step 23): `orange_star_held` true [episode terminated]

## Propositions
- `orange_star_made`: A rule turned a tile into an orange star on this step.
- `blue_key_picked_up`: The agent picked up a blue key from the grid on this step.
- `purple_ball_picked_up`: The agent picked up a purple ball from the grid on this step.
- `orange_star_held`: The goal fired on this step (pick up the orange star).

## Example tasks

- Pick up the orange star.
- Pick up the blue key and put it down next to the purple ball to make an orange star, then reach the goal.
