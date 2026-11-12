# Meta-World Bin-Picking: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Metaworld>
- Construction: `gym.make("Meta-World/MT1", env_name="bin-picking-v3")` returns one environment; `seed=0` fixes the layouts [code: `__init__.py:make_mt_envs`].
- Runtime: `metaworld==3.1.1`, `mujoco==3.3.0`, `gymnasium==1.3.0` in `RM_RL_env`. `requirements.txt` does not pin `metaworld` or `mujoco`.
- Reproduction status: ARM-FM used a sparse-reward adaptation whose wrapper is unpublished (`docs/decisions/arm-fm/reproduction-boundary.md`). `environment.md` describes the stock MT1 environment, which returns the dense `v2` reward [code: `__init__.py:_init_each_env`].
- Layout of `obs`, 39 floats [code: `sawyer_xyz_env.py:_get_obs`]: `obs[0:3]` hand position, `obs[3]` finger opening, `obs[4:7]` cube centre, `obs[7:11]` cube quaternion, `obs[18:36]` the previous step's `obs[0:18]`, `obs[36:39]` the target (MT1 shows it). Action: `[dx, dy, dz, gripper]`.
- `info` is empty at reset and filled by every step [run: `explore1.py`]. Read propositions from `obs`, `info` and `env.unwrapped` (`_target_pos`).
- Tags: `[code: file:function]` is MetaWorld 3.1.1 source (paths inside `metaworld/`; task files under `envs/`). `[run: script]` is a script in `.git/agent-memory/plans/env-files-upgrade/scripts/` run on the real environment. `mw_common.py` builds it and holds the readings of `environment.md` as code. Run from the repo root: `PYTHONPATH=<scripts dir> MUJOCO_GL=egl conda run -n RM_RL_env python -W ignore <script> <args>`.

## Truth conditions in code

All four are conditions recomputed from the current step; none uses the previous valuation. `d = np.linalg.norm(obs[4:7] - env.unwrapped._target_pos)`.

- `near_object`: `bool(info["near_object"])`, that is `np.linalg.norm(obs[4:7] - obs[0:3]) < 0.04`
- `object_grasped`: `bool(info["grasp_success"])`
- `object_near_target_bin`: `0.05 < d <= 0.075`
- `object_in_target_bin`: `bool(info["success"])`

## Evidence

Environment
- Cube, bin layout (start bin, target bin): [code: `assets/sawyer_xyz/sawyer_bin_picking.xml`, bodies `bin_start`, `bin_goal`; `assets/objects/assets/objA.xml`].
- Target is the `bin_goal` body centre (0.12, 0.7, 0.0) in every reset: [run: `reset_stats.py`].
- Reset, only the cube moves: [code: `sawyer_bin_picking_v3.py:reset_model`]. Cube range x [-0.21, -0.03], y [0.65, 0.75], z 0.03: [run: `reset_stats.py`]. Bounds chosen to start inside the start bin: class docstring.
- 50 pre-drawn layouts, random pick per reset: [code: `__init__.py:_make_tasks`, `RandomTaskSelectWrapper`]. Same `seed`, same layouts: [run: `reset_stats.py`, 800 resets].
- Hand start (0.005, 0.601, 0.195), fingers open: [run: `reset_stats.py`].
- Action effect: [code: `set_xyz_action`; run: `mechanics_check.py`, `obs[3]` 1.00 to 0.28 after 15 steps of +1].

Objective and episode boundary
- Success is a distance test to `bin_goal`, with no inside-the-bin test; reward saturates at 10 below 0.05 m: [code: `evaluate_state`, `info["success"]`; `compute_reward`, `target_to_obj`].
- `terminated` never true, truncation at step 500, `ValueError` after: [code: `sawyer_xyz_env.py:step`, `max_path_length`; run: `mechanics_check.py`].
- No values before the first step (`info` empty): [run: `explore1.py`].

Proposition semantics
- `near_object` is below 0.04 m from the hand body `obs[0:3]`; `object_grasped` is near, lifted 0.02 m, `obs[3] >= 0.43`: [code: `compute_reward`].
- `object_in_target_bin` is `d <= 0.05`: [code: `evaluate_state`].
- `object_near_target_bin` reading, smallest `d` at reset 0.157 m: [run: `reset_stats.py`]. The environment has no "near the bin" flag; the band of 1.5 times the success radius is this file's choice; which threshold ARM-FM used: no source says.
- All four false after the first step: [run: `mechanics_check.py`, 50 of 50 episodes].

Constraints
- `object_grasped` after `near_object`: `grasp_success` is `near_object and lifted and not pinched` [code: `compute_reward`]. 0 steps with `object_grasped` and not `near_object`: [run: `expert_stats.py` and `mechanics_check.py`, 30 expert and 40 random episodes].
- `object_near_target_bin` and `object_in_target_bin` never together: follows from the two `d` ranges, no run.

What the agent can and cannot do
- Hand box, hand target clipped: [code: `set_xyz_action`; run: `mechanics_check.py`, hand stopped at (0.416, 0.832, 0.413) after 120 steps of (+1, +1, +1), short of the box corner; cause not investigated].
- Orientation fixed: [code: `set_xyz_action`].
- `near_object` false while holding, about 0.04 m from the hand body: [run: `expert_trace.py`, seed 0 steps 44 to 63]. It did so in 23 of 30 expert episodes: [run: `expert_stats.py`].
- `object_in_target_bin` has no latch: [code: `evaluate_state`]. The expert never lost it in 30 episodes: [run: `expert_stats.py`].
- Success has no grasp term: [code: `evaluate_state`].

Example trace
- `SawyerBinPickingV3Policy` (`metaworld.policies`), `gym.make(..., seed=0)`, first reset; 500 steps, truncated, first success at step 120: [run: `expert_trace.py`, log `expert_bin-picking-v3_seed0.jsonl`].

This repository has no MetaWorld adapter (`ENVIRONMENT_FAMILIES` holds `minigrid` and `craftium`) [code: `app/src/arm_fm/environments.py`], so there is no labeling API; the conditions above read MetaWorld's own `obs` and `info`.
