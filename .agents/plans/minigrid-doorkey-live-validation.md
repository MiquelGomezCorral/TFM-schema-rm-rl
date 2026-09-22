# Validate ARM-FM End to End on MiniGrid DoorKey

## Goal

Produce eight validated DoorKey bundles—four baseline ARM-FM and four compiler-generated RMs—then train one shared DQN policy per generation mode and save two verified checkpoints.

## Context

The generation paths and native Tianshou training exist, but review confirmed three live blockers:

- Generated MiniGrid predicates expect `env.grid` and `env.agent_pos`, while Gymnasium exposes them only through `env.unwrapped`.
- Observation encoding attempts to convert MiniGrid’s textual `mission` field to `float`.
- The default one-million-entry replay buffer is excessive for 5120-dimensional smoke-test embeddings.

Generation uses the currently configured OpenCode provider. Embeddings use the local Qwen3.8 GGUF server as an explicitly non-paper validation substitute.

## Files Touched

- `app/src/arm_fm/runtime.py`
- `app/src/arm_fm/training.py`
- `tests/test_arm_fm.py`

The main orchestrator, rather than the coder, persists this plan at `.agents/plans/minigrid-doorkey-live-validation.md`.

## Requirements

- Use `RM_RL_env`, seed `42`, `MiniGrid-DoorKey-8x8-v0`, and the four exact requested tasks.
- Generate baseline bundles first, followed by compiler bundles. The compiler changes only RM generation.
- Use a fresh run directory: `outputs/arm-fm-doorkey-live/<run-id>/`.
- Fail fast unless configuration resolves to `opencode` with a configured model. Never print credentials or silently fall back to OpenAI.
- Preserve failed generation attempts in separate directories. Do not overwrite them during retries.
- Every complete bundle must contain an accepted RM, executable labeling functions, one description and embedding per state, attempts, provenance, and execution evidence.
- Labeling evaluates a complete valuation once per snapshot; the RM advances at most once.
- Local embeddings receive only state-description text. Record that Qwen3.8-27B GGUF embeddings are a validation substitute rather than the paper’s Qwen3-30B embeddings.
- Train two shared DQN policies: four baseline RMs together and four compiler RMs together.
- Do not claim performance, zero-shot generalization, or paper-equivalent embedding quality.

## Steps

1. **Persist and dispatch**
   - Persist this exact plan.
   - Launch one retained worker through Orca.
   - The worker first reproduces the known runtime and observation failures and reports evidence to the coordinator. The coordinator then authorizes the fixes below.

2. **Correct the MiniGrid labeling surface**
   - In `_LabelingContext` in `runtime.py`, resolve ordinary wrapper attributes first and fall back to `environment.unwrapped` for MiniGrid state fields.
   - Keep episode memory on the labeling context.
   - Add a real seeded MiniGrid check proving generated-style predicates can access `grid`, `agent_pos`, and `carrying`.

3. **Correct smoke-training inputs**
   - In `_observation_array` in `training.py`, flatten numeric observation fields and ignore nonnumeric metadata such as MiniGrid’s mission string.
   - Cap the effective replay capacity to `min(config.replay_capacity, config.total_timesteps)` before training and save that effective value in the checkpoint configuration.
   - Add focused checks for a real DoorKey reset and bounded replay configuration.

4. **Generate eight bundles**
   - Use `examples/arm-fm/minigrid-doorkey/environment.md`.
   - Generate task IDs `dk-1`, `dk-a`, `dk-b`, and `dk-c` individually in `arm-fm` mode, then in `compiler` mode.
   - Compiler intermediate RM files must use unique flat names under `outputs/`, because `--output` rejects directories.
   - Permit one clean rerun only after diagnosing a transient provider failure.

5. **Create local embeddings**
   - Start a dedicated embedding-only llama.cpp process on port `8081` using the supplied Qwen3.8 GGUF, existing GPU/KV/context settings, and `--embeddings --pooling last`.
   - Verify `/health`, `/v1/models`, and one embedding probe.
   - Use a minimal validation sidecar under the run directory. Send one state description at a time, verify model identity, dimension, finiteness, and response ordering, then L2-normalize.
   - Save through `ArtifactBundle`, set `stage_status["embeddings"] = "complete"`, and record endpoint/model/pooling/dimension/normalization provenance. No invented `validation` stage is needed.
   - Stop only the server process launched for this run before DQN training.

6. **Validate semantics**
   - Require `validate(require_complete=True)` and exact RM-state/description/embedding alignment.
   - Use fresh runtimes for:
     - happy path: initial → key → door → goal;
     - loss path: initial → key → key lost before opening;
     - door-before-key violation;
     - goal-before-door violation.
   - Reset between scenarios. For each snapshot, call labeling evaluation once and RM stepping once so `previous_valuation` is not mutated twice.
   - Verify ordered completion, lack of premature completion, expected `key_lost`, and one RM transition per snapshot.

7. **Train two shared policies**
   - Put one manifest inside each mode directory. Bundle paths are relative entries `dk-1`, `dk-a`, `dk-b`, and `dk-c`; all use the full DoorKey environment ID and `split: train`.
   - Run `train-larm` with each manifest, `--domain MiniGrid-DoorKey-8x8-v0`, `--total-timesteps 80128`, and seed `42`.
   - The 80,000-step warmup followed by 128 vector transitions should produce 32 optimizer steps.
   - Verify strict checkpoint loading, DQN identity, four task IDs, requested timestep count, bounded effective replay capacity, and nonempty positive-step optimizer state.

8. **Report**
   - Return the artifact tree, exact commands, eight bundle outcomes, semantic traces, embedding metadata, checkpoint evidence, fixes made, and remaining blockers.
   - If embedding or training remains externally impossible, preserve all successful generation artifacts and report the last successful stage and exact next action.

## Applicable Instructions

- `AGENTS.md`: preserve unrelated work, use the simplest root-cause fix, verify with real-flow evidence, and do not commit or publish.
- `python-coding/SKILL.md`: use `RM_RL_env`, `uv` for dependency installation, package-root imports, and existing project conventions.
- `docs/decisions/arm-fm/reproduction-boundary.md`: baseline first, compiler replaces only RM generation, in-process labels, and Tianshou-native training.
- `docs/decisions/arm-fm/rm-execution.md`: complete valuations, implicit self-loops, and exactly one RM update per environment step.
- `.agents/workflow.md`: live provider and environment execution requires explicit approval.

## Readiness Check

```bash
conda run -n RM_RL_env env PYTHONPATH=app \
  python -m unittest discover -s tests -p 'test_arm_fm.py' -v
```

## Live Validation

**Flow:** Generate four baseline and four compiler DoorKey bundles, create local embeddings, execute the four semantic scenarios, and train two shared DQN smoke policies.

**Expected:** Eight complete bundles, correct ordered RM behavior, normalized 5120-dimensional validation embeddings, and two strict-loadable checkpoints containing optimizer updates.

**Can run:** Pending explicit `$code` authorization. Run through the retained Orca worker with configured OpenCode access and localhost llama.cpp access.

## Main-Agent Memory Updates

None.

## Decision Records

**Assessment:** No change.

Applicable records:

- `docs/decisions/arm-fm/reproduction-boundary.md`
- `docs/decisions/arm-fm/task-and-rm-identity.md`
- `docs/decisions/arm-fm/rm-execution.md`
- `docs/decisions/arm-fm/catalogue-and-evidence.md`

Preserve baseline-first integration, one RM per task, identical downstream processing, complete valuations, single RM updates, and explicit reconstructed provenance. The local embedding substitute does not change the paper-faithful Qwen3-30B architecture decision.

## Out of Scope

- Figure 11 reproduction or aggregate judging
- Full paper training budgets or performance comparison
- Zero-shot evaluation
- Other environments
- Docker
- Replacing the canonical Qwen3-30B embedding implementation
- UI work, unrelated cleanup, commits, or pushes

The plan is finalized in chat and ready for `$code`.
