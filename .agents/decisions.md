# Decisions

Record closed decisions here. Do not reopen them unless the user explicitly asks.

## Active Decisions

### Compiler Pipeline

- V1 compiles environment Markdown and ordinary-language tasks into one task-specific Reward Machine per task.
- Use IBM `nl2ltl` DECLARE templates as the constrained NL-to-LTLf intermediate representation.
- Use FL-AT and the required MONA executable for formal automata generation and composition.
- The LLM never writes LTL or Reward Machine topology directly.
- Generator responses from the selected provider are schema-constrained to supported patterns, declared
  propositions, and compiler-supported priority semantics for each task clause.
- Automated task and RM critics replace human approval. Each may be disabled independently,
  at least one must remain enabled, and both use the configured provider/model.
- A task receives at most three complete generator/critic attempts; outputs are written
  only after every submitted task is accepted.
- The selected provider's model is required through `--model` or its provider-specific model
  environment variable; no model is hardcoded.
- The Antigravity provider uses the local cached Google account through `agy`, enforces the same
  structured-output contract, exposes no agent tools, and never falls back to another provider.

### Packaging And Output

- Target Python 3.13 and install editable dependencies from the exact-SHA submodules
  `dependencies/nl2ltl` and `dependencies/Flat`.
- The existing `TFM-schema-rm-rl` repository is the public superproject. Maintained
  dependency forks are `origin`, original projects are `upstream`, and parent commits
  pin exact revisions without floating submodule branches.
- Follow the `app/main.py`, `app/scripts/`, and `app/src/` setuptools layout used by the TFM project template.
- Persist the exact section-based Reward Machine format used by `llms-rm-rl`, not YAML.
- Proposition metadata and accepting states remain in memory because the selected text format does not persist them.
- The public Flat adaptation was published by explicit user authorization while the
  upstream license request remains open at `Jamidd/Flat#1`.
- V1 excludes RL training, policy evaluation, schemas, embeddings, and automatic proposition-code generation.
- Keep focused automated tests for deterministic orchestration, prompt contracts, and web controls;
  live LLM/MONA validation remains a separately approved check.

### Local Web UI

- Keep the Dash UI in this repository as a local, single-active-run input/output adapter.
- Support multiple ordinary-language task rows and one independently compiled RM per task.
- Reuse `scripts.generate_rm` through narrow timed-progress and completion hooks; do not
  duplicate or move critic or formal compiler behavior into the web layer.
- Expose both critic toggles, default both on, and reject a run with neither selected.
- Render the exact completed text and in-memory Reward Machine structures returned by the pipeline, using its authoritative output paths.
- Present the structured six-stage tracker by default while retaining the full plain-text
  Log view; task navigation observes the sequential pipeline and does not introduce
  parallel execution.
- Retain full local, gitignored diagnostics for every run until manually deleted; logs
  contain formatted generated artifacts but do not explicitly serialize secrets, prompts,
  or raw provider objects.
- Exclude production hosting, authentication, multi-user isolation, and persistent job queues.
