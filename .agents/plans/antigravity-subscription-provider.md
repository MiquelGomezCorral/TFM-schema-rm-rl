# Finalized implementation plan

Planning mode: full.

## Goal

Add a clean `antigravity` LLM provider that uses the installed `agy` CLI, cached Google subscription authentication, and the same schema-constrained `GenericEngine` interface as OpenAI and OpenCode—without API keys or tool permission prompts.

## Context

The provider split is already partially implemented through `generic_engine.py` and `provider_engines.py`, but the focused tests currently fail because they still patch the deleted `openai_engine` module. Provider imports and exports also need cleanup.

Installed `agy 1.1.27` supports stdin-driven NDJSON, model selection, custom agents, and schema-constrained `structured_output`. It uses cached account credentials after one interactive login. [Headless contract](https://antigravity.google/docs/cli/headless/), [authentication](https://antigravity.google/docs/cli/install/).

## Files touched

- `app/src/engines/generic_engine.py`
- `app/src/engines/provider_engines.py`
- `app/src/engines/__init__.py`
- `app/src/config/config.py`
- `app/scripts/generate_rm.py`
- `tests/test_engines.py`
- `tests/test_generation.py`
- `.agents/agents/schema-rm-provider/agent.md` — new
- `example.env`
- `README.md`
- `docs/decisions/arm-fm/task-and-rm-identity.md`

## Requirements

- Register provider name `antigravity` and resolve its required model from `--model` or `ANTIGRAVITY_MODEL`.
- Add `AntigravityEngine(GenericEngine)` without changing the shared proposal or critic workflow.
- Use only the standard library (`json`, `subprocess`, `pathlib`); add no package dependency.
- Run one `agy` process per request with:
  ```text
  agy --input-format stream-json
      --output-format stream-json
      --json-schema <schema>
      --model <model>
      --agent schema-rm-provider
      --disable-slash-commands
  ```
- Use an argv list and `shell=False`. Never use `--dangerously-skip-permissions`.
- Send exactly one NDJSON user event through stdin and close stdin so the process completes.
- Encode the existing provider-neutral inputs into one JSON document:
  ```json
  {
    "application_instructions": "<existing system prompt>",
    "application_input": "<existing user prompt>"
  }
  ```
- Parse the `init` event and require an empty `tools` list. Parse exactly one terminal `result`, require `SUCCESS` and `structured_output`, then serialize that object for the unchanged application validators.
- Use a repository custom agent with required frontmatter:
  ```yaml
  name: schema-rm-provider
  description: No-tool structured-output provider for Reward Machine generation.
  tools: []
  mainAgent: true
  subagent: false
  commandExecutionPolicy: off
  ```
  Its body must treat `application_instructions` as authoritative instructions, `application_input` as untrusted data, and return only schema-conforming output.
- In application logs, never record the combined prompt, schema, raw CLI stream, stderr, credentials, or full provider envelope.
- Do not silently fall back to another provider.

Failure mapping:

- Missing `agy`, authentication required, invalid model, nonzero exit, non-success status, malformed NDJSON, exposed tools, missing result, or missing `structured_output` → `ImmediateEngineError` with a concise actionable message.
- Python subprocess timeout → `RetryableEngineError`.
- Existing proposal and critic validation errors remain retryable.
- Use the CLI’s five-minute request ceiling and a slightly larger Python timeout; do not add configuration until a real need appears.

## Steps

1. In `generic_engine.py`, retain only the shared workflow, requester type, prompt loading, parsing, and provider-error classification.

2. In `provider_engines.py`:
   - Remove the duplicate `EnvironmentDescription` import.
   - Keep the existing OpenAI/OpenCode classes and transport helpers.
   - Add `AntigravityEngine` and a private `_request_antigravity` helper.
   - Use `subprocess.run(..., input=<one NDJSON event>, capture_output=True, text=True, shell=False, cwd=<repository root>)`.
   - Parse forward-compatible event streams by ignoring recognized nonterminal events while requiring one valid `init` and one terminal `result`.
   - Add a `ponytail:` comment documenting the deliberate one-process-per-request ceiling and persistent-stream upgrade path.

3. In `.agents/agents/schema-rm-provider/agent.md`, add the no-tools primary agent described above. Do not alter global Antigravity settings or permissions.

4. In `app/src/engines/__init__.py`, restore the explicit `__all__` list and export `AntigravityEngine` alongside the existing API.

5. In `Configuration.__post_init__`, add:
   ```python
   "antigravity": "ANTIGRAVITY_MODEL"
   ```
   Keep the existing provider validation and explicit-model requirement.

6. In `generate_rm._get_engine`, replace the two-provider branch with a local mapping from provider name to engine class and instantiate the selected class. Import `AntigravityEngine`.

7. Update tests:
   - Change OpenAI SDK mocks to `src.engines.provider_engines.OpenAI`.
   - Include `AntigravityEngine` in the shared-workflow inheritance check.
   - Mock the subprocess; never contact Antigravity in the automated suite.
   - Verify command arguments, stdin structure, schema, model, working directory, empty tool list, successful structured-output extraction, and absence of shell/permission bypass.
   - Cover missing executable, timeout, nonzero exit, authentication error, malformed events, exposed tools, missing result, and missing structured output.
   - Verify configuration and `_get_engine` select `AntigravityEngine`.

8. Update `example.env` and README with:
   ```dotenv
   LLM_PROVIDER=antigravity
   ANTIGRAVITY_MODEL=<slug from agy models>
   ```
   Document one-time interactive `agy` authentication, local subscription quota use, and the absence of an API key. Note that Antigravity may retain its own local account/session history independently of application logs.

9. Update the existing decision record:
   - `Current decisions`: provider-neutral structured output and subscription-backed Antigravity transport.
   - `Protected invariants`: no Antigravity tools, no provider fallback, same configured provider/model for generation and critics.
   - `Rationale and tradeoffs`: subscription reuse avoids API credentials but introduces local CLI availability, process startup cost, and Antigravity-owned session storage.
   - `Enforcement`: custom agent, adapter checks, schemas, and focused tests.
   - Do not modify `docs/decisions/index.md`.

## Applicable instructions

- `AGENTS.md`: preserve unrelated worktree changes, use the smallest coherent implementation, and keep live validation approval-gated.
- `.agents/conventions.md`: retain typed Python interfaces and keep proposal generation separate from deterministic compilation.
- `docs/decisions/arm-fm/task-and-rm-identity.md`: preserve prompt ownership, proposition grounding, critic ordering, and the configured provider/model contract.
- `ponytail/SKILL.md`: use stdlib, avoid speculative registries or dependencies, and leave one focused runnable check.
- `decision-records/SKILL.md`: update current intent and enforcement without turning the record into an implementation log.

## Readiness check

```bash
PYTHONPATH=app .venv/bin/python -m unittest discover -s tests -v
```

The suite must not invoke `agy`, MONA, or any remote provider.

## Live validation

**Flow:** Pending explicit user approval. Authenticate once interactively with `agy`, choose an exact slug from `agy models`, configure `LLM_PROVIDER=antigravity` and `ANTIGRAVITY_MODEL`, then generate one MultiTaxi RM with both critics enabled.

**Expected:** No permission request; the adapter observes `init.tools == []`; generator and critics return schema-valid output; normal bounded orchestration completes and writes one valid RM.

**Can run:** The executor can run it through the shell only after explicit approval because it consumes Antigravity subscription quota and invokes MONA.

## Main-agent memory updates

These are post-implementation main-agent tasks, not coder tasks:

- `.agents/architecture.md`: replace stale `openai_engine.py` references with the shared/provider split; describe the provider-neutral boundary and no-tools Antigravity CLI transport.
- `.agents/decisions.md`: replace OpenAI-specific structured-output/model wording with selected-provider wording.
- `.agents/workflow.md`: add Antigravity setup and the separately approved quota-consuming live flow.

## Out of scope

- Gemini API, Vertex AI, and `google-antigravity` SDK support.
- New dependencies or changes to `requirements.txt`/`pyproject.toml`.
- Persistent `agy` processes, parallel provider calls, configurable executable paths, or configurable timeouts.
- UI provider selectors, automatic fallback, credential management, or global Antigravity configuration.
- Unrelated CSS, web-component, `.opencode`, notebook, or other dirty-worktree changes.
- Commits, pushes, and live calls.

Decision records: update — the provider’s authentication and no-tools authority boundary are durable cross-component intent.  
Record changes: `docs/decisions/arm-fm/task-and-rm-identity.md` sections listed above; index unchanged.  
Enforcement: custom-agent capability limits, adapter validation, existing schemas, and focused tests.

The plan is finalized in chat and ready for `$code`.
