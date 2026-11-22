# XLand-MiniGrid ruleset Figure 10 A: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Source: `app/src/arm_fm/custom_envs/xland_env.py:XLandEnv`, a Gymnasium wrapper over the jitted `xminigrid` environment `XLand-MiniGrid-R4-13x13` <https://github.com/dunnolab/xland-minigrid>. Importing `src.arm_fm` registers the id; the wrapper module (and JAX, on CPU) loads only when an env is made.
- Gymnasium ID: `XLand-R4-13x13-v0`, keyword argument `ruleset="figure10-a"`, read from `app/src/arm_fm/custom_envs/xland_rulesets.json`: rebuilt by hand from the ARM-FM paper's Figure 10, whose rules are only partly visible.
- Runtime: `xminigrid==0.9.3` (with JAX), `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `reset(seed=s)` draws the layout from `jax.random.key(s)`, xminigrid's own layout for this ruleset; without a seed it draws one from the env's own random stream.
- Observation: `(5, 5, 5)` uint8: xminigrid's 5 x 5 view (tile id, color id per cell), then the pocket's tile id, its color id and the facing on every cell.
- `[code: file:function]` is under `xminigrid/` unless named otherwise. `[run: render]` is `experiments/benchmark/scripts/render_xland.py`, which wrote both files.

## Truth conditions in code

All read what the last step did; none reads the grid.

| id | expression |
|---|---|
| `orange_star_made` | `"orange star" in env.products_made` |
| `blue_key_picked_up` | `env.picked_up == "blue key"` |
| `purple_ball_picked_up` | `env.picked_up == "purple ball"` |
| `orange_star_held` | `env.goal_reached` |

## Evidence

- Environment, layout, doors and start: [code: `envs/xland.py:generate_four_rooms`, `XLandMiniGrid._generate_problem`].
- Environment, the rules and their actions: [code: `rules.py:TileNearRule`; `rules.py:check_rule` runs them in order].
- Objective, goal and reward: [code: `goals.py:AgentHoldGoal`; `environment.py:Environment.step`; `envs/xland.py:XLandMiniGrid.default_params` sets `max_steps` to `3 * 13 * 13`].
- Proposition semantics: [code: `xland_env.py:XLandEnv.step`: `products_made` from each rule's own replay in `_step`, `picked_up` from `pick_up`'s condition, `goal_reached` from the zero discount of a goal step].
- Constraints: only rules create tiles; actions move a tile between grid and pocket or open and close doors [code: `core/actions.py`].
- What the agent can and cannot do: [code: `core/actions.py:move_forward`, `pick_up`, `put_down`, `toggle`; `core/constants.py:WALKABLE`, `PICKABLE`, `FREE_TO_PUT_DOWN`; `core/grid.py:check_can_put`].
- Example trace: [run: render, reset seed 1, `xland_env.py:scripted_policy`]: 23 steps, reward 0.9592.
- Reference labeling: `xland_env.py:reference_labels` computes the expressions above; the benchmark's labeling check compares a bundle's labeling with it.

## Labeling API

- `env.last_action`: name of the last action (`"forward"`, `"turn_right"`, `"turn_left"`, `"pickup"`, `"putdown"`, `"toggle"`), `None` after reset.
- `env.products_made`: tuple of tile names (`"<color> <kind>"`, for example `"blue pyramid"`), one per rule that fired on the last step, in rule order; empty when none fired.
- `env.picked_up`: name of the tile the last step's `pickup` took from the grid, else `None`. A holding rule may already have changed it in the pocket.
- `env.goal_reached`: `True` on the step the ruleset's goal fired (that step ends the episode), else `False`.
- `env.pocket`: name of the carried tile, or `None`.
- `env.agent_pos`: `(row, column)` of the agent. `env.agent_dir`: its facing, `0` up, `1` right, `2` down, `3` left.
- `env.tiles`: tuple of rows, each a tuple of cell names (`"black floor"`, `"grey wall"`, `"red door_closed"`, `"blue pyramid"`, ...); read a cell as `env.tiles[row][column]`.

Every proposition of this ruleset is an event of the last step: read it from `env.products_made`, `env.picked_up` or `env.goal_reached`, not from the grid.
