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
  priority override. In compiler mode, the model infers each clause's IBM DECLARE template and
  whether the clause is hard or soft.
- The generator system prompt owns stable role, safety, supported-template, grounding,
  and output-format rules. The user prompt supplies the environment Markdown, task,
  candidate output (for critics), and, for labeling, the environment's declared API.
  Environment-specific facts do not belong in the shared system prompt.
- In compiler mode, the model translates ordinary language into normalized clauses and declared
  propositions. It does not write LTLf, invent propositions, or design RM topology;
  deterministic code and the formal compiler own those steps.
- The compiler proposal schema and runtime validation share IBM nl2ltl's 8 DECLARE templates
  and their exact arity: `Existence`, `ExistenceTwo` and `Absence` take one proposition;
  `RespondedExistence`, `Response`, `Precedence`, `ChainResponse` and `NotCoExistence` take two.
  Every clause has priority `hard` or `soft`. Invalid combinations are rejected, not coerced.
  Template objects are built from IBM's template classes and every formula is IBM's `to_ltlf()`;
  IBM's grounding helper is not used because it builds `NotCoExistence(b, b)`.
- Clause formulas follow IBM exactly; for example `Precedence(a, b)` means no `b` before `a`
  and also holds when neither occurs. Hard and soft never change a formula: soft changes only
  rewards; hard also changes the RM structure (a hard violation leads to the rejecting state and a
  pending hard obligation blocks finishing). The reward layer is described in
  `docs/COMPILER_REWARD_DESIGN.md`.
- In compiler mode, one critic reviews the compiled candidate after RM construction: it receives
  the environment, task, validated clauses, and the compiled RM with its final and rejecting
  states and compile warnings. It returns a strict acceptance decision and nonempty feedback,
  never corrected artifacts.
- A separate compiler state-description request runs after the critic accepts the RM. Its system prompt defines the inputs and tagging rules; its user prompt supplies
  the environment, original task, all validated clauses, compiled RM (its `REJECTING_STATES:` line names the well),
  and ordered node identifiers. It returns one JSON list of nonempty strings in node order,
  with 1–4 sentences describing each state's progress and remaining objectives.
- Description generation uses the configured provider and generator model. Malformed descriptions
  and transient provider failures permit at most three tagging requests against the same
  compiled candidate; exhaustion stops the run without regenerating that candidate.
  A critic rejection follows the existing bounded proposal retry loop. Disabling the critic
  does not disable tagging.
- Every request through the OpenAI SDK (OpenAI, OpenCode) repeats an HTTP 400 up to
  `Configuration.PROVIDER_RETRIES` (10) times, 1 s apart, before it counts as a failure; these
  repeats use no proposal or tagging attempt. OpenCode's random 400 sticks to the
  `x-opencode-session` id: repeating with the same id never recovered in a probe (0/9), a new id
  did (9/9), so every repeat sends a new session id. Command-line adapters (Pi, Antigravity) do
  not repeat.
- Descriptions remain separate from RM topology, rewards, and text. They distinguish
  successful completion from irreversible rejection, preserve conjunctive requirements,
  and follow the machine's event memory and fallback semantics.
- The compiler critic uses a paper-inspired checklist adapted to deterministic compilation:
  logic, grounding, completeness, compactness, format, event coverage, and reward safety using
  [RM execution](rm-execution.md). Rule-only tasks and warned soft clauses without reward effect
  are valid output. Generic worked examples illustrate acceptance and
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
- In compiler mode, each task has at most `--attempts` generator attempts (default 3, at most
  10, also a web UI field). Only a critic rejection uses one: a provider failure (connection
  error, exhausted 400 repeats, timeout) or a content failure (invalid proposal, incompatible
  clauses, malformed tagger output) reruns the same attempt and reports a warning, bounded by a
  fixed fuse of uncounted reruns. The critic may be disabled; disabling it prints a warning and
  accepts the compiler's first result. Enabled critics use the configured provider and critic
  model.
- The creator assumes the task is feasible in its environment; there is no refusal field.
  Whether a task can be done at all is the environment author's and the user's responsibility.
- The environment's `## Constraints` are declared facts the compiler applies to drop the states
  and transitions the environment cannot reach; they are never clauses and the model does not
  write them.
- The generator and the critic run at one shared reasoning level (`--reasoning`: `none`, `low`,
  `medium`, `high`, `max`; default `none`), sent on every provider request of the run.
- Compiler model selection is role-specific: one generator model writes clauses and state
  descriptions; a different critic model reviews the clauses and the compiled RM.
  Create the generator engine and, when the critic is enabled, the critic engine once
  per run, sharing the loaded environment and selected provider. OpenCode compiler runs
  read `OPENCODE_MODEL_GENERATOR` and `OPENCODE_MODEL_CRITIC` for these roles.
  Missing critic configuration must not silently reuse the generator model. ARM-FM baseline
  model selection and prompts remain unchanged.
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
  `FINAL_STATES:` (zero or one state; empty for rule-only tasks), `REJECTING_STATES:`
  (the one rejecting well, only when present), and `DEFAULT_REWARD: 0`. `STATES` includes all
  states, including accepting and rejecting states.
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
- Compiler mode optionally generates labeling functions after RM acceptance, for any
  environment whose `environment.md` declares a `## Labeling API`, which labeling requires.
  The expert receives the environment, task, validated clauses, accepted RM and node
  descriptions, declared propositions, explicit runtime API, and bounded feedback.
  It uses the generator engine; its associated critic uses the critic engine when
  the compiler critic is enabled. AST validation always applies. At most three labeling
  candidates are tried against the same accepted RM; exhaustion stops the run.
- Compiler bundles reuse accepted compiler labeling and node descriptions without
  additional generation calls. Persist predicates in `labeling.py` before execution;
  tests select a saved file and use the existing fixed predicate loader. No aggregate
  generated callable or dynamic import swapping is required.

## Protected invariants

- Every compiler clause uses only propositions declared by that environment.
- In compiler mode, one task's clauses have conjunction semantics; incompatible hard clauses are
  rejected rather than weakened, and a soft clause may be violated only at its recorded cost,
  never silently dropped.
- Separate tasks remain separate RMs even when they share propositions or subgoals.
- Task terminology is used consistently across CLI, web, configuration, prompts, and
  output; the removed instruction and priority-override interfaces are not aliases.
- In compiler mode, the RM is accepted/finalized only after the enabled critic accepts the same
  compiled attempt.
- Compiler presentation and critic improvements must preserve ARM-FM baseline prompts
  and published evidence. A declared `## Labeling API` replaces only the marked labeling-API
  regions and `${api}` in both modes; it is the only labeling surface (no MiniGrid default).
  Shared format adapters change representation without redesigning the compiled machine.
- Critics must follow declared finals, state memory, fallback rules, and one reward
  per step. They must not invent states, transitions, or extra task requirements to
  justify rejection; correct conjunctive decomposition and zero-reward progress rows
  are valid compiler output.
- In compiler mode, all generation steps use the generator model and all enabled critics
  use the critic model. When the critic is enabled, the resolved model identifiers must
  differ; an identical pair is a configuration error. Provider failures do not silently
  fall back to another provider or exchange the models' roles.
- Every completed compiler result carries a description for each declared node in the
  same identity order used at the shared text boundary. Descriptions cannot change
  compiled topology, rewards, accepting states, or rejecting states.
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

The clause generator does not know the final composed RM. A separate tagging request
can describe that actual machine and give the RM critic more context. This adds provider
cost and latency; shape validation does not prove the descriptions' semantic correctness.
ARM-FM baseline generation remains unchanged. Compiler bundles reuse these accepted
descriptions rather than asking another model to describe the machine again.

Using a different model for criticism provides another model's judgment instead of asking
the generating model to review its own artifacts. Different identifiers do not guarantee
independent reasoning or correct verdicts; grounded critic prompts and deterministic
validation remain necessary. The two critics share one model because their roles differ
through their inputs and prompts, while both challenge the same generator.

## Enforcement

- Task and clause boundaries are implemented in `app/src/compiler/pipeline.py` and
  `app/src/compiler/reward_layer.py`.
- Compiler text serialization and import reuse the ARM-FM format in
  `app/src/compiler/rm_format.py`, which the runtime also imports;
  `tests/test_reward_machine_format.py` checks interoperability.
- Clause count, exact arity, pattern-specific priorities, and proposition grounding
  share schema and runtime validation in
  `app/src/engines/structured.py`.
- Bounded refinement, strict critic schemas, and atomic batch output are implemented in
  `app/scripts/generate_rm.py` and `app/src/engines/generic_engine.py`.
- Compiler description-list validation belongs to `app/src/engines/structured.py`;
  request context, stage ordering, and bounded retries belong to the shared engine
  and compiler orchestration. Focused engine and orchestration checks enforce these
  contracts; description fidelity remains Review-only.
- Provider adapters in `app/src/engines/provider_engines.py` enforce the selected
  provider/model contract, selected Antigravity agent, and no-execution boundary.
- Role model resolution belongs to `Configuration.generator_model` and
  `Configuration.critic_model` in `app/src/config/config.py`. Compiler setup in
  `app/src/utils/generation.py` validates enabled critics' required, distinct model
  identifiers and creates the role engines once; `app/scripts/generate_rm.py` routes
  compiler generation and criticism. Shared labeling retries live in
  `app/src/arm_fm/generation.py`; compiler prompt contracts remain under `compiler-rm`.
  Focused configuration, orchestration, and web checks in
  `tests/test_generation.py`, `tests/test_pipeline_orchestration.py`, and
  `tests/test_web.py` enforce precedence, baseline isolation, routing, reuse, and
  critic disabling. Different model identifiers cannot establish independent reasoning
  or semantic correctness; those remain Review-only.
- Reusable prompt contracts and rendering functions are packaged under `app/src/prompts`,
  while deterministic compiler ownership remains in `app/src/compiler/`.
- Compiler critic instructions and worked examples live in
  `app/src/prompts/compiler-rm/reward-machine-critic.system.md`; baseline prompts
  remain separate under `app/src/prompts/arm_fm/`. Model compliance and preservation
  of baseline prompts and published evidence are Review-only. Runtime enforcement
  is listed in [RM execution](rm-execution.md).

## History

- 2026-09-18: Qualified formal translation and compiler critics as compiler-mode rules;
  retained one RM per task and shared-policy transfer across both generation modes.
- 2026-09-21: Standardized generated bundle state names at the compiler adapter only.
- 2026-09-22: Allowed a warned run with both critics disabled as an explicit fallback; the compiler
  still requires every enabled critic to accept the same attempt before finalizing.
- 2026-10-11: Labeling generation follows the environment's declared `## Labeling API` in both
  modes; MiniGrid prompts stay byte-identical when no section is declared.
- 2026-10-12: Labeling generation requires a declared `## Labeling API` (user decision); plain
  RM compilation without labeling does not. The MiniGrid default surface and MiniGrid-only prompt
  regions were removed, so MiniGrid prompts changed; earlier MiniGrid bundles stay usable for training.
- 2026-10-12: Compiler redesign (user decisions): IBM's 8 templates and formulas, hard/soft per
  clause, FL-AT's product with a reward layer, one critic after compilation, zero or one final
  state plus `REJECTING_STATES`. Design and sources: `docs/COMPILER_REWARD_DESIGN.md`.
- 2026-10-13: One template catalog (meanings, IBM formulas, cue words, worked examples) shared by
  the creator and the critic; provider HTTP 400s repeated 1 s apart inside each request (user decisions
  at the result gate).
- 2026-10-14: Attempts count critic rejections only, with `--attempts` up to 10 and visible warnings
  for uncounted reruns; one shared `--reasoning` level for both models; the task is assumed
  feasible, no refusal field (user decisions, iteration 2).
