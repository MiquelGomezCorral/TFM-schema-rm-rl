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

## Project Notes

- Stack: Python 3.13, setuptools, IBM `nl2ltl`, FL-AT, MONA, and OpenAI Structured Outputs.
- Package manager: install `requirements.txt` with `uv pip`, then install this package editably.
- Entry point: `app/main.py`; the initial command is `generate-rm`.
- V1 compiles reviewed natural-language instructions to Reward Machines. It does not train RL agents.
