# Architecture

## Stack

Python 3.13 package built with setuptools. The compiler uses OpenAI Structured Outputs, IBM `nl2ltl` and `pylogics` for constrained DECLARE/LTLf formulas, FL-AT for automata composition, and the external MONA executable for LTLf-to-DFA compilation.

## Layout

- `app/main.py`: argparse CLI entry point.
- `app/app.py`: local Dash web entry point.
- `app/scripts/`: bounded generator/critic orchestration and timed progress reporting.
- `app/src/models/environment.py`: strict environment Markdown and proposition parsing.
- `app/src/engines/openai_engine.py`: constrained proposal generation and structured task/RM critics.
- `app/src/compiler/ltlf.py`: `pylogics` AST to FL-AT syntax serialization.
- `app/src/compiler/pipeline.py`: per-task proposal and deterministic compilation boundaries.
- `app/src/compiler/reward_machine.py`: guard normalization, state renaming, and text serialization.
- `app/src/web/`: reusable Dash layout, callbacks, run state, and RM visualization.
- `app/assets/`: local responsive web styling.
- `examples/`: documented environment descriptions.
- `dependencies/nl2ltl/`: pinned submodule of the maintained IBM `nl2ltl` fork.
- `dependencies/Flat/`: pinned submodule of the maintained FL-AT fork.

## Boundaries

The environment Markdown owns the allowed proposition vocabulary. The OpenAI engine may select only an IBM DECLARE pattern, declared propositions, and a proposed reward. IBM templates own LTLf construction. FL-AT and MONA own DFA and Reward Machine topology. The serializer owns the reference repository's text format.

The nested packages `dependencies/nl2ltl` and `dependencies/Flat` are editable
development dependencies pinned by parent gitlinks. Their maintained forks are
`origin`; IBM `nl2ltl` and `Jamidd/Flat` remain `upstream`. MONA remains an external
executable. V1 stops after Reward Machine generation and does not depend on an RL runtime.

The local web UI is a thin adapter over `scripts.generate_rm`. Optional
`GenerationHooks` fan out run-scoped logging records and typed six-stage progress events
to the CLI, local persistent diagnostics, and the web controller while exposing completed
in-memory results and authoritative output paths. The web layer does not own proposal,
critic, compilation, serialization, or output-path behavior.

## Flow

Environment Markdown + task -> constrained proposal generator -> task critic ->
DECLARE/LTLf materialization -> FL-AT/MONA DFA compilation -> local RM composition and
serialization -> RM critic -> task-specific Reward Machine -> reference-format text.
Either critic may be disabled, but at least one remains enabled, and the complete
refinement attempt is bounded to three runs per task.

The web flow supplies the same inputs to that pipeline, polls local in-memory run state,
and renders the returned Reward Machine structure and serialized text.
