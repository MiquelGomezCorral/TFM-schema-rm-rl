# Reconstruct ARM-FM, then replace only RM generation

## Goal and reviewed context

Build the complete ARM-FM workflow—Reward Machines, executable labeling functions, state descriptions, embeddings, training, and zero-shot evaluation—then compare it with the existing compiler substituted only for RM generation.

The independent review is complete. Its findings are resolved by specifying a separate runtime RM representation, explicit prompt packaging, concrete Docker isolation, and independently implemented integrations using the author repository as behavioral evidence.

The repository currently supplies the improved DECLARE/LTLf compiler. The paper and released repository supply useful prompts, artifacts, and MiniGrid behavior, but several experiment components require reconstruction. Record that distinction without treating missing published code as a blocker.

No implementation, experiments, or decision-record edits occur during this planning turn.

## Requirements and interfaces

**One task produces one artifact bundle.** The bundle makes generation inspectable, repeatable, and reusable for training and comparison. Its versioned manifest references:

- Task text, environment identity, proposition meanings, and source provenance.
- RM text and its parsed representation.
- Generated Python predicates and their environment API.
- A description for every RM state; embeddings with an explicit state-to-row mapping.
- Generation settings, raw responses, critic feedback, validation results, and stage status.

Keep failed attempts and incomplete bundles available for analysis. Training requires a complete, validated bundle.

Expose these commands through the existing CLI:

| Command | Purpose |
|---|---|
| `generate-larm` | Generate a bundle using `arm-fm` or `compiler` RM generation |
| `embed-larm` | Embed validated state descriptions |
| `evaluate-larm` | Judge artifact correctness and aggregate benchmark results |
| `train-larm` | Train from a manifest of task bundles and experiment settings |
| `evaluate-policy` | Evaluate a saved policy on declared tasks without learning |

Preserve `generate-rm` and its existing outputs. Batch commands consume explicit manifests; do not add a workflow framework.

**Runtime semantics are fixed:**

- Labels describe all declared propositions that are true at the current step. Each proposition documents whether it represents a persistent condition or a one-step event.
- `!has_key` means the key is absent now. A moment-of-loss event requires its own explicit definition.
- Evaluate outgoing guards from the **old RM state** against one complete valuation. Select one transition and update the RM exactly once per environment step.
- Ignore propositions absent from a guard. Unmatched valuations produce a zero-reward self-loop; do not enumerate every proposition combination.
- Expect disjoint guards. If multiple ordinary guards match, select the first stored transition and emit a warning. `else` applies only when none matches.
- State changes never trigger another evaluation during the same environment step.
- Reset the RM and any episode-local labeling memory when the environment resets.

The runtime representation uses ordered transitions and string state identifiers. It must accept the paper’s format without requiring the compiler’s numeric identifiers or single accepting state. Environment termination remains authoritative; do not infer episode completion merely from an RM state name.

## Implementation steps and files

### 1. Establish the shared bundle and runtime

Implement the new subsystem under these paths:

- `app/src/arm_fm/artifacts.py`: bundle manifest, loading, validation, and provenance.
- `app/src/arm_fm/runtime.py`: paper-format parsing/serialization, ordered transition execution, reward lookup, and environment wrapper.
- `app/src/arm_fm/generation.py`: baseline generation and compiler adaptation.
- `app/src/arm_fm/evaluation.py`: embeddings, judging, and correctness aggregation.
- `app/src/arm_fm/environments.py`: environment creation, documented labeling APIs, and task decoding.
- `app/src/arm_fm/training.py`: algorithm selection, training, checkpoints, and frozen evaluation.
- `app/scripts/arm_fm.py`: command orchestration; register commands in `app/main.py`.

Use ordinary dataclasses, JSON, and existing repository conventions. Keep the compiler’s `RewardMachineStructure` unchanged.

Reuse Boolean guard parsing/evaluation from `app/src/compiler/reward_machine.py` through a small public helper rather than implementing a second parser. Preserve declared proposition identifiers and validate guard references.

Parse the paper’s separate transition and reward sections. Missing reward entries mean zero reward; reject reward entries referring to nonexistent transitions. Reject undeclared states and malformed artifacts, while preserving raw source text and diagnostics.

### 2. Reconstruct the baseline generation stages

Package prompts under `app/src/prompts/arm_fm/`, with a dedicated resource reader and explicit package-data configuration in `pyproject.toml`. Do not route these roles through the compiler’s three-role prompt mapping.

Implement:

1. RM generator → critic → bounded refinement.
2. Labeling-function generator → critic → bounded refinement.
3. State-description generation and structural validation.

Adapt Appendix A.8 to each environment’s task and available API. Preserve the paper’s two-section RM output. Use three attempts per stage as an explicitly reconstructed default; save every attempt.

Reuse provider clients, response extraction, and authentication in `app/src/engines/provider_engines.py`. Add the minimum request support needed for paper-style text artifacts without changing existing structured compiler requests. Preserve provider selection, failure reporting, and Antigravity’s no-tool-execution safeguards.

Generator and critic context includes the task, environment, proposition semantics, relevant APIs, and current candidate. Optional human feedback is explicit and recorded; automated benchmark runs disable it.

Generate callable predicates over the documented environment interface. Compute one valuation per step, then pass it to the RM. Compound guards remain Boolean expressions over predicates, not Python function names.

### 3. Supply the environment integrations and execution boundary

Implement MiniGrid/BabyAI first, then XLand-MiniGrid, Meta-World, and Craftium.

- **MiniGrid/BabyAI:** recover task behavior and labeling APIs from the released artifacts and official environments.
- **XLand:** pin the benchmark/source revision; decode indices `0–999` of `medium-1m`. Render goals, production rules, and initial objects deterministically. Cover every encountered encoding; report unsupported encodings explicitly rather than dropping tasks.
- **Meta-World:** implement the five catalogued tasks. Treat native success converted into a one-time sparse success reward and successful-episode termination as a reconstructed wrapper.
- **Craftium:** implement the documented wood → stone → iron → diamond task using the public carrier environment. Preserve first-acquisition-per-episode proposition semantics, including after inventory loss. Document reconstructed termination and horizon settings.

Keep environment-specific facts in the existing `examples/arm-fm/` catalogue. Published evidence remains unchanged; reconstructed runtime artifacts live separately.

Execute generated Python inside Docker, including when labeling during training. Add `docker/arm-fm.Dockerfile` with domain-specific dependency targets. Use network-disabled containers, no forwarded credentials, read-only inputs, bounded resources, a non-root process, and writable temporary/output locations only. Missing Docker support fails clearly; no automatic host-execution fallback.

Docker and its daemon are available on the inspected host. Container builds and execution have not been performed.

Keep RL/environment dependencies optional and isolate incompatible domain dependencies in their image targets. Do not install the upstream project wholesale: its `src` namespace conflicts with this repository, and no license was found in the inspected release. Implement the integration independently from documented behavior.

### 4. Implement descriptions, embeddings, and artifact judging

The **description generator** receives the task, environment, and RM context. The **embedding model** receives only each resulting state-description text.

Use the paper’s `Qwen3-30B-A3B-Instruct-2507` model identity. Because the precise embedding invocation is unpublished, implement the agreed reconstruction: frozen inference, final-layer last non-padding-token representation, and L2 normalization, without an added instruction prompt. Record model/tokenizer revisions and extraction settings; cache by text and those settings.

The judge receives:

- Task, environment/ruleset, proposition semantics, and labeling API.
- Candidate RM and labeling code.
- Available execution evidence, identified separately from its judgment.

Blind it to the RM-generation method. Require structured RM-correct and labeling-correct decisions with reasons. Report both correct, RM only, labeling only, and neither correct.

Keep transport failures and missing judgments visible as unscored failures. Report successful scoring coverage and generation failures against the complete submitted task count. Preserve first-attempt and refined outcomes separately. Judge acceptance and deterministic validation are evidence, not proof of semantic correctness.

Generator models, endpoints, seeds, and effective sampling parameters are explicit experiment inputs; do not invent the paper’s missing endpoint settings or silently substitute models.

### 5. Complete training and zero-shot evaluation

Implement the paper’s algorithm families and documented configurations:

| Domain | Algorithm |
|---|---|
| MiniGrid/BabyAI | DQN |
| XLand-MiniGrid | Rainbow |
| Craftium | PPO |
| Meta-World | SAC, including the reported RND variation |

Condition the policy on the environment observation and active RM-state embedding. Following the reported/released behavior, combine environment and RM rewards.

Ensure replay or rollout data contains the correct current and next RM contexts. Preserve termination versus truncation handling, episode resets, checkpoint metadata, and reproducible seeds.

Encode the paper’s training budgets, task groups, three-seed comparisons, sparse-reward baselines, and XLand ablations in experiment manifests. Include the reported XLand groups beginning with `[197]`, `[212,197,260]`, and their larger extensions from the paper.

Declare training and held-out task sets before a run. Zero-shot evaluation loads frozen policy and embedding-model parameters, disables optimization and training exploration, and evaluates unseen task compositions using their own generated bundles.

Do not claim exact recovery of unpublished task partitions, wrappers, or curves. Label reconstructed choices in manifests and reports.

### 6. Substitute the existing compiler only after the baseline is complete

Use `generate_rm` and its existing `GenerationHooks.completion` callback to obtain accepted in-memory compilation results. Avoid rebuilding the compiler pipeline or reconstructing machines from incomplete reward-only text.

Convert every compiled transition into the shared runtime representation, including zero-reward state changes. Derive the paper’s transition and reward sections from those edges; preserve conjunctions, negation, and implicit self-loops.

Reuse the existing supported temporal language. Unsupported tasks remain explicit failures; do not silently approximate them or expand the language as part of this work.

Generate descriptions for the compiler’s actual states using the same downstream method. Reuse labeling code when proposition meanings are identical; otherwise regenerate it through the same labeling workflow and report that distinction.

Compare methods with matched tasks, generation budgets, downstream models, training settings, and evaluation settings. Preserve failures in reported denominators. The research objective is 100% correct RMs on the evaluated benchmark, not an assumed implementation guarantee.

## Verification

Add focused checks in `tests/test_arm_fm.py` for the critical contracts:

- Simultaneous propositions cause one RM update; irrelevant propositions and unmatched valuations self-loop.
- Persistent possession, explicit loss events, negation, episode resets, and first-match overlap warnings.
- Paper-format round trips, zero-reward transitions, compiler adaptation, and incomplete-bundle rejection.
- Bounded refinement, description/state alignment, embedding-cache identity, benchmark accounting, and frozen evaluation.

Use mocks for providers and heavyweight dependencies. No live services, model downloads, training, or full benchmark runs during implementation checks.

**Readiness check**

```bash
PYTHONPATH=app .venv/bin/python -m unittest discover -s tests -v
```

**Live validation — pending separate user approval after all implementation is complete**

- **Flow:** Generate DoorKey bundles through both RM-generation modes, embed them, execute scripted environment traces, run a short training smoke with at least one optimizer update, save/reload its checkpoint, and run frozen evaluation through Docker.
- **Expected:** Complete inspectable bundles; correct labels, rewards, and exactly one RM update per step; aligned embeddings; finite training output; reloadable checkpoints; no parameter updates during evaluation. The short smoke does not need to learn the task.
- **Can run:** The executor can use `functions.exec` and Docker once approved model access and environment assets are available. Full paper-scale experiments remain separately deferred.

## Decision records and applicable instructions

**Decision records: update existing records and create the execution record.** The main orchestrator owns these approved documentation changes during execution:

- `docs/decisions/arm-fm/reproduction-boundary.md`: replace the obsolete V1 exclusion of labeling, embeddings, and RL with baseline-first reconstruction and subsequent RM-only substitution. Preserve compiler grounding and unsupported-language restrictions. Record embedding/judge context boundaries and deferred experiments.
- `docs/decisions/arm-fm/task-and-rm-identity.md`: qualify DECLARE translation, compiler critics, and deterministic topology ownership as compiler-mode rules. Preserve one RM per task and shared-policy transfer; reference the execution record.
- `docs/decisions/arm-fm/catalogue-and-evidence.md`: distinguish missing published artifacts from newly reconstructed artifacts. Permit reconstructed XLand prompts and generated bundles without presenting them as recovered originals.
- `docs/decisions/arm-fm/rm-execution.md`: create using the current decision-record template. Record full valuations, explicit proposition meanings, relevant guards, implicit self-loops, first-match-plus-warning behavior, and exactly one update per environment step.
- `docs/decisions/index.md`: update descriptions and add the execution-record link; preserve unrelated entries.

Add dated History entries for these meaningful decisions. Correct stale enforcement references, including the nonexistent `openai_engine.py`, to actual implementations. Coders receive these records as constraints and report conflicts instead of changing intent.

Applicable instructions:

- `AGENTS.md`: preserve unrelated changes; planning is read-only; live validation requires approval.
- `.agents/conventions.md`: follow existing package, environment-document, and output conventions.
- `.agents/workflow.md`: use the established non-live readiness command.
- `/home/turbotowerlnx/Documents/Code/my-codex-config/agent-home/skills/decision-records/SKILL.md`: maintain approved living records and their index.
- `/home/turbotowerlnx/Documents/Code/my-codex-config/agent-home/skills/review-plan/SKILL.md`: preserve approved intent and provide an executable handoff.

**Main-agent memory updates:** none. Leave personal `.agents/` memory unchanged.

**Out of scope:** temporal-language expansion, unrelated compiler/UI refactoring, fabricated source artifacts, automatic live validation, full experiments before implementation completion, commits, and publishing.

The plan is finalized in chat and ready for `$code`.
