# Automated Dual-Critic Task-to-RM Refinement

## Planning mode

Full.

## Goal

Automatically refine each natural-language task into a critic-approved, deterministically compiled Reward Machine within three attempts, without human approval, while showing timed progress in CLI and web logs.

## Context

The current model emits constrained IBM/DECLARE clauses, a human approves them, and LTLf/MONA constructs the RM. The new flow retains deterministic compiler ownership but replaces approval with two optional automated gates:

`proposal generator → task critic → compiler → RM critic`

The paper’s direct FM-generated RMs and labeling functions remain intentionally excluded.

## Files touched

- `app/src/prompts/prompts.py`
- `app/src/prompts/__init__.py`
- `app/src/prompts/reward-ltlf-creator.system.md`
- `app/src/prompts/reward-ltlf-creator.user.md`
- `app/src/prompts/reward-ltlf-reviewer.system.md`
- `app/src/prompts/reward-ltlf-reviewer.user.md`
- `app/src/prompts/reward-machine-reviewer.system.md` — new
- `app/src/prompts/reward-machine-reviewer.user.md` — new
- `app/src/engines/openai_engine.py`
- `app/src/engines/__init__.py`
- `app/src/compiler/pipeline.py`
- `app/src/compiler/__init__.py`
- `app/scripts/generate_rm.py`
- `app/src/config/config.py`
- `app/main.py`
- `app/src/web/components.py`
- `app/src/web/application.py`
- `app/src/web/runner.py`
- `app/assets/app.css`
- `tests/test_prompts.py`
- `tests/test_generation.py` — new
- `tests/test_web.py` — new
- `README.md`
- `docs/LTLF_TASK_LANGUAGE.md`
- `docs/decisions/arm-fm/task-and-rm-identity.md`
- `docs/decisions/arm-fm/reproduction-boundary.md`

## Requirements

- One task produces one RM; clauses within a task remain conjunctive and separate tasks remain independent.
- Both critics default to enabled; either may be disabled, but disabling both is invalid.
- All roles share the configured provider and model.
- Each task gets at most three generator attempts.
- Task-critic rejection skips compilation. RM-critic rejection regenerates and recompiles.
- Every enabled critic must accept the same attempt.
- Critics return strict `{accepted: bool, feedback: str}` output. Feedback is always nonempty; critics never return corrected artifacts.
- The task critic sees environment Markdown, original task, and IBM proposal.
- The independent RM critic sees environment Markdown, original task, and serialized RM only.
- Later generator attempts receive every prior proposal, compiled RM when available, failure source, and feedback.
- Failed multi-task generation writes no output. Already accepted results remain in memory until the whole batch succeeds.
- Existing numbered `.rm` output naming remains unchanged.
- Runtime histories are not persisted.
- Configure the OpenAI-compatible client with `max_retries=0`; the application owns retry accounting. [Official SDK behavior](https://github.com/openai/openai-python#retries)
- Retryable provider failures, refusals, malformed outputs, local proposal failures, and candidate-caused compiler `ValueError`s consume an attempt.
- Invalid configuration/input, authentication/permission/request failures, missing MONA, and MONA process/runtime failures stop immediately.
- Progress entries use `time.monotonic()` and the exact prefix `[total 12.345s | step 1.234s]`.
- The first entry’s step duration equals its total duration.
- Decorative CLI separators and rendered proposal/RM bodies need not be timestamped; every shared progress entry must be timestamped exactly once.

## Steps

1. In `app/src/prompts/`, wire the existing generator prompt into runtime, add bounded refinement history to its user prompt, convert the current reviewer into the task critic, and add the independent RM-critic system/user pair. Keep all supplied environment, candidates, RMs, and feedback explicitly marked as untrusted data.

2. In `app/src/engines/openai_engine.py`, centralize each provider’s structured request operation so generator and critic calls share transport code. Add `CriticResult`, strict critic-response validation, proposal and RM review methods, and public SDK exception/status classification without message matching. Preserve both OpenAI Responses and OpenCode-compatible Chat Completions behavior.

3. In `app/src/compiler/pipeline.py`, replace batch-oriented `propose_tasks` and approval-oriented `compile_approved_proposals` with single-task `propose_task` and `compile_proposal` operations suited to the refinement loop. Keep existing clause construction, LTLf serialization, DFA normalization, RM composition, and result types unchanged. Update package exports without legacy aliases.

4. In `app/scripts/generate_rm.py`, implement the sequential three-attempt loop. Record bounded attempt history, run only enabled critics, classify failures, retain accepted results, and call `_save_results` only after every task succeeds. Generation is atomic with respect to task failure; do not add transactional filesystem writes for later I/O errors.

5. Add one private run-scoped progress formatter in `generate_rm.py`. It stores start and previous timestamps, formats total/step durations, prints the formatted progress message for CLI use, and forwards the same string through `GenerationHooks`. Remove approval handling from `GenerationHooks`; keep progress and completion callbacks.

6. Add `task_critic: bool = True` and `rm_critic: bool = True` to `Configuration`. Validate that at least one is enabled. Expose them through `argparse.BooleanOptionalAction` as `--[no-]task-critic` and `--[no-]rm-critic`. Do not add environment variables or a configurable attempt count.

7. Simplify `RunController` to `IDLE`, `RUNNING`, `COMPLETED`, and `FAILED`. Remove approval events, decisions, methods, proposal snapshots, and untimed lifecycle log writes. Pass critic selection into the copied run request and rely on shared timed progress messages for the web log.

8. Replace approval buttons in UI panel 03 with `critic-options`, a two-value checklist defaulting to both critics. Validate at least one selection, copy it into the run request, and disable its option entries while active. Remove the approval callback and CSS; retain existing input locking, status display, output selector, RM text, and graph synchronization.

9. Update documentation to describe automatic critic acceptance, three attempts, critic controls, atomic generation behavior, timed logs, and the intentional deviation from ARM-FM. Remove human-approval language while preserving deterministic compiler and no-labeling-function boundaries.

10. Update the two existing decision records. Do not create or re-index a new concern.

11. Extend prompt tests and add focused generation/web tests using standard-library `unittest` and mocks. Do not call a live model or MONA.

## Applicable instructions

- `AGENTS.md`: preserve unrelated dirty-worktree changes, use focused patches, validate with fresh evidence, and require approval for live validation.
- `.agents/skills/decision-records/SKILL.md`: revise existing concern records rather than creating duplicates; never relax protected invariants silently.
- `.agents/conventions.md`: preserve strict proposition parsing, deterministic state naming, implicit zero-reward self-loops, and numeric RM serialization.
- `/home/turbotowerlnx/Documents/Code/my-codex-config/agent-home/skills/review-plan/SKILL.md`: execute this approved full plan without reopening settled decisions.
- `/home/turbotowerlnx/.config/orca/codex-runtime-home/home/plugins/cache/ponytail/ponytail/4.9.0/skills/ponytail/SKILL.md`: reuse existing boundaries, add no dependency or compatibility layer, and leave one focused runnable check.

## Readiness check

```bash
PYTHONPATH=app .venv/bin/python -m unittest discover -s tests -v
```

The tests must cover:

- First-attempt acceptance.
- Rejection and feedback-driven refinement from each critic.
- Three-attempt exhaustion and no writes.
- Complete bounded-history propagation.
- Each critic toggle and invalid both-disabled configuration.
- Retryable versus immediate failures.
- Multi-task numbering and generation atomicity.
- Deterministic total/step timestamps with no duplicate prefixes.
- CLI critic flags and web layout/callback construction.
- Removal of approval controls and preservation of output selection.

## Live validation

Flow: Pending approval, run the MultiTaxi CLI flow with both critics enabled, one composite task, a fresh output name, configured model credentials, and MONA available.

Expected: No approval prompt appears; logs show task, attempt, critic stages, total/step timings; both critics accept within three attempts; one RM is written and remains compatible with the existing serializer and graph.

Can run: The executor may use the repository shell through `exec_command` only after explicit user approval for the live model/MONA call.

## Main-agent memory updates

These are performed by the main agent after implementation, not by the coder:

- `.agents/architecture.md`: replace the human-approval flow with generator → task critic → compiler → RM critic and document shared timed progress.
- `.agents/decisions.md`: record bounded automated acceptance, critic controls, task-specific RMs, and focused automated tests.
- `.agents/workflow.md`: replace approval-based readiness/live instructions with critic-based validation and timed-log expectations.

Decision records: update — replace human approval with bounded automated critic acceptance while preserving deterministic compiler ownership.

Record changes:

- `docs/decisions/arm-fm/task-and-rm-identity.md`: update Current decisions, Protected invariants, Rationale and tradeoffs, and Enforcement.
- `docs/decisions/arm-fm/reproduction-boundary.md`: update Current decisions, Protected invariants, and Enforcement.
- `docs/decisions/index.md`: none.

Enforcement: structured schemas, local validation, bounded orchestration tests, compiler invariants, and CLI/UI configuration checks.

Reconciliation: Pending — the approved record changes are not yet implemented or freshly reviewed.

## Out of scope

- Direct FM-generated RM topology or rewards.
- Labeling-function generator or critic.
- Executing model-generated Python.
- RL training, policies, state embeddings, or deployment.
- Separate models per role.
- Parallel task or critic execution.
- Persisted critic transcripts or metrics.
- Transactional filesystem output machinery.
- Legacy approval mode or compatibility aliases.
- Changes to `docs/ARM-FM/ARM-FM.md`, dependency submodules, or unrelated dirty files.

The plan is finalized in chat and ready for `$code`.
