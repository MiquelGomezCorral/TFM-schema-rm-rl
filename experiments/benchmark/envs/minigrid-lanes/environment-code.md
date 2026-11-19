# MiniGrid Lanes: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Source: `app/src/arm_fm/forcing_envs.py:LanesEnv`, a MiniGrid environment written for this project on the Farama base <https://github.com/Farama-Foundation/Minigrid>. Importing `src.arm_fm.environments` registers it.
- Gymnasium ID: `MiniGrid-Lanes-v0`. Keyword argument: `max_steps` (int, default 300).
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `reset(seed=s)` seeds the whole schedule. Without a seed it draws one from the environment's own random stream. Either way `reset` returns the seed it used as `info["event_seed"]`, beside `info["events"]`.
- The observation is the whole grid: `gen_obs` returns `{"image": grid.encode() with the agent written in, "direction", "mission"}`, as MiniGrid's `FullyObsWrapper` does, so the standard `ImgObsWrapper` and `MiniGridCNN` work unchanged on an 11 x 11 x 3 image.
- `[code: file:function]` is `forcing_envs.py` unless a MiniGrid path is given. `[run: check]` is `experiments/benchmark/scripts/check_forcing.py` on the real environment, reset seeds 1 to 20.

## Truth conditions in code

All four read the state after the step. `events_this_step` is reset at the start of every step.

| id | expression |
|---|---|
| `top_breach` | `"top_breach" in env.events_this_step` |
| `side_breach` | `"side_breach" in env.events_this_step` |
| `plant_trampled` | `"plant_trampled" in env.events_this_step` |
| `zombie_killed` | `"zombie_killed" in env.events_this_step` |

## Evidence

- Environment, layout: 9 x 9 field, three lanes on grid rows 1, 5, 9, agent at (5, 5) facing left, the grid empty at reset [code: `LANES_SIZE`, `LANE_ROWS`, `LANES_START`, `_gen_grid`; run: check, layout, 20/20].
- Environment, whole-grid observation: the agent, its facing and each zombie show in the image [code: `gen_obs`; run: check, observation, 20/20]. A zombie on the agent's own cell is hidden by the agent.
- Environment, entry on a random lane, rhythm and the walk: a zombie nobody stops gets through exactly 27 steps after it entered [code: `ZOMBIE_PERIOD`, `_advance_zombies`; run: check, idle walk, 20/20 episodes; the earliest breach in them is step 31]. Zombies enter only on the lane rows, never two on one step, and breaches + zombies left on the grid = zombies entered [run: check, idle, 20/20 each].
- Environment, no entry while the entry cell is occupied [code: `_spawn_zombie`].
- Environment, the spawn chance rises 4% to 17% [code: `SPAWN_CHANCE`, `_plan_events`; run: check, idle spawns, mean 5.8 entries in steps 1 to 100 against 13.3 in steps 201 to 300].
- Environment, plants: off the lanes in every step of 20 random episodes (6000 steps), at most 3 alive, a step onto one kills it and removes exactly that plant (17 tramples) [code: `_sprout_plant`, `_land`, `MAX_PLANTS`; run: check, random walks].
- Environment, a kill needs a move of the agent onto the zombie (24 kills in the random walks); a zombie that stepped onto the agent's cell is not killed [code: `step` runs `_land` only when the position changed, before `_advance_zombies`; run: check, idle, the agent waits on the middle lane and every one of its zombies still gets through, 20/20]. Kills + breaches + zombies left = zombies entered [run: check, random walks, 20/20].
- Environment, the agent cannot hold, drop or toggle anything [code: `Creature.can_pickup` is False; MiniGrid `WorldObj.toggle` returns False for a ball].
- Objective, step limit 300, no other end [code: `MAX_STEPS`; `step` returns MiniGrid's truncation only].
- Objective, reward 1 per kill [code: `step`]. `success` is true exactly while no top breach happened [code: `success`; run: check, env flag, 20 of 20 idle episodes failed and the guard's flag equals its held top lane in 20/20].
- Constraints, no breach before step 28 [code: the walk takes 27 steps after the earliest entry at step 1; run: check, idle, first breach at step 31]. `plant_trampled` and `zombie_killed` never together [code: `_land` handles one cell per step; run: check, random walks, 6000/6000 steps].
- Same seed and same actions give the same episode [code: `reset`, `_plan_events`; run: check, replay, 20/20].
- Example trace: seed 1, scripted guard `scripted_policy` (see `forcing_envs.py`): 300 steps, 21 kills, side breaches at steps 238, 256, 275 and 293, no top breach [run: check; the guard keeps the top lane on 19 of 20 seeds, 37 of 40 over seeds 1 to 40].

## Labeling API

- `env.events_this_step`: list of strings for the step that just ended, empty when nothing happened. It can hold `"top_breach"`, `"side_breach"`, `"plant_trampled"` and `"zombie_killed"`, a kind can appear twice when two zombies get through side lanes on the same step. Event propositions come from it.
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- Object attributes: `type` (`wall` or `ball`) and `color` (`red` for a zombie, `green` for a plant).
- `env.width`, `env.height`: grid size (11 x 11).

Object classes cannot be imported. Guard empty cells with `cell is not None` before reading an attribute.
