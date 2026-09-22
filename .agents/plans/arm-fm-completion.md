# Complete the remaining ARM-FM implementation

**Goal:** Finish the runnable ARM-FM baseline, then substitute only RM generation with the existing compiler while preserving labeling, descriptions, embeddings, training, and frozen zero-shot evaluation.

The independent review is complete. Its six clarifications are incorporated below. No files were changed or dependencies installed during review.

## 1. Environment and dependencies

Use the existing **`RM_RL_env`** Conda environment and its Python 3.13. Keep `requirements.txt` authoritative:

```bash
conda activate RM_RL_env
uv pip install --python "$CONDA_PREFIX/bin/python" \
  --torch-backend auto -r requirements.txt
```

- Add compatible pinned Tianshou, Torch, Transformers, Accelerate, MiniGrid, XLand-MiniGrid, and Meta-World dependencies. Preserve the editable project installation.
- Implement the approved small, attributed MIT RLeXplore RND adaptation using Torch/NumPy. Record its upstream revision and reconstructed behavior; do not install incompatible `rllte-core` dependencies.
- Build Craftium’s native engine and install its Python interface into this same environment, documenting the source revision and native prerequisites.
- Update the existing README setup instructions. Create no additional environment or dependency-management system.

The earlier dependency dry run established resolution feasibility, not runtime correctness.

## 2. Generation, bundles, and environment execution

Work within the existing `app/src/arm_fm/artifacts.py`, `generation.py`, `environments.py`, and `runtime.py`; packaged prompts under `app/src/prompts/arm_fm/`; and `docker/arm-fm.Dockerfile`.

1. Restore the substantive Appendix A.8 generator, critic, and labeling instructions. Adapt task content and documented APIs per domain, retaining bounded refinement and the existing structured critic response.
2. Reuse the existing **OpenAI/OpenCode engines** for generation, critics, labeling, descriptions, and judging. Preserve provider selection, authentication, and failure behavior.
3. Persist complete task/environment inputs, API definitions, candidates, raw critic responses, feedback, effective model settings, and errors. Failed runs must remain inspectable even when no valid RM exists: save their manifest and attempts without fabricating missing artifacts.
4. Make validation authoritative. Distinguish structural validation, executable evidence, and critic judgments. Training rejects incomplete or invalid bundles.
5. Implement actual MiniGrid/BabyAI registration, XLand’s functional environment adapter and `get_ruleset` access, the five catalogued Meta-World tasks, and Craftium’s wood-to-diamond task. Remove guessed observation semantics.
6. Decode XLand `medium-1m` indices `0–999` into deterministic goal/rule/object descriptions, preserving indices and source provenance. Report unsupported encodings explicitly.
7. Match generated predicates’ documented API to an environment snapshot proxy, including interfaces such as `grid.get`. Use a persistent Docker labeling worker per active environment, with explicit reset and bounded execution. Correct container invocation, permissions, resource limits, and cleanup. Generated code never falls back to host execution.

**Preserve the agreed RM contract:** complete proposition valuations; exactly one RM update per environment step; relevant guards only; implicit zero-reward self-loops; first matching stored transition plus warning on overlap; and episode-local reset. Persistent possession, loss events, and first-acquisition-per-episode events retain their documented meanings.

## 3. Runnable training, embeddings, and evaluation

Complete `app/src/arm_fm/training.py` and `evaluation.py`, with command orchestration in `app/scripts/arm_fm.py`, registration in `app/main.py`, and settings in `app/src/config/config.py`.

1. Replace the generic placeholder learner with Tianshou DQN for MiniGrid/BabyAI, Rainbow for XLand, PPO for Craftium, and SAC with the declared RND variation for Meta-World. Apply Appendix A.11 budgets, schedules, update frequencies, and algorithm components.
2. Supply built-in policy networks and observation preprocessing: spatial encoders for grid/image observations and MLPs for continuous observations, concatenating the active RM embedding before policy/value heads. Record effective architecture and preprocessing as reconstructed choices. No caller-written policy factory is required.
3. Use algorithm-appropriate replay or rollouts, correct current/next RM context, and termination-versus-truncation handling. Combine environment and RM rewards; add RND only for declared variants.
4. Save tensor-aware checkpoints containing policy, optimizer, normalization, RND, configuration, and provenance. Evaluation must load the checkpoint and freeze every learning component.
5. Supply the built-in frozen **Qwen3-30B-A3B-Instruct-2507** embedding loader. Embed only state-description text using final-layer last non-padding-token pooling and L2 normalization. Record model/tokenizer revisions and extraction settings; handle device placement and cache identity correctly.
6. Configure the Qwen judge independently from generator selection through the existing engines. Give it full task/environment/rules/API context and candidate artifacts, blinded to generation method. Keep execution evidence separate from its judgment.
7. Continue benchmark processing after individual failures. Report the four correctness categories, unscored failures, scoring coverage, and first-attempt versus refined outcomes against the complete submitted task count.

**Task manifests:** Use an ordinary manifest mapping task IDs to bundle paths and environment settings. Generation processes entries independently; training shares one policy across declared training entries while maintaining separate RM/labeling state per environment. Evaluation distinguishes training tasks from disjoint held-out tasks. Include the paper’s XLand training groups, ablations, and three seeds.

**Compiler substitution:** Finish the baseline first. Invoke `scripts.generate_rm` from command orchestration and capture `GenerationHooks.completion`; pass accepted compilation results into the library for adaptation. Library code must not import scripts. Preserve every compiled transition, including zero-reward state changes, and reuse the same downstream methods. Unsupported temporal instructions remain explicit failures.

## 4. Verification and live validation

Extend the existing `tests/test_arm_fm.py` only for critical contracts:

- One RM update, irrelevant propositions, acquisition/loss, overlap warnings, and episode reset.
- Incomplete-bundle persistence and training rejection.
- Actual learner updates on synthetic batches, tensor checkpoint round trips, and frozen evaluation/RND targets.
- XLand indexing/rendering, multi-task isolation, disjoint held-out sets, and built-in CLI paths.
- Existing engine reuse, complete judge context, and failure accounting.

Minimum non-live readiness check:

```bash
conda activate RM_RL_env
uv pip check --python "$CONDA_PREFIX/bin/python"
python -m unittest discover -s tests -p 'test_arm_fm.py' -v
```

Keep previously reported web-test failures separate; do not label them pre-existing without evidence or expand into unrelated UI repairs.

**Live validation — pending separate user approval after implementation:**

- **Flow:** Generate DoorKey bundles through both RM-generation modes, embed them, execute scripted environment traces, perform a short training run with an optimizer update, save/reload the checkpoint, and run frozen evaluation.
- **Expected:** Executable bundles; correct labels/rewards; exactly one RM update per step; real parameter updates during training; unchanged learned state during evaluation.
- **Can run:** The executor through shell tools in `RM_RL_env`, with Docker, approved model access, and environment assets.

Implementation readiness and successful live validation must be reported separately. Full paper-scale experiments remain deferred.

## 5. Decisions, instructions, and boundaries

**Decision records: update** `docs/decisions/arm-fm/reproduction-boundary.md` with the already approved choices: existing `RM_RL_env`, `uv` plus `requirements.txt`, Tianshou learners, and the attributed RND adaptation. Add a dated History entry. The main orchestrator owns these document changes during execution.

Preserve the existing reproduction, task-identity, catalogue, and RM-execution records and index links. No new record or index link is required. **Personal `.agents/` memory remains unchanged.**

Applicable instructions:

- `AGENTS.md`: preserve unrelated work and require approval for live validation.
- `.agents/conventions.md`: follow existing package and environment-document conventions.
- `python-coding/SKILL.md`: use the existing Conda environment, `uv`, and correct script/library boundaries.
- `decision-records/SKILL.md`: apply only approved record changes.
- `review-plan/SKILL.md`: retain a self-contained execution specification.

Out of scope: new environments, workflow frameworks, temporal-language expansion, unrelated compiler/UI refactoring, fabricated published artifacts, automatic live experiments, commits, and publishing.

The plan is finalized in chat and ready for `$code`.

