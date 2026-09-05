# Finalized Plan: Structured Run Progress and Persistent Diagnostics

## Planning mode

Full.

## Goal

Provide a structured, navigable six-stage Run status while preserving detailed plain-text logging in the UI and persistent per-run log files for both CLI and web executions.

## Context

The pipeline currently executes tasks sequentially with up to three attempts, emits timed strings through `GenerationHooks`, and writes outputs only after every task is accepted. Dash stores those strings and polls every 500 ms, but has no structured stage identity.

Repository review confirmed:

- The task critic can run before LTLf construction because it consumes only the validated structured interpretation.
- `propose_task()` and `compile_proposal()` currently combine the desired internal stages and are exported APIs.
- `Configuration` already owns runtime paths, and `.gitignore` already excludes `logs/*`.
- Existing colors provide blue accent, green success, gray muted, and red error tones.
- The current non-live baseline is 22 passing tests.

## Files touched

- `app/src/config/config.py`
- `app/src/compiler/pipeline.py`
- `app/src/compiler/__init__.py`
- `app/scripts/generate_rm.py`
- `app/src/web/runner.py`
- `app/src/web/components.py`
- `app/src/web/application.py`
- `app/assets/icons/chevron-right.svg`
- `app/assets/00-tailwind.css`
- `tests/test_generation.py`
- `tests/test_pipeline_orchestration.py`
- `tests/test_web.py`
- `README.md`
- `docs/decisions/generation/run-observability.md`
- `docs/decisions/index.md`

## Requirements

- Execute and display these stages in order:
  1. Generate and validate structured LLM interpretation.
  2. Run task critic, or mark it skipped.
  3. Materialize IBM DECLARE templates and LTLf.
  4. Compile LTLf to DFA through FL-AT/MONA.
  5. Normalize, compose, and serialize the Reward Machine.
  6. Run RM critic, or mark it skipped.
- Preserve sequential tasks, independent RMs, three attempts per task, critic acceptance rules, retry history, and atomic batch output.
- Keep `propose_task()` and `compile_proposal()` behavior available through compatibility wrappers.
- Add shared `PipelineStep`, `StepState`, and immutable `ProgressEvent` types. An event carries task index, attempt, step, state, elapsed stage seconds, and optional failure detail.
- Preserve `GenerationHooks.progress: Callable[[str], None]`; add an optional structured event callback. Do not parse log text in the web layer.
- Create one unique UTC-timestamped file under `Configuration.LOGS_PATH` for every started CLI or web run, including failed runs.
- Use stdlib `logging` with run-scoped handlers and guaranteed handler cleanup. Do not use global `basicConfig`.
- File, console, and Log tab use the same plain-text record formatting without ANSI sequences.
- Lifecycle records retain `[total … | step …]`. Full artifacts appear as readable, labeled, untruncated multiline blocks:
  - validated proposal JSON;
  - critic verdict and feedback;
  - per-clause LTLf;
  - complete pretty-printed DFA data;
  - exact serialized RM.
- Do not explicitly log credentials, environment variables, headers, full prompts, or raw provider response objects.
- Steps is the default tab; Log remains monospaced, scrollable, and preserves multiline whitespace.
- Stage presentation combines color, icon, and text:
  - blue `Running`;
  - green `Completed`;
  - gray `Pending` or `Skipped`;
  - red `Failed`.
- Show task text and:
  - pending: `Task N of M · Not started`;
  - active: `Task N of M · Attempt N of 3`;
  - accepted: `Task N of M · Accepted on attempt N of 3`;
  - exhausted: `Task N of M · Failed on attempt 3 of 3`.
- Retain only the latest retry reason per task, including after eventual success.
- For multiple tasks, render previous/next buttons and at most five task dots. Center the window around the selected task where possible; show a leading or trailing ellipsis when hidden tasks exist.
- Task dots use overall task state colors. Selection has a separate visible focus/selection treatment.
- Hide navigation for one task but retain `Task 1 of 1`.
- Smart-follow rule: when the active task changes, follow it only if the selected task was the previous active task; preserve any manually browsed task otherwise.
- Retryable failures temporarily mark the responsible stage failed; beginning the next attempt resets that task’s enabled stages and durations while retaining its latest note.
- Setup failures leave task stages pending. Output-write failures leave accepted tasks completed but mark the overall run failed.

## Steps

1. In `Configuration`, add `LOGS_PATH = WORKSPACE_PATH / "logs"` and include it in existing directory creation. Keep the existing ignore rules unchanged.

2. In `pipeline.py`, extract three focused operations:
   - materialize a `Proposal` and LTLf from validated selections;
   - compile proposal clauses into DFAs;
   - build `CompilationResult` from those DFAs.
   
   Keep `propose_task()` and `compile_proposal()` as thin wrappers over these operations and export the new operations through `src.compiler`.

3. In `generate_rm.py`:
   - Add the six-step enums and structured event dataclass.
   - Extend `GenerationHooks` with optional structured notification.
   - Extend `_Progress` into the run-scoped logging boundary: monotonic lifecycle timing, stage timing, artifact formatting, file/console/hook fan-out, and handler cleanup.
   - Name logs `run-<UTC date-time with microseconds>.log` and emit the absolute path as the first record.
   - Reorder each attempt so the engine returns validated selections, the task critic reviews their JSON, and only accepted selections are converted to LTLf.
   - Emit running and completed/failed events around every stage. Attach stage duration only to completed or failed events.
   - Log each stage artifact immediately after production.
   - Preserve existing history payloads and add precise source names for LLM, task critic, LTLf, DFA, RM construction, and RM critic failures.
   - Log unexpected setup/output errors once and re-raise them, preserving current exception behavior while ensuring failed-run diagnostics survive.

4. In `runner.py`:
   - Add immutable step/task snapshots to `RunSnapshot`.
   - Initialize all submitted tasks when `start()` succeeds; initialize disabled critics as skipped.
   - Consume structured events under the existing lock, update the relevant task, reset it on a higher attempt number, retain its latest failure note, and derive the active task index.
   - Continue storing every formatted string for the Log tab.
   - Preserve single-active-run thread behavior and completed result retention.

5. In `components.py`:
   - Replace the bare log with native Dash `Steps` and `Log` tabs.
   - Add the task header, attempt text, six rows, retry note, navigator, ellipses, and accessible labels.
   - Add one local right-chevron SVG and mirror it for the left button using the existing icon-mask helper.
   - Use existing theme colors and Tailwind utilities; do not add a new component library or custom styling layer.
   - Add one `dcc.Store` holding selected and last-active task indexes.

6. In `application.py`:
   - Extend the existing polling callback to render snapshots and process interval, chevron, and task-dot triggers.
   - Clamp navigation at the first and last tasks.
   - Compute the five-dot window as `start = min(max(selected - 2, 0), max(total - 5, 0))`.
   - Apply the smart-follow rule using the selection store.
   - Reset selection to the first task for a new run.
   - Keep existing input locking, result selection, RM text, and graph behavior unchanged.

7. Rebuild `app/assets/00-tailwind.css` after component classes are final.

8. Extend the existing tests:
   - `test_generation.py`: timing, event payloads, log creation, handler cleanup, multiline formatting, and failed-run persistence.
   - `test_pipeline_orchestration.py`: exact six-stage order, critic-before-LTLf, wrappers, optional critics, retries, exhaustion, artifact content, and atomic output.
   - `test_web.py`: snapshot reduction, colors and labels, default Steps tab, preserved Log tab, five-dot overflow, chevrons, selection boundaries, and smart follow.
   - Patch `LOGS_PATH` to temporary directories; never call a real provider or MONA.

9. Update `README.md` with stage order, task navigation, log contents, log location, privacy boundary, and manual deletion policy.

10. Create `docs/decisions/generation/run-observability.md` and index it. Record the shared typed-event boundary, thin web adapter, dual Steps/Log presentation, local persistent diagnostics, manual retention, and secret-exclusion policy.

## Applicable instructions

- `AGENTS.md`: keep changes focused, preserve unrelated dirty-worktree changes, use the simplest existing patterns, and do not run live validation without approval.
- `.agents/decisions.md`: keep Dash a thin single-run adapter over `generate_rm`; do not duplicate compiler or critic behavior in web code.
- `docs/decisions/arm-fm/task-and-rm-identity.md`: preserve task-specific RMs, critic acceptance of the same attempt, deterministic compiler ownership, and atomic batch output.
- `decision-records/SKILL.md`: create and index a durable record because observability and retention cross compiler, CLI, and web boundaries.
- `ponytail/SKILL.md`: use stdlib logging, one event contract, existing theme utilities, and no speculative framework or retention subsystem.

## Readiness check

```bash
PYTHONPATH=app .venv/bin/python -m unittest discover -s tests -v
```

The CSS build is an implementation step, not an additional readiness gate.

## Live validation

- **Flow:** Pending explicit approval. Start `python app/app.py`, submit three MultiTaxi tasks with both critics enabled and a fresh output name, browse completed/current/pending tasks while generation runs, inspect full Log artifacts, and open the emitted local log file.
- **Expected:** Sequential smart-follow works; six stages, attempts, durations, colors, skipped states, and task dots remain accurate; UI and file artifacts are readable and complete; the run produces three numbered RMs only after all tasks pass.
- **Can run:** Codex can start and monitor the server with `exec_command` after approval; browser interaction is user-only and requires configured provider credentials plus MONA.

## Main-agent memory updates

These are post-implementation main-agent updates, not coder tasks:

- `.agents/architecture.md`: record the six-stage flow and shared event/logger fan-out.
- `.agents/decisions.md`: record Steps plus preserved Log, sequential task navigation, and retained local diagnostics.
- `.agents/workflow.md`: record the updated readiness coverage and pending representative live flow.

## Out of scope

- Parallel task execution.
- Cancellation or pause controls.
- Persistent job/run-history UI.
- Log download, deletion, search, or filtering controls.
- Automatic rotation or retention limits.
- Expandable artifacts inside Steps.
- New logging, UI, or concurrency dependencies.
- Authentication, hosting, multi-user isolation, or production logging.
- Unrelated cleanup or modification of existing user changes.
