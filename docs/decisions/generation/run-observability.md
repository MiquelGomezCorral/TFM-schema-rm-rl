# Run observability

## Intent

Make a generation run understandable while it is executing and leave enough local
diagnostics to reproduce a failed run without changing compilation semantics.

## Current decisions

- The pipeline publishes one immutable typed event for each task stage. The CLI and
  web controller consume the same event boundary; the web layer does not parse log text.
- Compiler failures returned as exit codes are delivered through an explicit hook.
  When three attempts are exhausted, the error includes the last failing stage and
  its feedback; the web Run status retains this reason rather than only the exit code.
  Expected provider failures also retain their diagnostic message. The generic exit
  code message is a fallback only when no specific reason was delivered.
- Each task exposes nine sequential stages: structured proposal generation, optional task
  critic, deterministic DECLARE/LTLf materialization, FL-AT/MONA DFA compilation,
  Reward Machine construction, state-description generation, optional Reward Machine critic,
  optional MiniGrid labeling generation, and optional local node embeddings.
- State descriptions appear in the app's Completed output, paired with their node
  identifiers, and are retained in the existing step trace and optional Markdown report.
  Previously saved traces without descriptions remain readable.
- Completed output includes accepted labeling source and its saved bundle path. Embeddings
  show model, dimension, node identifiers, and artifact path; full vectors stay in artifacts.
  Standalone compiler bundles use the configured output folder's `bundles/<task stem>`.
- The web Run status defaults to a Steps view and retains the complete plain-text Log
  view. Multiple submitted tasks remain sequential and are navigated one at a time.
- Every started CLI or web run writes one UTF-8 plain-text log under `logs/`. The file,
  console, and web Log view share the same timed records and multiline artifact output.
- Logs are retained locally until manually deleted. There is no automatic rotation or
  run-history UI in V1.
- Graph focus is a desktop-only reading mode; the focus control is hidden below the
  desktop breakpoint instead of introducing a separate mobile graph layout.

## Protected invariants

- Stage events carry task index, attempt, stage, state, and terminal duration; retrying
  a task does not alter another task's progress.
- Disabled critics and optional artifact stages are explicitly skipped. A task is accepted only when every enabled
  critic accepts the same attempt and state descriptions are complete; output files
  remain gated on all task acceptance and enabled postprocessing completion. All final
  destinations are checked before writing; overwrite policy applies to bundles too.
- Tagging retries preserve the compiled candidate and its proposal attempt number.
  They do not reset completed compiler stages or consume extra proposal attempts.
  An exhausted tagging stage retains its specific diagnostic through the failure hook.
- Labeling retries likewise preserve the accepted RM and descriptions. Labeling or embedding
  failure retains its stage-specific diagnostic and does not restart proposal generation.
- Failure reporting must not parse logs, replace an available diagnostic with a
  generic exit code, add refinement attempts, or override a critic's rejection.
- Logs include validated proposal data, critic verdicts, LTLf clauses, complete DFA data,
  serialized Reward Machines, validated node descriptions and labeling source, and embedding
  metadata, but never explicitly include credentials, environment
  variables, request headers, full prompts, or raw provider response objects.
- The persistent log is plain text without ANSI escape sequences, and the UI uses text
  labels with color rather than color alone to identify state.

## Rationale and tradeoffs

Typed events give the web UI stable state without coupling it to wording. A run-scoped
stdlib logger keeps console, browser, and disk output consistent with no new dependency.
Local manual retention is intentionally simple for this single-user V1; rotation and
multi-user isolation can be added only if deployment scope expands.

State descriptions reuse the same event, artifact, and output-tab boundaries rather
than introducing a second controller. Capturing descriptions with node identifiers
keeps their association visible when a trace is reopened.

## Enforcement

- `app/scripts/generate_rm.py` owns stage ordering, event publication, artifact logging,
  and handler cleanup.
- `app/src/utils/generation_logging.py` exposes the explicit failure callback;
  `app/src/web/runner.py` retains that diagnostic alongside immutable snapshots and
  retry reset behavior.
- `app/src/web/components.py` and `app/src/web/application.py` own presentation only.
- `app/src/utils/step_trace.py` owns description artifacts in portable traces and
  optional reports. The shared stage enum, web stage order, output-tab labels, and
  JSON highlighting include the description stage.
- Deterministic orchestration and web tests verify event order, skipped states, retry
  behavior, persisted artifacts, labels, colors, and navigation.
- `tests/test_web.py` exercises the controller and compiler pipeline with deterministic
  provider responses for generator, task-critic, RM-critic, and provider failures.
  These checks verify diagnostic propagation and output gating, not live provider
  reliability or improved critic acceptance rates.
