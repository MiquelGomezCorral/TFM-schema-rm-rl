# Architecture

## Stack

Python 3.13 package built with setuptools. The compiler uses OpenAI Structured Outputs, IBM `nl2ltl` and `pylogics` for constrained DECLARE/LTLf formulas, FL-AT for automata composition, and the external MONA executable for LTLf-to-DFA compilation.

## Layout

- `app/main.py`: argparse CLI entry point.
- `app/scripts/`: command orchestration and human approval flow.
- `app/src/environment.py`: strict environment Markdown and proposition parsing.
- `app/src/openai_engine.py`: constrained OpenAI-to-DECLARE proposal generation.
- `app/src/ltlf.py`: `pylogics` AST to FL-AT syntax serialization.
- `app/src/pipeline.py`: proposal and approved-compilation orchestration.
- `app/src/reward_machine.py`: guard normalization, state renaming, and text serialization.
- `examples/`: documented environment descriptions.
- `dependencies/nl2ltl/`: pinned submodule of the maintained IBM `nl2ltl` fork.
- `dependencies/Flat/`: pinned submodule of the maintained FL-AT fork.

## Boundaries

The environment Markdown owns the allowed proposition vocabulary. The OpenAI engine may select only an IBM DECLARE pattern, declared propositions, and a proposed reward. IBM templates own LTLf construction. FL-AT and MONA own DFA and Reward Machine topology. The serializer owns the reference repository's text format.

The nested packages `dependencies/nl2ltl` and `dependencies/Flat` are editable
development dependencies pinned by parent gitlinks. Their maintained forks are
`origin`; IBM `nl2ltl` and `Jamidd/Flat` remain `upstream`. MONA remains an external
executable. V1 stops after Reward Machine generation and does not depend on an RL runtime.

## Flow

Environment Markdown -> constrained proposal -> human approval -> DECLARE/LTLf -> FL-AT/MONA DFA compilation -> composed Reward Machine -> reference-format text.
