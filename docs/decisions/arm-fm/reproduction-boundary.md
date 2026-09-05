# ARM-FM reproduction boundary

## Intent

State exactly what this project recreates from ARM-FM and where comparison must remain
semantic rather than byte-for-byte.

## Current decisions

- V1 generates and compiles Reward Machines from critic-validated natural language. It does not
  generate labeling functions, execute RL training, or reproduce the paper's embedding
  and agent-training stack.
- The environment Markdown owns the allowed proposition vocabulary. Propositions describe
  observable state conditions or explicitly documented progress events; raw actions are
  not RM events.
- The current compiler supports `Existence`, `ExistenceTwo`, and `Precedence` clauses,
  then deterministically composes their reachable conjunction product.
- Reconstruction targets should be submitted as one composite task. Atomic probes are
  useful for checking individual stages but are not a replacement for the composite
  target.
- Semantic equivalence is the default comparison criterion. Byte-identical comparison is
  valid only when proposition names, event predicates, rewards, and serialization format
  all match the released artifact.

## Protected invariants

- No labeling-function or RL implementation is added to the V1 RM-generation scope.
- The compiler must not invent undeclared propositions or silently approximate unsupported
  temporal meaning.
- At least one bounded automated critic precedes acceptance of a compiled proposal; the
  deterministic compiler remains the owner of LTLf, automata, and rewards.
- Paper defects remain visible in evidence files: Craftium's Appendix A.9 block uses an
  undeclared `u4` and inconsistent reward transitions; KeyCorridor's trace uses a
  DoorKey mission; Meta-World's exact sparse wrapper is unpublished; XLand's decoded
  1,000 prompts and task-specific RMs are unpublished.
- Proposition-name translations are documented beside each pair. A translation is not
  claimed to be an executable labeling-function implementation.

## Rationale and tradeoffs

ARM-FM covers a larger system than the current project. Limiting V1 to critic-validated RM
generation keeps the formal boundary testable and avoids pretending that source gaps can
be filled by guessed wrappers or predicates. The tradeoff is that generated machines may
share the intended staged objective without matching the paper's exact state numbering,
reward shaping, or event vocabulary.

## Enforcement

- Supported templates and retry/refusal behavior are defined in
  `app/src/engines/openai_engine.py`.
- Formula composition and rejection of unreachable accepting products are implemented in
  `app/src/compiler/pipeline.py` and `app/src/compiler/reward_machine.py`.
- Environment vocabulary validation is implemented in `app/src/models/environment.py`.
- Critic schemas, three-attempt orchestration, and CLI/web toggles are documented in
  `docs/LTLF_TASK_LANGUAGE.md` and enforced in the generation and UI modules.
- Source gaps and semantic mappings are review-only because the unpublished artifacts
  cannot be mechanically verified.
