# ARM-FM task and RM identity

## Intent

Define what the pipeline considers one task, one Reward Machine, and a collection of
tasks, while keeping the generator and critic responsibilities stable.

## Current decisions

- One submitted natural-language task produces one task-specific RM.
- In compiler mode, a task may contain several atomic clauses. Clauses that jointly describe one objective
  are compiled separately and composed conjunctively into the same RM.
- Independent submitted tasks produce independent RMs. Do not merge them into one
  product RM merely for transfer or multi-task training.
- Shared-policy transfer follows ARM-FM: train with separate task RMs and condition the
  policy on the active RM state's language description or embedding.
- The public input is an ordinary-language task, not an instruction or a caller-supplied
  priority override. In compiler mode, the model infers the supported clause pattern and, for precedence,
  whether ordering is soft or hard.
- The generator system prompt owns stable role, safety, supported-template, grounding,
  and output-format rules. The user prompt supplies the environment Markdown, task,
  candidate output (for critics), and use-case-specific additions.
  Environment-specific facts do not belong in the shared system prompt.
- In compiler mode, the model translates ordinary language into normalized clauses and declared
  propositions. It does not write LTLf, invent propositions, or design RM topology;
  deterministic code and the formal compiler own those steps.
- The compiler proposal schema and runtime validation share each supported pattern's
  exact arity and allowed priorities. Invalid combinations are rejected, not coerced:
  `Existence` and `ExistenceTwo` take one proposition with priority `none`;
  `Precedence` takes two with priority `soft` or `hard`.
- A precedence clause already requires both events. Hard ordering requires the first
  event before the first occurrence of the second; reverse or simultaneous first
  occurrence fails. Soft ordering permits those completions while preferring the
  requested order. `ExistenceTwo` requires two distinct time points.
- In compiler mode, the task critic reviews semantic fidelity and proposition grounding before compilation;
  the independent RM critic reviews only the serialized compiled machine. Both return a
  strict acceptance decision and nonempty feedback, never corrected artifacts.
- Compiler critics use paper-inspired checklists adapted to deterministic compilation.
  The task critic checks logic, grounding, completeness, compactness, and format;
  the RM critic also checks event coverage and reward safety using
  [RM execution](rm-execution.md). Generic worked examples illustrate acceptance and
  concrete rejection without declaring propositions for the submitted environment.
- A correct candidate is accepted without optional changes. Rejection identifies a
  necessary defect in an actual clause, header, or transition; an RM semantic defect
  includes a feasible event sequence following the candidate's rows. Critics do not
  demand redundant existence clauses, environment-guaranteed prerequisites, optional
  guard merging, different reward magnitudes, or penalties on valid rejecting sinks.
- Critic responses remain JSON with boolean `accepted` and nonempty `feedback`.
  Prompt feedback begins with `NO CHANGES NEEDED` or `CHANGES REQUIRED`. These are
  prompt instructions, not an additional execution-evidence gate or automated override
  of a critic's verdict.
- In compiler mode, each task has at most three generator attempts. Each critic may be disabled;
  disabling both prints a warning and accepts the compiler's first result. Enabled critics use the
  configured provider and model.
- Compiler generator and critic responses use the same provider-neutral structured-output
  contract regardless of the selected LLM provider.
- Antigravity is supported through its local `agy` CLI and cached Google account
  subscription. The adapter is headless, schema-constrained, verifies its selected agent,
  rejects tool or subagent execution, and has no permission bypass.
- The packaged compiler prompts include the executable subset of `docs/LTLF_TASK_LANGUAGE.md`.
  They do not load or symlink the full document because it also describes candidate
  patterns that are not executable.
- ARM-FM baseline mode generates RM topology directly, then labeling functions and state
  descriptions. It uses separate paper-derived generation and critic prompts; compiler-only
  clause restrictions do not constrain the baseline.
- Compiler RMs retain numeric identities internally. At compiler text and shared artifact boundaries,
  map them consistently to `u0`, `u1`, and so on across states, transitions, finals,
  and state descriptions without changing their topology or rewards.
- Compiler text uses the existing ARM-FM `TRANSITION_FUNCTION` and `REWARD_FUNCTION`
  sections. Generated headers are `REWARD_MACHINE:`, `STATES:`, `INITIAL_STATE:`,
  `FINAL_STATES:`, and `DEFAULT_REWARD: 0`. `STATES` includes all states, including
  accepting and rejecting states; compiler imports require exactly one final state
  distinct from the initial state.
- Transition rows are `(source, guard) -> destination`, including zero-reward state
  changes. Reward rows are `(source, guard, destination) -> reward` and generated text
  lists only nonzero rewards; omitted rewards are zero. Guards use `!`, `&`, `|`, and
  parentheses. Generation omits explicit zero-reward self-loops and `else` rows;
  import and fallback behavior follow [RM execution](rm-execution.md).
- This replaces the compiler's numeric semicolon text format; legacy artifacts must
  be regenerated. ARM-FM generation prompts and published artifacts retain their
  existing format.
- Both modes follow [RM execution](rm-execution.md) and produce separate task bundles for
  shared-policy training and evaluation.

## Protected invariants

- Every compiler clause uses only propositions declared by that environment.
- In compiler mode, one task's clauses have conjunction semantics; unsupported disjunction, optional
  branches, or incompatible clauses are rejected rather than weakened.
- Separate tasks remain separate RMs even when they share propositions or subgoals.
- Task terminology is used consistently across CLI, web, configuration, prompts, and
  output; the removed instruction and priority-override interfaces are not aliases.
- In compiler mode, the RM is accepted/finalized only after every enabled critic accepts the same attempt;
  the RM critic necessarily reviews the already compiled candidate.
- Compiler presentation and critic improvements must preserve ARM-FM baseline prompts
  and published evidence. Shared format adapters change representation without
  redesigning the compiled machine.
- Critics must follow declared finals, state memory, fallback rules, and one reward
  per step. They must not invent states, transitions, or extra task requirements to
  justify rejection; correct conjunctive decomposition and zero-reward progress rows
  are valid compiler output.
- In compiler mode, the configured provider and model are used consistently for generation and both
  critics; provider failures do not silently fall back to another provider.
- Antigravity requests use the selected `schema-rm-provider` agent, must not bypass tool
  permissions, and must reject any tool or subagent execution. AGY's advertised tool list
  is not treated as execution because primary sessions always expose the CLI registry.
- A reconstruction target in `examples/arm-fm/*/tasks.md` is the input for one task;
  its atomic probes are diagnostic inputs, not an implicit batch to merge.

## Rationale and tradeoffs

The paper's language-aligned RM model needs one automaton per objective and obtains
cross-task transfer from shared state descriptions. In compiler mode, replacing manual approval with bounded
automated critics keeps that gate self-contained and repeatable while preserving the
deterministic compiler boundary. The tradeoff is possible false rejection and additional
provider cost for refinement attempts. Conjunctive clause composition gives
the current compiler a small, deterministic way to express multi-stage objectives while
avoiding a hidden policy that merges unrelated tasks. The tradeoff is that conjunction
of the present templates may not reproduce the paper's hand-shaped transition topology
or reward magnitudes exactly. Using an authenticated local Antigravity subscription
avoids storing an API credential, at the cost of requiring the `agy` CLI, its cached
account session, per-request process startup, and CLI-owned session history. AGY primary
sessions advertise their CLI tool registry even when the custom agent requests no tools,
so the adapter checks executed stream events rather than rejecting the advertised list.

Separate transition and reward sections deliberately retain the ARM-FM layout for
later comparisons. A combined `(source, guard, destination) -> reward` representation
would be compact, but would require changing the baseline's model prompts or keeping
another translation format. Adapting deterministic compiler serialization preserves
baseline reproducibility. Zero-reward state changes remain explicit because they
record progress even when no reward is emitted.

The compiler critics borrow the paper's review approach without changing the baseline
prompts. Explicit execution rules and worked examples address observed false
rejections; prompt compliance remains model-dependent and is not proof of semantic
correctness.

## Enforcement

- Task and clause boundaries are implemented in `app/src/compiler/pipeline.py` and
  `app/src/compiler/reward_machine.py`.
- Compiler text serialization and import reuse the ARM-FM format in
  `app/src/arm_fm/runtime.py`; `tests/test_reward_machine_format.py` checks interoperability.
- Clause count, exact arity, pattern-specific priorities, and proposition grounding
  share schema and runtime validation in
  `app/src/engines/structured.py`.
- Bounded refinement, strict critic schemas, and atomic batch output are implemented in
  `app/scripts/generate_rm.py` and `app/src/engines/generic_engine.py`.
- Provider adapters in `app/src/engines/provider_engines.py` enforce the selected
  provider/model contract, selected Antigravity agent, and no-execution boundary.
- Reusable prompt contracts and rendering functions are packaged under `app/src/prompts`,
  while deterministic compiler ownership remains in `app/src/compiler/`.
- Compiler critic instructions and worked examples live in
  `app/src/prompts/compiler-rm/reward-ltlf-reviewer.system.md` and
  `app/src/prompts/compiler-rm/reward-machine-reviewer.system.md`; baseline prompts
  remain separate under `app/src/prompts/arm_fm/`. Model compliance and preservation
  of baseline prompts and published evidence are Review-only. Runtime enforcement
  is listed in [RM execution](rm-execution.md).

## History

- 2026-09-18: Qualified formal translation and compiler critics as compiler-mode rules;
  retained one RM per task and shared-policy transfer across both generation modes.
- 2026-09-21: Standardized generated bundle state names at the compiler adapter only.
- 2026-09-22: Allowed a warned run with both critics disabled as an explicit fallback; the compiler
  still requires every enabled critic to accept the same attempt before finalizing.
