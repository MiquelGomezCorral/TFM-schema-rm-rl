# Natural-Language Tasks and Composite Reward Machines

## Summary

Replace instructions with tasks throughout the application. Each task is unrestricted natural-language input, decomposed by the model into 1–10 supported clauses. All clauses for one task are composed into one RM; separate tasks always produce separate RMs.

## Implementation Changes

- Replace `--instruction` with repeatable `--task`; remove `--priority` entirely. Rename configuration, compiler, web UI, logs, CSS identifiers, validation messages, and README terminology. Do not retain instruction aliases.
- Change structured model output to a task containing `clauses`, where every clause has:
  - normalized natural-language text;
  - one supported IBM pattern: `Existence`, `ExistenceTwo`, or `Precedence`;
  - declared proposition identifiers;
  - inferred priority: `none` for unary clauses and `soft` or `hard` for precedence.
- Tune the prompt to interpret ordinary language semantically, preserve ordering/repetition, reject ambiguity and unsupported patterns, and never invent propositions or generate LTLf/RM topology. Categorical ordering is hard; preference wording is soft.
- Represent a task proposal as the original task plus its clause proposals. Show every clause’s normalization, pattern, propositions, inferred priority, LTLf, and reward behavior during the existing batch approval.
- Compile each clause through IBM templates and FL-AT/MONA, normalize it with the existing deterministic compiler, then form a reachable conjunction product:
  - product final state only when every clause is final;
  - any hard-clause rejection enters one absorbing dead-end with zero reward;
  - unreachable product final means incompatible clauses and rejects the task;
  - zero-reward self-loops remain implicit;
  - independent submitted tasks are never composed.
- Apply the selected fixed paper-style shaping:
  - maximum 10 clauses per task;
  - preferred/unary clause completion: `+0.1`, once;
  - soft reverse or simultaneous ordering: `0`;
  - hard reverse or simultaneous ordering: zero-reward dead-end;
  - transition completing the whole task adds `+1.0`;
  - simultaneous clause completions sum their one-time rewards.
- Remove unused medium/strong priority levels and the old graded reward table. Preserve the existing numbered output convention: one task uses the requested filename; multiple tasks use `name-1.rm`, `name-2.rm`, etc.
- Update `docs/LTLF_TASK_LANGUAGE.md` and README so composite clauses are current behavior rather than future work. Leave source-paper wording untouched.
- Reconcile the current partial task rename without reverting unrelated dirty-worktree changes. Do not update `.agents/*` memory without separate authorization; report its stale “instructions into one RM” decision.

## Public Interfaces

- CLI: `generate-rm --task TEXT [--task TEXT ...]`; no `--instruction` or `--priority`.
- `Configuration.tasks` replaces `instructions`; stored priority overrides disappear.
- Proposal results become task-level objects containing clause proposals.
- Compilation results retain one result per task and expose the task’s clause DFAs as a tuple.

## Verification

- Run syntax/import checks and the project readiness commands using the configured Python 3.13 environment.
- Verify CLI and web UI expose only task terminology and no priority selector.
- Use a deterministic, non-live check for:
  - one single-clause task;
  - one multi-clause task with intermediate `+0.1` rewards and final `+1.0`;
  - soft reverse/simultaneous completion receiving no clause reward;
  - hard violation entering an absorbing dead-end;
  - contradictory hard clauses being rejected as unsatisfiable;
  - two submitted tasks producing two independent numbered outputs.
- Inspect the final diff and perform one independent correctness review.
- Do not call an LLM or MONA live without explicit approval, consistent with the project workflow.

## Assumptions

- Clause conjunction is the only composite operation; disjunction and optional branches remain unsupported.
- The ten-clause limit keeps pre-terminal shaping below the `+1.0` completion reward, following ARM-FM’s terminal-dominance condition.
- Recoverable regression penalties are deferred because the currently executable patterns have no regression transitions; add matched negative rewards when such patterns are introduced.
- Shared policies, state-language embeddings, RL training, and cross-task RM composition remain out of scope.
