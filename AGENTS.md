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
- V1 compiles reviewed natural-language instructions to Reward Machines, with optional MiniGrid
  labeling and local state embeddings.
- The ARM-FM path additionally generates, runs, trains, and evaluates task bundles.

## Paper Evidence

- This project becomes a paper. `docs/paper/` keeps results worth citing: pages with visual
  proof, measured results, figures, and the inputs and scripts that rerun them.
  `docs/paper/README.md` lists every entry and explains how entries are added.
- When work produces such a result (a before/after page, a decisive check, a number the paper
  could quote), name it to the user as a paper candidate and ask before copying it there.
  Pages under `.git/agent-memory/artifacts/` are working copies, not the record.
- An entry is one folder that opens from disk on its own, plus a README note: what it shows, the
  evidence, the files, how to rerun it, and the code or commit it refers to.
