# ARM-FM correctness corrections

## Goal

Correct the current ARM-FM reconstruction so bundles remain inspectable, native Tianshou training follows the paper’s settings, and evaluation/judging produce reliable reproducible results.

## Context

The implementation already contains the planned ARM-FM pipeline, but review found several correctness gaps: unsafe manifest path semantics, missing episode memory updates, incomplete failure persistence, incorrect PPO interaction accounting, unused warmup settings, incomplete judge context, inaccurate embedding provenance, and evaluation metrics that are discarded.

The final review used one fresh Codex worker with `gpt-5.6-sol` at high reasoning. It confirmed the findings against Tianshou 2.0.1 and the repository.

## Files touched

- `app/main.py`
- `app/scripts/arm_fm.py`
- `app/src/arm_fm/runtime.py`
- `app/src/arm_fm/environments.py`
- `app/src/arm_fm/training.py`
- `app/src/arm_fm/generation.py`
- `app/src/arm_fm/evaluation.py`
- `app/src/prompts/arm_fm/labeling_generator.system.md`
- `app/src/prompts/arm_fm/labeling_generator.user.md`
- `app/src/prompts/arm_fm/labeling_critic.system.md`
- `tests/test_arm_fm.py`

No configuration layer, artifact schema module, README, Docker, or dependency files need changes.

## Requirements

- Evaluate the complete proposition valuation before updating the RM.
- Perform exactly one RM update per environment step.
- Give every predicate the same immutable previous-step valuation.
- Save the current valuation only after every predicate succeeds.
- Clear RM state and episode memory on reset.
- Keep unmentioned transitions as zero-reward self-loops.
- Preserve environment-owned termination.
- Generation failures must leave inspectable partial bundles.
- Training requires accepted artifacts, callable predicates, and aligned finite embeddings. Execution evidence is recorded only after predicates execute.
- Use native Tianshou collectors, replay buffers, trainers, optimizers, schedulers, and algorithm checkpoints.
- Count actual collected environment transitions in checkpoints.
- Preserve complete PPO rollouts of four environments × 128 steps. With a requested 10,000,000-transition budget, the native final rollout reaches 10,000,384 transitions; record this actual count instead of truncating the paper’s rollout.
- RND is enabled only for explicitly named RND variants.
- Judge inputs remain independent of RM-generation method.
- No live environment or model calls during implementation.

## Steps

1. **Correct predicate execution in `runtime.py`.**
   - Add `range` to the restricted builtin namespace used by `load_labeling_functions`.
   - Before evaluating predicates, create one read-only snapshot containing the previous complete valuation.
   - Give every predicate that same snapshot so evaluation order cannot affect results.
   - After all predicates succeed, save `dict(valuation)` as `previous_valuation`.
   - Do not update memory when any predicate raises.
   - Reset clears this memory.
   - Keep the existing single call to `RewardMachineRuntime.step`.

2. **Clarify the generated-label contract.**
   - Update the labeling generator and critic prompts to state that `env.episode_memory["previous_valuation"]` is read-only and contains the preceding environment step’s complete valuation.
   - Persistent propositions describe current state. Event propositions such as `key_lost` may compare current state with that previous valuation.
   - Predicates must not mutate the environment or episode memory.

3. **Complete the XLand adapter in `environments.py`.**
   - Expose the current timestep’s `observation` and `state`, while retaining `params`.
   - Replace XLand’s local action-space stub with `gymnasium.spaces.Discrete`, because native random warmup calls `action_space.sample()`.
   - Leave the unknown Craftium state interface as an explicit blocker.

4. **Make task manifests unambiguous in `training.py` and `arm_fm.py`.**
   - Replace `TaskManifestEntry.environment` with:
     - `environment_description: Path`
     - `environment_id: str`
   - Resolve `bundle` and `environment_description` relative to the manifest’s directory.
   - Treat `environment_id` as an opaque runtime identifier and never path-resolve it.
   - Generation reads the Markdown description; training constructs the runtime environment from the ID.
   - Retain `settings` and `split`, which current generation and held-out selection use.
   - Do not add compatibility handling for the previous unvalidated manifest format.
   - Remove the evaluation fallback that treats `bundle.manifest.environment` as a runtime environment ID.

5. **Persist compiler-mode downstream failures in `generation.py`.**
   - Give `generate_compiler_bundle` the requested bundle directory.
   - If labeling or description generation fails, construct and save a partial bundle containing:
     - the accepted compiler RM;
     - completed and failed stage status;
     - accumulated attempts, feedback, raw responses, and errors.
   - Re-raise after persistence.
   - Keep the RM stage complete; do not replace it with the current generic compiler-failure bundle.
   - Pass the bundle directory from `generate_larm`.

6. **Correct generation metadata and attempt accounting.**
   - Remove `validation.deterministic`.
   - For ARM-FM generation, classify an artifact as first-attempt only when RM, labeling, and descriptions were all accepted on attempt one. Classify it as refined when any accepted generated stage required a later attempt.
   - For compiler mode, exclude the compiler-created RM from FM attempt accounting; calculate first/refined from labeling and description generation.
   - Keep compiler origin in `rm_mode` and `compiler_text`, without inventing a synthetic FM attempt.

7. **Fix learner selection, warmup, and checkpoint accounting in `training.py`.**
   - Replace substring iteration through `ALGORITHMS` with explicit most-specific matching so XLand always selects Rainbow.
   - For off-policy learners, run `Collector.collect(random=True)` before trainer updates using `min(learning_starts, remaining budget)`.
   - Use the collector’s returned `n_collected_steps`, because vector collection may pass the requested boundary.
   - Subtract actual warmup steps from the remaining trainer budget.
   - Offset epsilon and learning-rate progress by the warmup count.
   - Preserve the prefilled native replay buffer when starting the trainer.
   - If warmup consumes the complete budget, skip the trainer and save a valid checkpoint.
   - Return actual collected transitions from the training function and store that number in `TrainingCheckpoint.timestep`; keep the requested budget in the serialized configuration.

8. **Correct native PPO configuration.**
   - Construct exactly four independent environment instances and wrappers for a single-task Craftium PPO run.
   - Manifest PPO runs must supply exactly four independent training entries; reject unsupported counts instead of adding a task scheduler.
   - Use:
     - four environment lanes;
     - 128 steps per lane and collection;
     - batch size 128;
     - four update repetitions;
     - value clipping enabled;
     - entropy coefficient `0.01`;
     - value coefficient `0.5`;
     - one trainer epoch owning the requested run;
     - native `LRSchedulerFactoryLinear`.
   - Keep full 512-transition collections. Allow the final collection to pass the requested total and persist the actual transition count.
   - Remove the current `ceil(total / rollout_length)` outer epoch multiplication.

9. **Correct RND behavior.**
   - Compute the intrinsic bonus before updating the predictor.
   - Add that pre-update bonus to the rollout reward, then update the predictor.
   - Do not introduce a new normalization subsystem.
   - Enable RND only when the runtime domain/variant explicitly contains the RND designation, rather than for every Meta-World run.
   - Keep the target frozen and disable predictor updates during evaluation.

10. **Persist resolved embedding provenance in `evaluation.py` and `arm_fm.py`.**
    - Resolve the actual model and tokenizer revisions from their loaded commit or stable snapshot identifiers.
    - Reject embedding when no stable resolved revision can be determined.
    - Return those revisions in `EmbeddingSettings`.
    - Use resolved settings in cache keys.
    - Store model, tokenizer, extraction, normalization, and device settings in the bundle’s effective settings before saving.

11. **Make judging complete and method-blind.**
    - Build each bundle’s judge engine from its stored `inputs.environment_markdown`; remove the required external `--environment` argument from `evaluate-larm`.
    - Include stored task text, environment Markdown, proposition semantics, API definitions, candidate RM, labeling code, state descriptions, and execution evidence.
    - When no evidence argument is supplied, use `bundle.execution_evidence`.
    - Exclude RM mode, provenance, provider settings, attempts, critic feedback, and judge model from the prompt.
    - Keep judge/provider failures as unscored judgments. Count only incomplete or failed generation bundles as generation failures.

12. **Expose meaningful frozen-evaluation results.**
    - Accumulate reward over the entire episode.
    - Return episode return, step count, final RM state, termination/truncation flags, and scalar final-info metrics.
    - Have `evaluate_policy_command` print the returned results as JSON.
    - Preserve evaluation mode, disabled gradients, disabled exploration, and disabled RND updates.

13. **Add focused regression coverage in `tests/test_arm_fm.py`.**
    - Generated predicate using `range`.
    - Immutable shared previous valuation, post-success update, and reset.
    - XLand observation/state access and random action sampling.
    - Compiler downstream failure persistence without losing the accepted RM.
    - Relative manifest paths and distinct description/runtime fields.
    - XLand-to-Rainbow dispatch.
    - Random warmup, remaining-budget accounting, and actual checkpoint timestep.
    - Four-lane PPO arguments, complete-rollout overshoot, and native LR scheduler.
    - Pre-update RND bonus.
    - Explicit-only RND selection.
    - Resolved embedding revisions and cache identity.
    - Complete method-blind judge context and default execution evidence.
    - Cross-stage first/refined accounting.
    - Accumulated evaluation output.
    - One small native algorithm parameter update followed by strict checkpoint save and restore.

## Applicable instructions

- `AGENTS.md`: keep the solution small, preserve unrelated changes, and require separate approval for live validation.
- `.agents/conventions.md`: preserve existing script/library boundaries and the separate compiler/paper RM representations.
- `python-coding/SKILL.md`: use the existing `RM_RL_env` environment and `uv`; do not create another environment.
- `decision-records/SKILL.md`: preserve existing approved invariants and avoid progress-note records.
- `review-plan/SKILL.md`: provide a self-contained execution plan and perform no edits during review.

## Readiness check

```bash
conda run -n RM_RL_env python -m unittest discover -s tests -p 'test_arm_fm.py' -v
```

## Live validation

**Flow:** Pending separate user approval, generate one DoorKey bundle through each RM-generation mode, embed its state descriptions, execute a scripted direct-label trace, run a short native DQN update, strictly save/reload its checkpoint, and run frozen evaluation.

**Expected:** Complete correct valuations, exactly one RM update per environment step, correct accumulated rewards, changed training parameters, exact checkpoint restoration, and no learned-state changes during evaluation.

**Can run:** Shell tools in `RM_RL_env` with approved model and environment access. Docker is not involved.

## Main-agent memory updates

None. Leave personal `.agents/` memory unchanged.

## Decision records

**Decision records: no change** — these corrections enforce the existing decisions and the previously applied reproduction-boundary update.

**Applicable records:**

- `docs/decisions/arm-fm/catalogue-and-evidence.md`
- `docs/decisions/arm-fm/task-and-rm-identity.md`
- `docs/decisions/arm-fm/reproduction-boundary.md`
- `docs/decisions/arm-fm/rm-execution.md`

**Record changes:** None.

**Protected invariants:** one task/RM identity, full bundle evidence, complete valuations, irrelevant-proposition independence, ordered overlap handling, and exactly one RM update per environment step.

**Enforcement:** Runtime behavior, bundle validation, focused tests, and the pending live validation flow.

## Out of scope

- Docker or subprocess labeling execution
- CUDA support
- New dependencies or Conda environments
- Craftium installation or an invented Craftium inventory interface
- Compiler-language expansion
- A new configuration or environment-factory framework
- Backward compatibility for the unvalidated task-manifest format
- RND normalization infrastructure
- Live LLM, embedding, compiler, or environment calls
- Unrelated cleanup
- Commits, pushes, or publishing

The plan is finalized in chat and ready for `$code`.
