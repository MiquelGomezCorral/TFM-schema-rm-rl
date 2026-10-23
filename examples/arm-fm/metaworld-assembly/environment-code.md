# Meta-World Assembly: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Metaworld>
- Construction: `gym.make("Meta-World/MT1", env_name="assembly-v3")` returns one environment; `seed=0` fixes the layouts [code: `__init__.py:make_mt_envs`].
- Runtime: `metaworld==3.1.1`, `mujoco==3.3.0`, `gymnasium==1.3.0` in `RM_RL_env`. `requirements.txt` does not pin `metaworld` or `mujoco`.
- Reproduction status: ARM-FM used a sparse-reward adaptation whose wrapper is unpublished (`docs/decisions/arm-fm/reproduction-boundary.md`). `environment.md` describes the stock MT1 environment, which returns the dense `v2` reward [code: `__init__.py:_init_each_env`].
- Layout of `obs`, 39 floats [code: `sawyer_xyz_env.py:_get_obs`]: `obs[0:3]` hand position, `obs[3]` finger opening, `obs[4:7]` handle end, `obs[7:11]` nut quaternion, `obs[18:36]` the previous step's `obs[0:18]`, `obs[36:39]` the target (MT1 shows it). Action: `[dx, dy, dz, gripper]`.
- `info` is empty at reset and filled by every step [run: `explore1.py`]. Read propositions from `obs`, `info` and `env.unwrapped` (`tcp_center`, `_target_pos`, `_get_site_pos`).
- Tags: `[code: file:function]` is MetaWorld 3.1.1 source (paths inside `metaworld/`; task files under `envs/`). `[run: script]` is a script in `.git/agent-memory/plans/env-files-upgrade/scripts/` run on the real environment. `mw_common.py` builds it and holds the readings of `environment.md` as code. Run from the repo root: `PYTHONPATH=<scripts dir> MUJOCO_GL=egl conda run -n RM_RL_env python -W ignore <script> <args>`.

## Truth conditions in code

All four are conditions recomputed from the current step; none uses the previous valuation. `u = env.unwrapped`.

- `near_nut`: `np.linalg.norm(obs[4:7] - u.tcp_center) <= 0.03`
- `nut_grasped`: `bool(info["grasp_success"])`
- `nut_near_peg`: `np.linalg.norm(u._get_site_pos("RoundNut") - u._target_pos) < 0.05 and not info["success"]`
- `assembly_complete`: `bool(info["success"])`

## Evidence

Environment
- Nut geometry (ring plus 0.13 m handle): [code: `assets/objects/assets/assembly_peg.xml`, sites `RoundNut` (ring centre) and `RoundNut-8` (handle end)].
- Reset, nut not randomized (low and high bounds equal), peg ranges, 0.1 m redraw: [code: `sawyer_assembly_peg_v3.py:reset_model`]. Ring (0, 0.6, 0.02) and `obs[4:7]` (0.13, 0.6, 0.02): [run: `reset_stats.py`].
- 50 pre-drawn layouts, random pick per reset: [code: `__init__.py:_make_tasks`, `RandomTaskSelectWrapper`]. Same `seed`, same layouts: [run: `reset_stats.py`, 800 resets].
- Hand start (0.005, 0.601, 0.195), fingers open: [run: `reset_stats.py`].
- Action effect: [code: `set_xyz_action`; run: `mechanics_check.py`, `obs[3]` 1.00 to 0.28 after 15 steps of +1].

Objective and episode boundary
- Success (aligned, hooked), reward 10: [code: `sawyer_assembly_peg_v3.py:_reward_pos`; `evaluate_state`, `info["success"]`; `compute_reward`].
- `terminated` never true, truncation at step 500, `ValueError` after: [code: `sawyer_xyz_env.py:step`, `max_path_length`; run: `mechanics_check.py`].
- No values before the first step (`info` empty): [run: `explore1.py`].

Proposition semantics
- `nut_grasped`, caging plus reach reward at least 0.5, no contact or lift test: [code: `compute_reward`, `sawyer_xyz_env.py:_gripper_caging_reward`, `evaluate_state`].
- `near_nut` reading: `info["near_object"]` holds the nut-orientation reward, `reward_ready` is `_reward_quat` [code: `evaluate_state`]; 0.999 at step 1 with the hand 0.18 m away [run: `expert_trace.py`, seed 0]. The 0.03 m value comes from the other tasks' flag [code: `sawyer_pick_place_v3.py:evaluate_state`]. The environment's own near-object flag is unusable here because it measures the nut's orientation, so the 0.03 m distance test is this file's choice; this task's own threshold: no source says.
- `nut_near_peg` reading, smallest `d` at reset 0.172 m (success radius 0.02 m in x-y): [run: `reset_stats.py`]. The environment has no "near the peg" flag; which threshold ARM-FM used: no source says.
- All four false after the first step: [run: `mechanics_check.py`, 50 of 50 episodes].

Constraints
- `nut_near_peg` and `assembly_complete` never hold together: follows from the `nut_near_peg` expression above, no run.

What the agent can and cannot do
- Hand box, hand target clipped: [code: `set_xyz_action`; run: `mechanics_check.py`, hand stopped at (0.416, 0.832, 0.413) after 120 steps of (+1, +1, +1), short of the box corner; cause not investigated].
- Orientation fixed: [code: `set_xyz_action`].
- Success has no grasp term: [code: `_reward_pos`]. `assembly_complete` held with `nut_grasped` false for 7854 steps in 30 expert episodes: [run: `expert_stats.py`].
- `nut_grasped` turned false again in 30 of 30 expert episodes: [run: `expert_stats.py`].
- `assembly_complete` has no latch: [code: `_reward_pos`]. The expert never lost it in 30 episodes: [run: `expert_stats.py`].

Example trace
- `SawyerAssemblyV3Policy` (`metaworld.policies`), `gym.make(..., seed=0)`, first reset; 500 steps, truncated, first success at step 91: [run: `expert_trace.py`, log `expert_assembly-v3_seed0.jsonl`].

This repository has no MetaWorld adapter (`ENVIRONMENT_FAMILIES` holds `minigrid` and `craftium`) [code: `app/src/arm_fm/environments.py`], so there is no labeling API; the conditions above read MetaWorld's own `obs` and `info`.
