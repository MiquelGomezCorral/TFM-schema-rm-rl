# Meta-World Stick-Push: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Metaworld>
- Construction: `gym.make("Meta-World/MT1", env_name="stick-push-v3")` returns one environment; `seed=0` fixes the layouts [code: `__init__.py:make_mt_envs`].
- Runtime: `metaworld==3.1.1`, `mujoco==3.3.0`, `gymnasium==1.3.0` in `RM_RL_env`. `requirements.txt` does not pin `metaworld` or `mujoco`.
- Reproduction status: ARM-FM used a sparse-reward adaptation whose wrapper is unpublished (`docs/decisions/arm-fm/reproduction-boundary.md`). `environment.md` describes the stock MT1 environment, which returns the dense `v2` reward [code: `__init__.py:_init_each_env`].
- Layout of `obs`, 39 floats [code: `sawyer_xyz_env.py:_get_obs`, `_get_pos_objects`]: `obs[0:3]` hand position, `obs[3]` finger opening, `obs[4:7]` stick centre, `obs[7:11]` stick quaternion, `obs[11:14]` thermos position (the `insertion` site plus 0.09 m in y), `obs[18:36]` the previous step's `obs[0:18]`, `obs[36:39]` the target (MT1 shows it). Action: `[dx, dy, dz, gripper]`.
- `info` is empty at reset and filled by every step [run: `explore1.py`]. Read propositions from `obs`, `info` and `env.unwrapped` (`tcp_center`, `_target_pos`).
- Tags: `[code: file:function]` is MetaWorld 3.1.1 source (paths inside `metaworld/`; task files under `envs/`). `[run: script]` is a script in `.git/agent-memory/plans/env-files-upgrade/scripts/` run on the real environment. `mw_common.py` builds it and holds the readings of `environment.md` as code. Run from the repo root: `PYTHONPATH=<scripts dir> MUJOCO_GL=egl conda run -n RM_RL_env python -W ignore <script> <args>`.

## Truth conditions in code

All four are conditions recomputed from the current step; none uses the previous valuation. `d = np.linalg.norm(obs[11:14] - env.unwrapped._target_pos)`; `tcp` = `env.unwrapped.tcp_center`, the midpoint of the two finger sites.

- `near_stick`: `bool(info["near_object"])`, that is `np.linalg.norm(obs[4:7] + np.array([0.015, 0, 0]) - tcp) <= 0.03`
- `stick_grasped`: `bool(info["grasp_success"])`
- `pushed_object_near_goal`: `0.12 < d <= 0.18`
- `push_complete`: `bool(info["success"])`, that is `stick_grasped and d <= 0.12`

## Evidence

Environment
- Stick, thermos: [code: `assets/sawyer_xyz/sawyer_stick_obj.xml`, `assets/objects/assets/stick.xml`, `thermos.xml`].
- Reset, stick range: [code: `sawyer_stick_push_v3.py:reset_model`]. Thermos fixed at `obs[11:14]` (0.2, 0.6, 0.132); target ranges; thermos 0.199 to 0.207 m from the target: [run: `reset_stats.py`].
- 50 pre-drawn layouts, random pick per reset: [code: `__init__.py:_make_tasks`, `RandomTaskSelectWrapper`]. Same `seed`, same layouts: [run: `reset_stats.py`, 800 resets].
- Hand start (0.005, 0.601, 0.195), fingers open: [run: `reset_stats.py`].
- Action effect: [code: `set_xyz_action`; run: `mechanics_check.py`, `obs[3]` 1.00 to 0.28 after 15 steps of +1].

Objective and episode boundary
- Success is `grasp_success` and thermos within 0.12 m, in one step: [code: `evaluate_state`, `info["success"]`]. Reward 10 needs the same pair: [code: `compute_reward`].
- `terminated` never true, truncation at step 500, `ValueError` after: [code: `sawyer_xyz_env.py:step`, `max_path_length`; run: `mechanics_check.py`].
- No values before the first step (`info` empty): [run: `explore1.py`].

Proposition semantics
- `near_stick` (0.03 m from `tcp` to `obs[4:7]` + 0.015 in x), `stick_grasped` (pad contact force, `obs[3] > 0`, lifted 0.01 m, stick geom `objGeom`), `push_complete`: [code: `evaluate_state`, `compute_reward`, `sawyer_xyz_env.py:touching_object`].
- `pushed_object_near_goal` reading, smallest `d` at reset 0.199 m: [run: `reset_stats.py`]. A first try with a band of 2 times the radius was true at reset, so the band is 1.5 times. The environment has no "near the goal" flag; which threshold ARM-FM used: no source says.
- All four false after the first step: [run: `mechanics_check.py`, 50 of 50 episodes].

Constraints
- `push_complete` after `stick_grasped`: success is `grasp_success and (d <= 0.12)` [code: `evaluate_state`]. 0 steps with `push_complete` and not `stick_grasped`: [run: `expert_stats.py` and `mechanics_check.py`, 30 expert and 40 random episodes].
- `pushed_object_near_goal` and `push_complete` never together: follows from the two `d` ranges, no run.

What the agent can and cannot do
- Hand box, hand target clipped: [code: `set_xyz_action`; run: `mechanics_check.py`, hand stopped at (0.416, 0.832, 0.413) after 120 steps of (+1, +1, +1), short of the box corner; cause not investigated].
- Orientation fixed: [code: `set_xyz_action`].
- No stick-touches-thermos check, only thermos position and stick held: [code: `evaluate_state`].
- `push_complete` lost after releasing the stick in 30 of 30 expert episodes: [run: `expert_stats.py`; `expert_trace.py`, seed 0 step 151].
- `near_stick` with the stick not lifted or not held: [code: `evaluate_state`].

Example trace
- `SawyerStickPushV3Policy` (`metaworld.policies`), `gym.make(..., seed=0)`, first reset; 500 steps, truncated, first success at step 77: [run: `expert_trace.py`, log `expert_stick-push-v3_seed0.jsonl`].

This repository has no MetaWorld adapter (`ENVIRONMENT_FAMILIES` holds `minigrid` and `craftium`) [code: `app/src/arm_fm/environments.py`], so there is no labeling API; the conditions above read MetaWorld's own `obs` and `info`.
