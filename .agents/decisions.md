# Decisions

Record closed decisions here. Do not reopen them unless the user explicitly asks.

## Active Decisions

### Compiler Pipeline

- V1 compiles environment Markdown and a list of simple natural-language instructions into one Reward Machine.
- Use IBM `nl2ltl` DECLARE templates as the constrained NL-to-LTLf intermediate representation.
- Use FL-AT and the required MONA executable for formal automata generation and composition.
- The LLM never writes LTL or Reward Machine topology directly.
- OpenAI responses are schema-constrained to supported patterns, declared propositions, and one finite proposed reward per instruction.
- A human must approve all patterns, grounded propositions, formulas, and rewards before formal compilation.
- The OpenAI model is required configuration through `--model` or `OPENAI_MODEL`; no model is hardcoded.

### Packaging And Output

- Target Python 3.13 and use local editable sibling dependencies `../nl2ltl` and `../Flat` during V1.
- Follow the `app/main.py`, `app/scripts/`, and `app/src/` setuptools layout used by the TFM project template.
- Persist the exact section-based Reward Machine format used by `llms-rm-rl`, not YAML.
- Proposition metadata and accepting states remain in memory because the selected text format does not persist them.
- FL-AT modifications remain a local academic prototype because the upstream repository has no declared license; do not publish or redistribute them without permission.
- V1 excludes RL training, policy evaluation, schemas, UI, embeddings, and automatic proposition-code generation.
- Do not add automated tests for V1; use the readiness check and an approved representative live flow.
