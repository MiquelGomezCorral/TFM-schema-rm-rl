# Meta-World Shelf-Place: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Metaworld>
- Construction: `gym.make("Meta-World/MT1", env_name="shelf-place-v3")` returns one environment; `seed=0` fixes the layouts [code: `__init__.py:make_mt_envs`].
- Runtime: `metaworld==3.1.1`, `mujoco==3.3.0`, `gymnasium==1.3.0` in `RM_RL_env`. `requirements.txt` does not pin `metaworld` or `mujoco`.
- Reproduction status: ARM-FM used a sparse-reward adaptation whose wrapper is unpublished (`docs/decisions/arm-fm/reproduction-boundary.md`). `environment.md` describes the stock MT1 environment, which returns the dense `v2` reward [code: `__init__.py:_init_each_env`].
- Layout of `obs`, 39 floats [code: `sawyer_xyz_env.py:_get_obs`]: `obs[0:3]` hand position, `obs[3]` finger opening, `obs[4:7]` cube centre, `obs[7:11]` cube quaternion, `obs[18:36]` the previous step's `obs[0:18]`, `obs[36:39]` the target (MT1 shows it). Action: `[dx, dy, dz, gripper]`.
- `info` is empty at reset and filled by every step [run: `explore1.py`]. Read propositions from `obs`, `info` and `env.unwrapped` (`tcp_center`, `_target_pos`).
- Tags: `[code: file:function]` is MetaWorld 3.1.1 source (paths inside `metaworld/`; task files under `envs/`). `[run: script]` is a script in `.git/agent-memory/plans/env-files-upgrade/scripts/` run on the real environment. `mw_common.py` builds it and holds the readings of `environment.md` as code. Run from the repo root: `PYTHONPATH=<scripts dir> MUJOCO_GL=egl conda run -n RM_RL_env python -W ignore <script> <args>`.

## Truth conditions in code

All four are conditions recomputed from the current step; none uses the previous valuation. `d = np.linalg.norm(obs[4:7] - env.unwrapped._target_pos)`; `tcp` = `env.unwrapped.tcp_center`, the midpoint of the two finger sites.

- `near_object`: `bool(info["near_object"])`, that is `np.linalg.norm(obs[4:7] - tcp) <= 0.03`
- `object_grasped`: `bool(info["grasp_success"])`
- `object_near_shelf_goal`: `0.07 < d <= 0.105`
- `object_on_shelf`: `bool(info["success"])`

## Evidence

Environment
- Cube and shelf: [code: `assets/sawyer_xyz/sawyer_shelf_placing.xml`, geom `objGeom`; `assets/objects/assets/shelf.xml`].
- Reset ranges, shelf moved to the target, 0.1 m redraw: [code: `sawyer_shelf_place_v3.py:reset_model`]. Target z in [0.299, 0.301]: [run: `reset_stats.py`].
- 50 pre-drawn layouts, random pick per reset: [code: `__init__.py:_make_tasks`, `RandomTaskSelectWrapper`]. Same `seed`, same layouts: [run: `reset_stats.py`, 800 resets].
- Hand start (0.005, 0.601, 0.195), fingers open: [run: `reset_stats.py`].
- Action effect: [code: `set_xyz_action`; run: `mechanics_check.py`, `obs[3]` 1.00 to 0.28 after 15 steps of +1].

Objective and episode boundary
- Success within 0.07 m of the target point, no shelf-board test: [code: `evaluate_state`, `info["success"]`]. Reward 10 only below 0.05 m: [code: `compute_reward`].
- `terminated` never true, truncation at step 500, `ValueError` after: [code: `sawyer_xyz_env.py:step`, `max_path_length`; run: `mechanics_check.py`].
- No values before the first step (`info` empty): [run: `explore1.py`].

Proposition semantics
- `near_object` (0.03 m from `tcp`), `object_grasped` (pad contact force, `obs[3] > 0`, lifted 0.02 m), `object_on_shelf`: [code: `evaluate_state`, `sawyer_xyz_env.py:touching_object`].
- `object_near_shelf_goal` reading, smallest `d` at reset 0.354 m: [run: `reset_stats.py`]. The environment has no "near the shelf target" flag; the band of 1.5 times the success radius is this file's choice; which threshold ARM-FM used: no source says.
- All four false after the first step: [run: `mechanics_check.py`, 50 of 50 episodes].

Constraints
- `object_near_shelf_goal` and `object_on_shelf` never together: follows from the two `d` ranges, no run.

What the agent can and cannot do
- Hand box, hand target clipped: [code: `set_xyz_action`; run: `mechanics_check.py`, hand stopped at (0.416, 0.832, 0.413) after 120 steps of (+1, +1, +1), short of the box corner; cause not investigated].
- Orientation fixed: [code: `set_xyz_action`].
- z at least 0.229 for success (target z about 0.3, `d <= 0.07`): arithmetic from the code, not run.
- `object_grasped` turned false again in 28 of 30 expert episodes; held while `near_object` was false for 33 steps in 30 expert episodes: [run: `expert_stats.py`].
- `object_on_shelf` has no latch: [code: `evaluate_state`]. The expert lost it in 21 of 30 episodes: [run: `expert_stats.py`].

Example trace
- `SawyerShelfPlaceV3Policy` (`metaworld.policies`), `gym.make(..., seed=0)`, first reset; 500 steps, truncated, first success at step 98: [run: `expert_trace.py`, log `expert_shelf-place-v3_seed0.jsonl`].

This repository has no MetaWorld adapter (`ENVIRONMENT_FAMILIES` holds `minigrid` and `craftium`) [code: `app/src/arm_fm/environments.py`], so there is no labeling API; the conditions above read MetaWorld's own `obs` and `info`.
