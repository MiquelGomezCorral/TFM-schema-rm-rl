# X2 code changes

Branch `MiquelGomezCorral/tp-x2-dqn-crm` (worktree `tp-x2-dqn-crm`), base `7ae1157`. Uncommitted; the full diff is `code-changes.patch`.
Defaults are byte-identical to the base (K1): `dqn_num_envs: 1`, `counterfactual: false`.

| File | Function / part | Why |
|---|---|---|
| `app/src/config/config.py` | `dqn_num_envs: int = 1`, `counterfactual: bool = False` | The two new settings; defaults keep the old behaviour. |
| `app/src/arm_fm/runtime.py` | `RewardMachineRuntime.step_from(state, valuation)` | Pure transition selection from any state; `step()` calls it and sets `self.state`. CRM needs "what would state u have done". |
| `app/src/arm_fm/runtime.py` | `RewardMachineEnvironment.settle(rm_step, env_reward, env_terminated, truncated)` | The end / judgment / end-charge / `both` logic moved out of `step()` unchanged so a counterfactual transition is scored by the same rule as a real one. |
| `app/src/arm_fm/runtime.py` | `RewardMachineEnvironment.step()` | Calls `settle`; puts `rm_source` (the state the step started in) in `info` so CRM can skip the real source. |
| `app/src/arm_fm/environments.py` | `RewardMachineObservation.counterfactual_transition`, `counterfactual_transitions` | One `(obs, next_obs, reward, terminated)` per non-final, non-rejecting state other than the real source, from the same true propositions (Toro Icarte et al., JAIR 2022). |
| `app/src/arm_fm/dqn.py` | `train_dqn` | Builds `dqn_num_envs` training environments (a plain loop, not `SyncVectorEnv`, so the 1-env path stays identical and each wrapper stays reachable). |
| `app/src/arm_fm/dqn.py` | `_check_settings` | Rejects `total_timesteps % dqn_num_envs`, and `counterfactual` with `reward_source: env` or `task_bundles`. |
| `app/src/arm_fm/dqn.py` | `select_actions` (new), `select_action`, `_stack` | One batched greedy forward pass for all envs; per-env exploration draws in order, so N=1 draws the same numbers as before. |
| `app/src/arm_fm/dqn.py` | `create_replay_buffer` | `n_envs=dqn_num_envs`; capacity stays `min(buffer_size, total_timesteps)` transitions. |
| `app/src/arm_fm/dqn.py` | `step_transitions`, `store_transitions` (replace `store_transition`) | The real transition first, then its counterfactuals; the k-th transition of every env goes in the k-th buffer row. |
| `app/src/arm_fm/dqn.py` | `DQNLearner.update`, `_multiples` | Update and target-sync schedules count env-step multiples inside a round, so gradient updates per env step equal the 1-env run for any `dqn_num_envs`. |
| `app/src/arm_fm/dqn.py` | `_train`, `_training_reset_seeds` | Round loop over all envs, per-env episode trackers and resets, eval trigger by multiples. Procedural layouts: env `i` first-reset seed is `seed + i` (run seeds that differ by less than `dqn_num_envs` share layouts; see the report). |
| `app/src/arm_fm/dqn.py` | `POSITIVE_SETTINGS`, `RUN_SETTINGS` | The new settings are validated and recorded in the run's settings. |
| `tests/test_rl_contract.py` | the three `store_transition(...)` calls | Moved to `store_transitions(buffer, [action], [step_transitions(CONFIG, env, observation, step)])`. The test is skipped locally without the git-ignored `outputs/bundles/UnlockPickup-1`. |
| `experiments/benchmark/tuning/dqn/{round1,round2,round3,round4,control,procedural}/` | suite files | Run definitions, new files. |
