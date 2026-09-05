# Run observability

## Intent

Make a generation run understandable while it is executing and leave enough local
diagnostics to reproduce a failed run without changing compilation semantics.

## Current decisions

- The pipeline publishes one immutable typed event for each task stage. The CLI and
  web controller consume the same event boundary; the web layer does not parse log text.
- Each task exposes six sequential stages: structured proposal generation, optional task
  critic, deterministic DECLARE/LTLf materialization, FL-AT/MONA DFA compilation,
  Reward Machine construction, and optional Reward Machine critic.
- The web Run status defaults to a Steps view and retains the complete plain-text Log
  view. Multiple submitted tasks remain sequential and are navigated one at a time.
- Every started CLI or web run writes one UTF-8 plain-text log under `logs/`. The file,
  console, and web Log view share the same timed records and multiline artifact output.
- Logs are retained locally until manually deleted. There is no automatic rotation or
  run-history UI in V1.

## Protected invariants

- Stage events carry task index, attempt, stage, state, and terminal duration; retrying
  a task does not alter another task's progress.
- Disabled critics are explicitly skipped. A task is accepted only when every enabled
  critic accepts the same attempt, and output files remain gated on all task acceptance.
- Logs include validated proposal data, critic verdicts, LTLf clauses, complete DFA data,
  and serialized Reward Machines, but never explicitly include credentials, environment
  variables, request headers, full prompts, or raw provider response objects.
- The persistent log is plain text without ANSI escape sequences, and the UI uses text
  labels with color rather than color alone to identify state.

## Rationale and tradeoffs

Typed events give the web UI stable state without coupling it to wording. A run-scoped
stdlib logger keeps console, browser, and disk output consistent with no new dependency.
Local manual retention is intentionally simple for this single-user V1; rotation and
multi-user isolation can be added only if deployment scope expands.

## Enforcement

- `app/scripts/generate_rm.py` owns stage ordering, event publication, artifact logging,
  and handler cleanup.
- `app/src/web/runner.py` owns immutable snapshots and retry reset behavior.
- `app/src/web/components.py` and `app/src/web/application.py` own presentation only.
- Deterministic orchestration and web tests verify event order, skipped states, retry
  behavior, persisted artifacts, labels, colors, and navigation.
