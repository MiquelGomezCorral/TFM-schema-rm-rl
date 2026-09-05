# Refactor Reward Machine Generation Orchestration

## Goal

Make the shared Reward Machine generation entry point readable as a short, behavior-preserving sequence of phases while keeping hook integration outside the proposal and compiler implementations.

## Context

`app/scripts/generate_rm.py::_run_pipeline` currently mixes validation, setup, proposal generation, console review, approval, compilation, output writing, and optional hook checks across one long function. It also invokes the existing batch APIs `propose_instructions` and `compile_approved_proposals` once per item, duplicating loops already owned by `app/src/compiler/pipeline.py`. The CLI calls `generate_rm(config)` directly, while the web runner supplies progress, approval, and completion callbacks through `GenerationHooks`; both paths must remain supported.

## Files touched

- `app/scripts/generate_rm.py`

## Requirements

- Keep `generate_rm` and `GenerationHooks` as the shared public CLI/web integration contract; preserve the existing hook constructor fields and callback signatures.
- Normalize absent hooks once, then let `GenerationHooks` encapsulate optional progress, approval, and completion dispatch. The default approval path must retain the interactive CLI prompt and accept only `y` or `yes`, case-insensitively.
- Remove `_notify_progress(hooks, ...)` and all repeated hook null checks. Extracted phase helpers must not receive hooks.
- Call `propose_instructions` exactly once with the complete instruction and priority batches, preserving input order and the existing inferred-priority behavior.
- Call `compile_approved_proposals` exactly once with the complete approved proposal batch, preserving result order and the configured MONA executable.
- Keep progress reporting at meaningful phase boundaries rather than restoring per-item callbacks inside compiler functions.
- Preserve the start/end and phase console separators, proposal review details, output-path reporting, declined-run behavior, completion callback timing after successful writes, error return codes, overwrite behavior, and exception behavior outside the existing `ProposalValidationError` handling.
- Keep one human approval for the complete proposal batch. A decline must write no Reward Machine files and return success as it does now.
- Rename uppercase function parameters such as `CONFIG` to `config`; no compatibility shim is required because repository callers pass the configuration positionally.
- Use small named functions to expose the flow. Short phase-heading comments are allowed only in the top-level orchestrator; do not add decorative banner comments or narration inside focused helpers.
- Do not add dependencies, classes beyond the existing `GenerationHooks`, a pipeline framework, an event bus, or speculative extension points.

## Steps

1. In `GenerationHooks`, add the minimal methods needed to dispatch progress, request approval, and dispatch completion. Each method owns its optional callback check; the approval method falls back to the existing CLI prompt and returns a boolean.
2. In `generate_rm`, rename `CONFIG` to `config`, normalize `hooks` to one `GenerationHooks` instance, and flatten the nested `try` blocks into one `try`/`except ProposalValidationError`/`finally` while preserving separators, reporting, and return codes.
3. Refactor `_run_pipeline` into a short top-to-bottom orchestration of output setup, environment/engine setup, batch proposal generation, review and batch approval, batch compilation, and output writing. Keep only concise phase headings as visual anchors and issue hook notifications from this orchestration boundary.
4. Extract focused private helpers for setup and console presentation where they make each phase self-contained. Reuse `_derive_output_paths`, `_get_engine`, and `_save_results` instead of introducing wrapper layers; rename their `CONFIG` parameters to `config`.
5. Replace the per-instruction proposal loop with one `propose_instructions(environment, config.instructions, engine, config.priorities)` call. Review the returned proposals in order with the existing field-level console output.
6. Replace the per-proposal compilation loop with one `compile_approved_proposals(environment, proposals, mona_executable=config.mona_executable or "mona")` call. Report successful compiled instructions afterward without invoking compilation again.
7. Remove `_notify_progress`, redundant tuple accumulation, repeated hook guards, and existing trailing whitespace. Inspect the final file to ensure the normal path is visible without following callback plumbing.

## Applicable instructions

- `AGENTS.md`: make the smallest evidence-based change, preserve unrelated work, and avoid speculative features.
- `.agents/conventions.md`: use `snake_case`, type public interfaces, and keep proposal generation separate from approved compilation.
- `.agents/decisions.md`: preserve batch human approval, the shared CLI/web hook boundary, output format, and the decision not to add automated V1 tests.
- `/home/turbotowerlnx/Documents/Code/my-codex-config/agent-home/skills/code-quality/SKILL.md`: keep orchestration separate from transformations and side effects; prefer structure and names over narrative comments.
- `/home/turbotowerlnx/.config/orca/codex-runtime-home/home/plugins/cache/ponytail/ponytail/4.9.0/skills/ponytail/SKILL.md`: reuse existing batch APIs and stop at the smallest refactor that makes ownership clear.

## Readiness check

```bash
.venv/bin/python app/main.py --help
PYTHONPATH=app .venv/bin/python -c "from src.web import create_app; assert create_app().layout is not None"
```

The CLI must still expose `generate-rm`, and the web application must construct with its callbacks and `GenerationHooks` integration intact. These checks must not contact an LLM, invoke MONA, or start the server.

## Live validation

- **Flow:** Pending user approval. Start `app/app.py`, upload `examples/multitaxi/environment.md`, submit the two eventual-delivery instructions plus one passenger-ordering instruction with priorities, generate under a new output basename, inspect the complete proposal batch, approve it, and inspect all numbered outputs.
- **Expected:** The run reports clear phase-level progress, pauses once for the complete batch approval, compiles every approved proposal in order, writes the same numbered Reward Machine files, exposes them in the UI, and completes without duplicated proposal or compilation work.
- **Can run:** Codex can start the server with `exec_command`; browser interaction is user-only. The flow requires explicit approval because it uses configured LLM credentials, invokes MONA, and writes output files.

## Main-agent memory updates

None needed. The refactor preserves the documented architecture, conventions, decisions, and workflow.

## Out of scope

- Changes to `app/src/compiler/pipeline.py`, `app/src/web/runner.py`, `app/src/web/application.py`, provider retry logic, Reward Machine normalization, CLI parser structure, CSS, dependencies, tests, or memory files.
- Exact preservation of per-item progress timing; phase-level progress is the intentional simplification.
- New abstractions for generic stages, hooks, providers, state machines, or future consumers.
