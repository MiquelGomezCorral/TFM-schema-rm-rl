# XLand-MiniGrid Medium-1M: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/corl-team/xland-minigrid>
- Benchmark data: <https://huggingface.co/datasets/Howuhh/xland_minigrid>, file `medium_1m_v3`; loaded with `xminigrid.load_benchmark("medium-1m")` [code: benchmarks.py:NAME2HFFILENAME]. `XLAND_MINIGRID_DATA` sets the folder holding the file.
- Rulesets used by ARM-FM: `benchmark.get_ruleset(i)` for `i` in 0 to 999. Which data revision the paper used: no source says.
- Carrier: `xminigrid.make("XLand-MiniGrid-R4-13x13")`.
- Runtime: `xminigrid==0.9.3`, `jax==0.11.2`, `flax==0.12.9` as installed in `RM_RL_env` (CPU, `JAX_PLATFORMS=cpu`); `xminigrid` is not pinned in `requirements.txt`.
- State: `ts.state.grid[y, x]` is `(tile, color)` ints, `ts.state.agent.position` is `(y, x)`, `.agent.direction` and `.agent.pocket` as `(tile, color)`. Actions: `0` forward, `1` turn clockwise, `2` turn counterclockwise, `3` pickup, `4` putdown, `5` toggle [code: core/actions.py:take_action]. Directions: `0` up (row - 1), `1` right (column + 1), `2` down, `3` left [code: core/constants.py:DIRECTIONS].
- Tags: `[code: file:function]` is xminigrid 0.9.3 source (`xminigrid/...`). `[run: script]` is a script in `.git/agent-memory/plans/env-files-upgrade/scripts/` run on the real environment: `xland_common.py` (builds it), `xland_checks.py`, `xland_benchmark_stats.py`, `xland_solve.py`, `xland_goal_gate.py`, each with a `.log` where one exists.

## Truth conditions in code

`prev = env.episode_memory["previous_valuation"]`. Let `a`, `b`, `c` be the bound `(tile, color)` pairs, `(y, x)` = `agent.position`, `side(Dir)` = `(-1, 0), (0, 1), (1, 0), (0, -1)` for up, right, down, left, and `cell(p)` = `tuple(grid[p])` (guard the border). Not run as labeling code.

Goal and rule names of `environment.md` in library terms: "the agent holds `a`" is `AgentHold`; "the agent is next to `a`" is `AgentNear`; "the agent stands on `a`" is `AgentOnTile`; "`a` is next to `b`" is `TileNear`; "`b` is on a given side of `a`" is `TileNear<Dir>` (`TileNearUp/Right/Down/Left`); "`a` is on a given side of the agent" is `AgentNear<Dir>` (`AgentNearUp/Right/Down/Left`). Rules use the same names: holding rule `AgentHold(a -> c)`, agent-next-to rule `AgentNear(a -> c)`, agent-side rule `AgentNear<Dir>(a -> c)`, tile-pair rule `TileNear(a, b -> c)` and its side variant `TileNear<Dir>`. Ruleset 197 of the example trace: goal `AgentNearRight(blue pyramid)`; rules `AgentHold(purple star -> blue pyramid)`, `AgentNearDown(yellow pyramid -> purple star)`, `AgentNear(brown star -> red hex)`.

- `required_object_held`: `tuple(agent.pocket) == a`
- `required_object_reached`: `any(cell((y + dy, x + dx)) == a for dy, dx in [(0, 0), (-1, 0), (0, 1), (1, 0), (0, -1)])`
- `required_relation_satisfied`: `TileNear(a, b)` is "some cell holding `a` has an orthogonal neighbour holding `b`"; `TileNear<Dir>` is "`b` is at `side(Dir)` from some cell holding `a`"; `AgentNear<Dir>(a)` is `cell((y, x) + side(Dir)) == a`.
- `intermediate_object_created`: `prev["intermediate_object_created"] or tuple(agent.pocket) == c or any(cell(p) == c for p in all cells)`
- `goal_satisfied`: the goal predicate of the ruleset on `grid`, `agent.position` and `agent.pocket`, ignoring the action; a reference implementation is `state_goal` in `xland_goal_gate.py`.

## Evidence

Source and layout
- Ruleset is data fixed per task: [code: envs/xland.py:XLandMiniGrid._generate_problem].
- Layout (grid, wall cross, four closed unlocked doors, objects on distinct floor cells, agent random): [code: envs/xland.py:generate_four_rooms, _generate_problem; run: `xland_checks.py`, 300 resets of rulesets 0 to 49]. The same run: 4 closed doors, no locked or open door, exact wall cross, objects equal `init_tiles`, all cells connected through the doors, agent in all four rooms and 4 directions.
- Carrier choice: the paper does not report its grid; `XLand-MiniGrid-R4-13x13` is the library's documented default.
- Ruleset contents (goal kinds `AgentHold` 101, `AgentNear` 94, `TileNear` 103, `TileNearUp/Right/Down/Left` 89/90/101/77, `AgentNearUp/Right/Down/Left` 108/91/76/70; 0 to 9 rules, 9 rulesets with none; 3 to 15 initial objects, mean 7.1; 34 of 4,558 floor products, 193 of 1,460 goal-tile slots initial, 1,267 not): [run: `xland_benchmark_stats.py`]. Rule products also include goal tiles (193).
- Actions, no `done`: [code: core/actions.py:take_action]. Observation 5x5, no occlusion, no goal or rules: [code: environment.py:Environment.reset, core/observation.py:transparent_field_of_view].

Objective and episode boundary
- Termination after action and rules, reward `1 - 0.9 * step_num / max_steps`: [code: environment.py:Environment.step; run: `xland_checks.py`, reward at step 100].
- Step limit 507: [code: envs/xland.py:XLandMiniGrid.default_params; run: `xland_checks.py`, `max_steps` 507 in 300 of 300 resets].
- Goal action gates: [code: core/goals.py:AgentHoldGoal, AgentNearGoal, TileNearGoal, AgentNearUpGoal; run: `xland_checks.py`, each gate in a minimal scenario].
- Solvability of the 1,000 rulesets: no sweep was run. The paper says a distractor can make a sampled task unsolvable.

Proposition semantics
- Grid sides, not agent-relative: [code: core/goals.py:AgentNearUpGoal].
- `reached` against `relation`: `environment.md` chose the split so that each goal family has one proposition. Whether the paper's labeling used this split: no source says.
- `intermediate_object_created` is read as a latch because an event would need the previous grid, and only the previous valuation is remembered. True from step 0 for 243 of 4,558 rules: [run: `xland_benchmark_stats.py`].
- `goal_satisfied` ignores the action because the labels are computed from the state alone. It can be true without ending: [run: `xland_checks.py`]. Random policy, 400 episodes: 12 ended, 16 steps had the predicate true (4 without an ending), 0 endings had it false, 1 of 400 resets started true [run: `xland_goal_gate.py`, log `xland_goal_gate.log`]. Few events, so it only supports "no counterexample"; the implication is from code.

Constraints
- `goal_satisfied` after `intermediate_object_created` for a produced goal tile: [code: envs/xland.py:_generate_problem; core/rules.py:check_rule]. Count 1,267 of 1,460: [run: `xland_benchmark_stats.py`].
- `intermediate_object_created` never false once true: by the latch expression, no run.

What the agent can and cannot do
- Forward and blocking: [code: core/actions.py:move_forward; core/constants.py:WALKABLE; run: `xland_checks.py`].
- Pickup: [code: core/actions.py:pick_up; run: `xland_checks.py`]. Putdown: [code: core/actions.py:put_down; run: `xland_checks.py`]. Toggle: [code: core/actions.py:toggle; run: `xland_checks.py`].
- A rule can make the goal unreachable, since nothing recreates a consumed tile except another rule (the paper's distractor): follows from the rule kinds below, not run.
- Rule order and chaining: [code: core/rules.py:check_rule; run: `xland_checks.py`]. Rule kinds on fixed actions: [code: core/rules.py; run: `xland_checks.py`, every kind on all six actions].
- `xland_checks.py` also ran 89 minimal scenarios (movement, pickup, putdown, toggle, every rule kind on all six actions, rule order, goal gates, reward formula, truncation); all pass.

Example trace
- Ruleset 197, reset key `jax.random.key(0)`, breadth-first search over `env.step` with privileged state access, 15 steps, reward 0.9734, 491 states searched: [run: `xland_solve.py 197 0`, log `xland_trace_197_seed0.jsonl`].
- Whether ruleset 197 is the paper's "seed 197": no source says.

This repository has no XLand adapter or labeling code (`ENVIRONMENT_FAMILIES` holds `minigrid` and `craftium`) [code: app/src/arm_fm/environments.py:ENVIRONMENT_FAMILIES], so there is no labeling API; the conditions above read the JAX state, not a MiniGrid `env` object.
