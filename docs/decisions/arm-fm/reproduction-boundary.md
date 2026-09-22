# ARM-FM reproduction boundary

## Intent

State exactly what this project recreates from ARM-FM and where comparison must remain
semantic rather than byte-for-byte.

## Current decisions

- Reconstruct the complete ARM-FM baseline: Reward Machines, executable labeling functions,
  state descriptions, embeddings, training, and zero-shot evaluation. Then substitute the
  existing compiler for RM generation only, retaining the same downstream methods.
- Generated baseline RMs explicitly identify final states as a documented reconstruction
  extension to the paper's printed format. Published RM evidence remains unchanged.
- An experiment task bundle has one paper-layout RM artifact, `reward_machine.txt`.
  Compiler generation passes its accepted numeric RM in memory instead of writing a
  second `.rm` file; both modes use the same downstream embedding and training flow.
- The environment Markdown owns the allowed proposition vocabulary. Propositions describe
  observable state conditions or explicitly documented progress events; raw actions are
  not RM events.
- The current compiler supports `Existence`, `ExistenceTwo`, and `Precedence` clauses,
  then deterministically composes their reachable conjunction product.
- Reconstruction targets should be submitted as one composite task. Atomic probes are
  useful for checking individual stages but are not a replacement for the composite
  target.
- Semantic equivalence is the default comparison criterion. Byte-identical comparison is
  valid only when proposition names, event predicates, rewards, and serialization format
  all match the released artifact.
- Missing published components are reconstructed and labelled as such; they do not block
  implementing the complete workflow or become claims of exact experimental recovery.
- The state-description generator receives task, environment, and RM context. The embedding
  model receives only the resulting state-description text. The judge receives the task,
  environment, rules, labeling API, candidate artifacts, and identified execution evidence.
- Complete implementation before full experiments. Live validation requires separate approval.
- Use the existing `RM_RL_env` Conda environment for local Python work. Install dependencies
  with `uv pip` into that environment, keeping `requirements.txt` authoritative; do not create
  another Conda environment or virtual environment for this reconstruction.
- Use Tianshou for the reconstructed DQN, Rainbow, PPO, and SAC learners. This library choice
  is a reconstruction, not a claim about the authors' original training stack.
- Finish generation before training or evaluation. Load saved labeling functions once per
  environment and execute them in the same Python process, with isolated episode-local
  memory; Docker and a separate labeling execution backend are not required.
- Let native Tianshou policies, collectors, replay buffers, trainers, and algorithm state
  dictionaries own learning and checkpoint state. Keep only the RM observation integration
  and the narrow SAC scheduling adaptation needed for the paper's critic-every-update and
  actor-every-second-update schedule.
- Adapt the small MIT-licensed RLeXplore RND implementation to the project's Torch interface,
  preserving attribution and the upstream revision. Do not install the incompatible legacy
  `rllte-core` dependency set or bypass dependency checks.

## Protected invariants

- Complete the baseline before integrating the compiler replacement. Comparisons change RM
  generation while preserving downstream methods and frozen zero-shot evaluation.
- The compiler must not invent undeclared propositions or silently approximate unsupported
  temporal meaning.
- Every enabled bounded automated critic must accept a compiled proposal before finalization;
  disabling both critics is an explicit, warned fallback rather than the default. The deterministic
  compiler remains the owner of LTLf, automata, and rewards.
- Paper defects remain visible in evidence files: Craftium's Appendix A.9 block uses an
  undeclared `u4` and inconsistent reward transitions; KeyCorridor's trace uses a
  DoorKey mission; Meta-World's exact sparse wrapper is unpublished; XLand's decoded
  1,000 prompts and task-specific RMs are unpublished.
- Proposition-name translations are documented beside each pair. A translation is not
  claimed to be an executable labeling-function implementation.

## Rationale and tradeoffs

Reconstructing the complete baseline makes it possible to measure the contribution of the
improved RM generator while preserving the paper's downstream capabilities. Unpublished
details require explicit reconstruction choices, so semantic comparisons remain distinct
from exact reproduction of source artifacts or numerical results. The compiler's supported
language remains bounded; unsupported tasks are reported rather than weakened.

Separating generation from policy execution permits direct calls to saved predicates and
avoids container and serialization machinery. Labeling runs with the Python process's
permissions. Native Tianshou components avoid competing implementations of action selection,
replay, and optimizer state; the narrow SAC adaptation retains the paper's update schedule
without introducing another learner framework.

## Enforcement

- Supported templates and retry/refusal behavior are defined in
  `app/src/engines/generic_engine.py`, `app/src/engines/structured.py`, and
  `app/scripts/generate_rm.py`.
- Formula composition and rejection of unreachable accepting products are implemented in
  `app/src/compiler/pipeline.py` and `app/src/compiler/reward_machine.py`.
- Environment vocabulary validation is implemented in `app/src/models/environment.py`.
- Critic schemas, three-attempt orchestration, and CLI/web toggles are documented in
  `docs/LTLF_TASK_LANGUAGE.md` and enforced in the generation and UI modules.
- Source gaps and semantic mappings are review-only because the unpublished artifacts
  cannot be mechanically verified.
- Shared in-process predicate loading, isolated episode memory, and one RM update per
  environment step are implemented in `app/src/arm_fm/runtime.py`; focused runtime contracts
  are checked in `tests/test_arm_fm.py`.
- Native Tianshou learning, replay, checkpoint restoration, and SAC scheduling are owned by
  `app/src/arm_fm/training.py`, with focused readiness checks in `tests/test_arm_fm.py`.
- Baseline-first integration, context boundaries, deferred experiments, and complete frozen
  comparison remain Review-only; focused checks do not establish full paper reproduction.
- Environment selection, the dependency installation workflow, and RND provenance remain
  Review-only. `uv pip check` verifies installed dependency consistency, not Craftium's native
  compatibility or task interface; those remain unverified pending live validation.

## History

- 2026-09-18: Expanded the former RM-only scope to complete baseline reconstruction followed
  by an RM-generation-only substitution; fixed context boundaries and deferred experiments.
- 2026-09-18: Selected the existing `RM_RL_env` with `uv pip` and `requirements.txt`, Tianshou
  learners, and an attributed RLeXplore RND adaptation for completing the reconstruction.
- 2026-09-21: Required explicit final states in generated baseline bundles and one
  paper-layout RM output per experiment task, while leaving published evidence intact.
- 2026-09-22: Permitted warned critic-free compiler runs for controlled fallback comparisons while
  keeping the deterministic compiler boundary.
