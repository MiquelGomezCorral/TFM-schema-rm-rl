# ARM-FM simplification and correctness plan

## Goal and context

Make the existing ARM-FM implementation simpler and ready for representative live validation: saved labeling functions execute directly in Python, and native Tianshou components own training.

Independent review by one fresh Codex worker (`gpt-5.6-sol`, high reasoning) identified four gaps now addressed below: the label loader, manifest CLI wiring, readiness gates, and live-validation specification. No files changed or checks ran.

## Implementation

**Files touched:** `app/main.py`, `app/scripts/arm_fm.py`, `app/src/config/config.py`; the existing `__init__.py`, `runtime.py`, `environments.py`, `training.py`, `artifacts.py`, `generation.py`, and `evaluation.py` under `app/src/arm_fm/`; the RM generator/critic and labeling generator/critic templates under `app/src/prompts/arm_fm/`; `tests/test_arm_fm.py`; `README.md`. Delete `docker/arm-fm.Dockerfile`. The approved decision-record edit is specified separately below.

1. **Create one direct labeling path.**  
   In `runtime.py`, add `load_labeling_functions` using standard Python loading and the shared source validator. Load each bundle’s predicates once into an isolated namespace per environment. Extend `RewardMachineEnvironment` to own the callable mapping and resettable episode context, exposing the documented live environment API. After each environment step, evaluate the complete proposition valuation, update the RM once, combine rewards, and return the observation with its new RM-state embedding. Training and frozen evaluation must both use this wrapper.

2. **Remove Docker and obsolete alternatives.**  
   Delete `DockerLabelingWorker`, `DockerLabelingExecutor`, both harness generators, Docker-only imports/exports, and snapshot IPC. Remove unused policy-factory/embedding-loader CLI hooks, dead loaders, unused environment factories, and guessed labeling helpers. Retain actual domain adapters, useful error handling, and unrelated existing fixes.

3. **Unify proposition and validation contracts.**  
   In `artifacts.py` and `generation.py`, use one labeling validator and the environment’s declared proposition vocabulary. Require one synchronous `predicate(env)` per declared proposition; missing predicates are errors, not false defaults. Update labeling prompts accordingly and document episode-memory access. RM prompts and critics must accept implicit self-loops. Keep paper-format serialization and every compiler transition, including zero-reward state changes.

4. **Replace custom learner plumbing with Tianshou.**  
   In `training.py`, remove the custom replay buffer, manually rebuilt mini-buffers, fallback losses, and independent action-selection path. Use native collectors, persistent vector replay buffers, and off-policy/on-policy trainers. Keep only the necessary observation/RM-embedding encoder integration and algorithm-specific configuration.

   | Domain | Learner |
   |---|---|
   | MiniGrid/BabyAI | Native DQN |
   | XLand | Native RainbowDQN |
   | Craftium | Native PPO |
   | Meta-World | Native SAC, with RND only for declared variants |

   Rainbow uses native `Net` with dueling heads, `NoisyLinear` configured in both trunk and head dictionaries, 51 atoms over `[-10, 10]`, three-step returns, and persistent prioritized replay with alpha `0.5` and initial beta `0.4`. Preserve inherited Double-Q selection.

   Apply Appendix A.11 through `paper_training_config`, recording effective settings and library units. PPO uses contiguous rollouts. Retain only a narrow SAC specialization for critic updates every iteration and actor updates every second iteration; checkpoint its scheduling counter. Update the RND predictor during training, freeze its target always, and freeze both during evaluation.

5. **Wire single-task and shared-policy execution.**  
   In `app/main.py`, training accepts mutually exclusive `--bundle` and `--task-manifest` inputs. Wire manifest training and evaluation through `app/scripts/arm_fm.py`. Create separately wrapped environments for task entries, sharing one native policy and collector while isolating RM/label memory. Enforce compatible observation/action spaces and disjoint held-out task identities. Optional training overrides default to unset, preserving paper settings.

6. **Use native checkpoint ownership.**  
   Save and strictly restore Tianshou’s complete `Algorithm.state_dict`, which already includes registered optimizer state. Keep configuration, normalization, task/RM provenance, scheduling counters, and RND state alongside it. Remove JSON fallbacks and permissive partial loading. Evaluation uses the restored native policy with exploration and all learning updates disabled.

7. **Make bundle readiness stage-specific.**  
   Generation records actual stage acceptance, candidates, raw responses, feedback, settings, and failures through one consistently constructed attempt record. Preserve inspectable bundles and failure accounting.

   - Artifact judging requires candidate artifacts and their context, not embeddings.
   - Embedding requires a valid RM and complete, aligned state descriptions.
   - Training requires accepted RM/labeling stages, valid callable predicates, and finite, aligned embeddings.
   - The runtime wrapper records execution evidence only after predicates actually execute. Remove the undriven aggregate validation-stage requirement and `bool(source)` as evidence of executability.

   Invalid or incomplete bundles remain inspectable but cannot enter training.

8. **Keep embeddings and judging narrowly integrated.**  
   In `evaluation.py`, load and freeze the approved Qwen embedding model once; embed description text only using final-layer, last-non-padding-token pooling and L2 normalization. Record resolved model/tokenizer revisions and extraction settings. Do not inherit the generator’s model configuration accidentally. Reuse existing OpenAI/OpenCode engines for the independently selected judge, supplying full task/environment/API context while excluding generation-method metadata. Preserve submitted-task denominators and first-attempt/refined accounting.

## Requirements and boundaries

Preserve complete valuations, exactly one RM update per environment step, irrelevant-proposition independence, implicit zero-reward self-loops, ordered overlap warnings, episode reset, and environment-owned termination.

One task retains one RM. Both RM-generation modes share downstream labeling, descriptions, embeddings, training, and evaluation. Compiler language remains bounded; unsupported tasks fail explicitly.

Use only the existing **`RM_RL_env`**, Python 3.13, `uv pip`, and current dependencies. Craftium dependency compatibility and its wood-to-diamond state interface remain explicit completion blockers. Remove the documented `--no-deps` workaround; this pass must not fabricate an inventory API or claim complete paper reproduction.

Out of scope: new environments or frameworks, dependency bypasses, compiler-language expansion, published evidence edits, unrelated provider/compiler/web repairs, automatic experiments, commits, and publishing.

## Verification

Update only the existing focused tests for direct predicate loading, full valuations, reset/isolation, one RM update, native replay ordering, native action selection, checkpoint restoration, readiness gates, and frozen evaluation/RND state.

**Readiness check:**

```bash
conda activate RM_RL_env
uv pip check --python "$CONDA_PREFIX/bin/python"
python -m unittest discover -s tests -p 'test_arm_fm.py' -v
```

**Live validation — pending separate user approval**

- **Flow:** Generate DoorKey bundles through both RM-generation modes, embed them, execute scripted traces through direct labeling, perform a short native DQN optimizer update, save/reload the checkpoint, and evaluate frozen.
- **Expected:** Correct labels/rewards, exactly one RM update per step, actual training parameter changes, successful strict restoration, and unchanged learned state during evaluation.
- **Can run:** The executor through shell tools in `RM_RL_env`, with approved environment/model access. No Docker required.

## Instructions, memory, and decision records

Applicable instructions:

- `AGENTS.md`: preserve unrelated work; live validation requires approval.
- `.agents/conventions.md`: retain script/library boundaries; numeric RM conventions apply to compiler output.
- `python-coding/SKILL.md`: use the existing Conda environment and `uv`.
- `decision-records/SKILL.md`: apply only the approved record changes.
- `review-plan/SKILL.md`: keep this review read-only and provide a self-contained execution plan.

**Main-agent memory updates:** None. Personal `.agents/` memory remains unchanged.

**Decision records: update** `docs/decisions/arm-fm/reproduction-boundary.md`. The main orchestrator owns these exact changes during execution: record completed generation followed by in-process labeling, native Tianshou ownership, and the narrow paper-required scheduling adaptation in **Current decisions** and **Rationale**; update **Enforcement** after verification. Preserve existing protected invariants. No new record or index change.

The plan is finalized in chat and ready for `$code`.

