# Project Agent Rules

Read this file before changing code in this repository.

## Memory Files

- `.agents/architecture.md` - stack, layout, boundaries, and compiler flow.
- `.agents/conventions.md` - naming, imports, environment Markdown, and output rules.
- `.agents/decisions.md` - closed project decisions and rationale.
- `.agents/glossary.md` - formal-method and project terminology.
- `.agents/workflow.md` - setup, readiness, and live validation commands.
- `.agents/known-errors.md` - recurring setup and input failures.

## Load Rules

- Load only the memory file relevant to the current task.
- If memory conflicts with current code, trust current code and flag the stale entry.
- Do not update memory silently. Propose changes unless the user asks to write them.
- For non-trivial implementation, read `docs/decisions/index.md` and any applicable records before
  changing code. Report `Decision records: create`, `update`, or `no change` with a short reason.
- If implementation conflicts with a protected invariant, pause and let the developer choose whether
  to revise the code, revise the record, or reopen planning; never resolve the mismatch silently.

## Project Notes

- Stack: Python 3.13, setuptools, IBM `nl2ltl`, FL-AT, MONA, and OpenAI Structured Outputs.
- Environment: run everything inside the existing `RM_RL_env` Conda environment (Python 3.13).
  `uv pip` installs `requirements.txt` into it and this package editably. Do not create another
  environment, and do not use the repository `.venv`.
- Entry point: `app/main.py`; the initial command is `generate-rm`.
- V1 compiles reviewed natural-language instructions to Reward Machines. It does not train RL agents.
