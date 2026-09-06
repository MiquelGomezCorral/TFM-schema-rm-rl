## Planning Mode

Full.

## Goal

Add a modular local Dash UI that submits multiple instructions to the existing Reward Machine pipeline, preserves human approval, shows progress logs, and displays each generated RM as text and a synchronized graph.

## Context

- The CLI supports repeated instructions and priorities at `app/main.py:42`.
- Generation, approval, compilation, and writing are currently combined in `app/scripts/generate_rm.py:21`.
- Proposal and compilation APIs are already separated at `app/src/compiler/pipeline.py:49` and `app/src/compiler/pipeline.py:120`.
- `CompilationResult` exposes serialized text and the normalized RM structure at `app/src/compiler/pipeline.py:39`.
- The reference Dash/Cytoscape viewer provides reusable visual styling, but its graph-editor behavior and data model do not fit this read-only UI.
- `Configuration.OUTPUT_PATH` must not be reconstructed by the UI. The completion hook must provide the authoritative paths.

## Files Touched

- `app/app.py`
- `app/scripts/generate_rm.py`
- `app/scripts/__init__.py`
- `app/src/web/__init__.py`
- `app/src/web/application.py`
- `app/src/web/components.py`
- `app/src/web/runner.py`
- `app/src/web/visualization.py`
- `app/assets/app.css`
- `requirements.txt`
- `pyproject.toml`
- `README.md`

## Requirements

- Support uploaded UTF-8 Markdown and directly pasted Markdown.
- An upload populates the editable Markdown textarea; its current text is authoritative.
- Support add/remove instruction rows with one priority selector per instruction.
- Default each priority to `infer`.
- Accept one base output filename and preserve existing numbered-output behavior.
- Permit one active local run at a time.
- Keep the existing batch approval requirement.
- Show simple progress and proposal-review details as log lines, not structured cards.
- Display completed outputs using the exact text and paths returned by the pipeline.
- Synchronize the selected output, text, and graph.
- Render initial, final, and rejecting states from the in-memory `RewardMachineStructure`.
- Render explicit transitions only and explain that omitted transitions are zero-reward self-loops.
- Preserve existing CLI behavior when no web hooks are supplied.
- Do not expose API keys or accept credentials through the UI.

## Steps

1. **Introduce the narrow integration hook**

   In `app/scripts/generate_rm.py`, add an optional `GenerationHooks` dataclass accepted by `generate_rm`.

   It must support:

   - A progress callback receiving plain messages.
   - An approval callback receiving the complete proposal tuple and returning `bool`.
   - A completion callback receiving `CompilationResult` values and their authoritative output paths.

   Keep all existing terminal prints. When no custom approval callback exists, retain the current blocking `[y/N]` prompt.

2. **Report existing pipeline boundaries**

   Add progress notifications around output validation, environment setup, each proposal, proposal review, each compilation, writing, completion, and handled proposal failure.

   Call the completion hook only after `_save_results` succeeds. Do not change proposal generation, compilation, output naming, return codes, or partial-write behavior.

3. **Export the hook**

   Export `GenerationHooks` from `app/scripts/__init__.py` alongside `generate_rm`.

4. **Build the run controller**

   In `app/src/web/runner.py`, implement a `RunController` that owns:

   - One worker thread.
   - A lock-protected status, log, proposals, results, and output paths.
   - A `threading.Event` for approval.
   - States equivalent to idle, running, awaiting approval, declined, completed, and failed.
   - Immutable snapshots for Dash callbacks.

   The worker must create a temporary directory, write the submitted environment Markdown there, construct `Configuration`, and call `generate_rm(config, hooks=...)`.

   Preserve the uploaded basename safely for the environment title fallback; use `environment.md` for pasted content. Always clean up the temporary directory.

5. **Implement approval and completion hooks**

   The approval hook must append each proposal’s instruction, pattern, propositions, priority, LTLf, and reward behavior as plain log lines, mark the run as awaiting approval, and wait for Approve or Decline.

   The completion hook must retain the actual `CompilationResult` objects and supplied paths. Never calculate output paths in the web package.

6. **Implement visualization conversion**

   In `app/src/web/visualization.py`, convert `RewardMachineStructure` directly into Cytoscape elements.

   Include every declared state and explicit transition. Apply combined classes where applicable for initial, final, and rejecting states. Use unique edge IDs and labels containing the guard and reward.

7. **Create reusable components**

   In `app/src/web/components.py`, define layout factories for:

   - Environment upload and textarea.
   - Dynamic instruction/priority rows.
   - Output filename and Generate button.
   - Status and scrolling log panel.
   - Approve and Decline controls.
   - Output selector and raw text panel.
   - Read-only Cytoscape canvas.

   Use Dash pattern-matching IDs for instruction rows.

8. **Construct the Dash application**

   In `app/src/web/application.py`, implement `create_app()`.

   Instantiate one `RunController`, explicitly configure `app/assets`, load Cytoscape’s extra layouts, and register focused callbacks for uploads, instruction rows, run start, approval, polling, and selected-result rendering.

   Use `dcc.Interval` for polling. Do not redirect global stdout or add Diskcache/Celery.

9. **Add the entry point**

   Keep `app/app.py` minimal: load `.env`, call `create_app()`, expose the Dash instance, and run it with debugging and the reloader disabled.

10. **Add responsive styling**

    Adapt the reference viewer’s CSS into `app/assets/app.css`.

    Use a top input region and a lower approximately 40/60 output-to-graph split. Add accessible focus states, `aria-live` status behavior, reduced-motion handling, scrollable logs, and a stacked mobile layout.

11. **Declare dependencies**

    Add `dash>=4,<5` and `dash-cytoscape` to both `requirements.txt` and `pyproject.toml`. Do not add a background-job dependency.

12. **Document usage**

    Add a focused web UI section to `README.md` covering installation, `python app/app.py`, provider/MONA prerequisites, batch approval, output naming, and local single-run limitations.

    Preserve the existing uncommitted environment-name edits in `README.md`.

## Applicable Instructions

- `/home/turbotowerlnx/.config/opencode/AGENTS.md`: use the smallest correct change and preserve unrelated worktree edits.
- `AGENTS.md`: retain the Python 3.13 compiler architecture and stop at RM generation.
- `.agents/conventions.md`: use typed public Python interfaces and keep proposal generation separate from approved compilation.
- `.agents/decisions.md`: preserve mandatory human approval, numeric RM output, and the no-automated-tests V1 decision.
- `.agents/workflow.md`: do not run the representative OpenAI/MONA flow without explicit approval.

## Readiness Check

After installing declared dependencies, run only:

```bash
PYTHONPATH=app python -c "from src.web import create_app; assert create_app().layout is not None"
```

This must construct the layout and register callbacks without calling an LLM, invoking MONA, or starting the server.

## Live Validation

**Flow:** Start `python app/app.py`; upload `examples/multitaxi/environment.md`; enter the three documented instructions with priorities `none`, `none`, and `hard`; use a new base filename; confirm logs stop for batch approval; approve; inspect all three selected text/graph results and the responsive layout.

**Expected:** No compilation or output occurs before approval. After approval, the existing pipeline writes three numbered outputs to its configured paths, and each selector option displays the corresponding exact RM text and graph.

**Can run:** User-only and pending explicit live-run approval. Requires configured provider credentials, model, and MONA.

## Main-Agent Memory Updates

- `.agents/architecture.md`: add `app/app.py`, `app/src/web/`, assets, and the narrow `GenerationHooks` boundary; correct stale module paths.
- `.agents/decisions.md`: remove UI from the superseded exclusion and record the local, single-run, thin-adapter decision.
- `.agents/conventions.md`: replace stale section-based serialization rules with the numeric semicolon format.
- `.agents/workflow.md`: add web installation, launch, readiness, and pending live-validation instructions.
- Do not change `.agents/glossary.md` or `.agents/known-errors.md`.

These memory changes are main-agent maintenance, not coder implementation tasks.

## Out Of Scope

- Changes to `app/main.py`, `app/src/compiler/`, engines, models, serializers, or dependency submodules.
- Production hosting, authentication, multi-user isolation, Celery, Redis, or persistent jobs.
- Pipeline stdout capture.
- Graph editing, raw DFA display, structured proposal cards, or implicit self-loop synthesis.
- Overwrite or pre-approval cancellation controls.
- Correcting `Configuration.WORKSPACE_PATH` or changing output locations.
- Automated tests.
- Modifying the source under `../.pre/web-visualization`.
- Commits, pushes, or live validation.

The plan is finalized in chat and ready for `/code`.
