# Known Errors

## Missing MONA

- Symptom: compilation reports that the `mona` executable cannot be found.
- Cause: MONA is not installed or its installation directory is absent from `PATH`.
- Resolution: build/install MONA and verify `mona -v` before compiling.

## Missing OpenAI Configuration

- Symptom: proposal generation fails before an API request.
- Cause: `OPENAI_API_KEY` or both `--model` and `OPENAI_MODEL` are absent.
- Resolution: provide the missing environment variable or CLI option without placing credentials in repository files.

## Unsupported Structured Outputs

- Symptom: OpenAI rejects the response schema or model request.
- Cause: the configured model does not support the required Structured Outputs behavior.
- Resolution: choose a compatible model explicitly; do not silently retry with another model.

## Invalid Environment Markdown

- Symptom: proposition parsing reports a specific line.
- Cause: the `## Propositions` section is missing, duplicated, malformed, or contains duplicate, reserved, or invalid IDs.
- Resolution: use `- `<id>`: <description>` declarations and the identifier rules in `.agents/conventions.md`.

## FL-AT Licensing

- Symptom: the local compiler works but cannot be safely published as a modified dependency.
- Cause: the upstream FL-AT repository has no declared license.
- Resolution: keep modifications local until the owner grants permission or adds a license.

## Wrong Python Environment

- Symptom: the readiness suite reports `ModuleNotFoundError: No module named 'tianshou'` (also `torch`, `transformers`) and several test modules fail to import.
- Cause: commands ran in the repository `.venv` or a system interpreter instead of the project Conda environment.
- Resolution: run every command inside `RM_RL_env` (`conda run -n RM_RL_env ...`) as described in `.agents/workflow.md`. That environment already holds the complete pinned dependency set; do not install into `.venv`.
