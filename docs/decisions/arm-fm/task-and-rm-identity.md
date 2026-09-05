# ARM-FM task and RM identity

## Intent

Define what the pipeline considers one task, one Reward Machine, and a collection of
tasks, while keeping the generator and critic responsibilities stable.

## Current decisions

- One submitted natural-language task produces one task-specific RM.
- A task may contain several atomic clauses. Clauses that jointly describe one objective
  are compiled separately and composed conjunctively into the same RM.
- Independent submitted tasks produce independent RMs. Do not merge them into one
  product RM merely for transfer or multi-task training.
- Shared-policy transfer follows ARM-FM: train with separate task RMs and condition the
  policy on the active RM state's language description or embedding.
- The public input is an ordinary-language task, not an instruction or a caller-supplied
  priority override. The model infers the supported clause pattern and, for precedence,
  whether ordering is soft or hard.
- The generator system prompt owns stable role, safety, supported-template, grounding,
  and output-format rules. The user prompt supplies the environment Markdown, task,
  candidate output (for critics), and use-case-specific additions.
  Environment-specific facts do not belong in the shared system prompt.
- The model translates ordinary language into normalized clauses and declared
  propositions. It does not write LTLf, invent propositions, or design RM topology;
  deterministic code and the formal compiler own those steps.
- The task critic reviews semantic fidelity and proposition grounding before compilation;
  the independent RM critic reviews only the serialized compiled machine. Both return a
  strict acceptance decision and nonempty feedback, never corrected artifacts.
- Each task has at most three generator attempts. Either critic may be disabled, but at
  least one remains enabled; both use the configured provider and model.
- The packaged prompts include the executable subset of `docs/LTLF_TASK_LANGUAGE.md`.
  They do not load or symlink the full document because it also describes candidate
  patterns that are not executable.

## Protected invariants

- Every clause uses only propositions declared by that environment.
- One task's clauses have conjunction semantics; unsupported disjunction, optional
  branches, or incompatible clauses are rejected rather than weakened.
- Separate tasks remain separate RMs even when they share propositions or subgoals.
- Task terminology is used consistently across CLI, web, configuration, prompts, and
  output; the removed instruction and priority-override interfaces are not aliases.
- The RM is accepted/finalized only after every enabled critic accepts the same attempt;
  the RM critic necessarily reviews the already compiled candidate.
- A reconstruction target in `examples/arm-fm/*/tasks.md` is the input for one task;
  its atomic probes are diagnostic inputs, not an implicit batch to merge.

## Rationale and tradeoffs

The paper's language-aligned RM model needs one automaton per objective and obtains
cross-task transfer from shared state descriptions. Replacing manual approval with bounded
automated critics keeps that gate self-contained and repeatable while preserving the
deterministic compiler boundary. The tradeoff is possible false rejection and additional
provider cost for refinement attempts. Conjunctive clause composition gives
the current compiler a small, deterministic way to express multi-stage objectives while
avoiding a hidden policy that merges unrelated tasks. The tradeoff is that conjunction
of the present templates may not reproduce the paper's hand-shaped transition topology
or reward magnitudes exactly.

## Enforcement

- Task and clause boundaries are implemented in `app/src/compiler/pipeline.py` and
  `app/src/compiler/reward_machine.py`.
- Clause count and proposition grounding are validated in
  `app/src/engines/openai_engine.py`.
- Bounded refinement, strict critic schemas, and atomic batch output are implemented in
  `app/scripts/generate_rm.py` and `app/src/engines/openai_engine.py`.
- Reusable prompt contracts and rendering functions are packaged under `app/src/prompts`,
  while deterministic compiler ownership remains in `app/src/compiler/`.
