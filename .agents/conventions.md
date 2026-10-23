# Conventions

## Python

- Use `snake_case` for functions and modules and `PascalCase` for classes.
- Type public interfaces and add concise module, class, and function docstrings.
- Code under `app/` imports application modules through the `src` and `scripts` packages.
- Keep proposal generation separate from approved compilation so library APIs are non-interactive.

## Environment Markdown

- Write or revise an environment's `environment.md` (facts, read by the generator and the critic)
  and `environment-code.md` (all implementation: Labeling API, code, evidence, links; code agents
  read both files) by `docs/ENVIRONMENT_AUTHORING.md`.
- Parse proposition declarations only below one `## Propositions` heading.
- Each declaration is `- `<id>`: <description>` on one line.
- Proposition IDs match `^[a-z_][a-z0-9_]*$`, are unique, and cannot be `true` or `false`.
- Reject malformed declarations instead of asking the LLM to infer identifiers.
- An environment used for labeling or training also needs a `## Labeling API` section in its
  `environment-code.md`: the only runtime surface the labeling generators see
  (`EnvironmentDescription.require_labeling_api`). Labeling steps load both files with
  `EnvironmentDescription.from_file(path, code=True)`; the clause generator and the critic load
  the facts file alone.

## Reward Machines

- Rename states deterministically in breadth-first order from `u0`.
- Expand Boolean guards into disjoint conjunctions before serialization.
- Emit the numeric semicolon format: `s`, `i`, `f`, and `r` headers followed by `source; destination; condition; reward` rows.
- Exclude the final state from the `s` header and emit state-changing transitions plus any nonzero-reward self-loop.
- Omitted transitions are zero-reward self-loops.

## Presenting results

- Every shown result carries three things: the natural-language task, the IBM clauses with their LTLf (readable and raw), and the Reward Machine.
- A hand-picked clause set with no real task gets a hand-written task, marked illustrative.
- Anything added to the real clauses, LTLf or RM for presentation is stated at the top and shown, never silent.
- Build with `src/utils/presentation.py`; `app/scripts/present_results.py` makes the page from run directories.
