# Conventions

## Python

- Use `snake_case` for functions and modules and `PascalCase` for classes.
- Type public interfaces and add concise module, class, and function docstrings.
- Code under `app/` imports application modules through the `src` and `scripts` packages.
- Keep proposal generation separate from approved compilation so library APIs are non-interactive.

## Environment Markdown

- Parse proposition declarations only below one `## Propositions` heading.
- Each declaration is `- `<id>`: <description>` on one line.
- Proposition IDs match `^[a-z_][a-z0-9_]*$`, are unique, and cannot be `true` or `false`.
- Reject malformed declarations instead of asking the LLM to infer identifiers.

## Reward Machines

- Rename states deterministically in breadth-first order from `u0`.
- Expand Boolean guards into disjoint conjunctions before serialization.
- Emit only `REWARD_MACHINE`, `STATES`, `INITIAL_STATE`, `TRANSITION_FUNCTION`, and `REWARD_FUNCTION` sections.
- Write only nonzero reward rows; omitted rewards mean zero.
