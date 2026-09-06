## Planning Mode

Brief corrective change.

## Goal

Ensure an uploaded filename is used only while the textarea still represents that upload, preventing stale filename metadata from influencing the environment title sent to the LLM.

## Context

`start_run()` always forwards `environment-upload.filename` at `app/src/web/application.py:73`, even after the textarea changes. The runner uses it as the temporary source filename at `app/src/web/runner.py:138`.

For Markdown without an H1, the filename determines `EnvironmentDescription.title` at `app/src/models/environment.py:115`, which is included in the LLM request at `app/src/engines/openai_engine.py:268`.

The separate `binascii.Error` finding requires no fix: CPython 3.13 defines it as a `ValueError` subclass, already covered by `app/src/web/application.py:36`.

## Files Touched

- `app/src/web/application.py`

## Requirements

- Preserve the uploaded filename when the textarea still contains the uploaded Markdown.
- Treat edited or replaced textarea content as pasted input and pass no uploaded filename.
- Normalize CRLF/CR line endings before comparison to avoid classifying browser-normalized text as edited.
- Continue using `environment.md` as the runner fallback.
- Keep malformed Base64 handling inline through the existing `ValueError` branch.
- Do not change pipeline, runner, UI layout, dependencies, or public behavior elsewhere.

## Steps

1. Extract upload decoding from `load_environment()` into a private `_decode_uploaded_markdown(contents)` helper.
2. Add a private helper that compares current Markdown with decoded upload content after normalizing line endings.
3. Return the uploaded filename only when the normalized contents match and both upload contents and filename exist.
4. Return `None` for changed content, missing upload metadata, malformed Base64, or invalid UTF-8.
5. Add `environment-upload.contents` as `State` to the Generate callback.
6. Resolve the source filename before calling `controller.start()` and pass only that resolved value.
7. Keep `_safe_environment_filename()` in `runner.py` as the authoritative path-sanitization boundary.
8. Do not add an explicit `binascii.Error` handler because it would duplicate the existing `ValueError` coverage.

## Applicable Instructions

- System plan mode: remain read-only until `/code`.
- `/home/turbotowerlnx/.config/opencode/AGENTS.md`: make the smallest correct change and avoid speculative compatibility code.
- `.agents/conventions.md`: retain typed interfaces and existing module boundaries.
- `.agents/decisions.md`: preserve pipeline behavior and avoid automated tests.
- `.agents/workflow.md`: do not run the external LLM/MONA flow without approval.

## Readiness Check

Run one non-live smoke command that:

- Constructs the Dash application.
- Confirms unchanged uploaded content retains its filename.
- Confirms edited content resolves to `None`.
- Confirms malformed Base64 resolves safely without escaping as an error.

Then run `git diff --check`.

## Live Validation

**Flow:** In the local UI, upload environment Markdown without an H1, replace its textarea content with a different valid no-H1 environment, and start generation with a new output name.

**Expected:** The current textarea content enters the pipeline and the original uploaded basename is not reused as its environment-title fallback.

**Can run:** User-only and pending approval; completing generation requires configured provider credentials and MONA.

## Main-Agent Memory Updates

None. This correction does not change architecture, conventions, workflow, or closed decisions.

## Out Of Scope

- Changes to `runner.py`, pipeline hooks, compiler code, or environment parsing.
- Explicit `binascii.Error` handling.
- New stores, dependencies, automated tests, documentation, or memory changes.
- UI redesign, live LLM/MONA execution, commits, or pushes.

The plan is finalized in chat and ready for `/code`.
