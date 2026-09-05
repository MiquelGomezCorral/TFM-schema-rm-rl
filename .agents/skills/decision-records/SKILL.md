---
name: decision-records
description: Assess, create, update, and reconcile repository decision records during implementation planning and review. Use when work may change important non-derivable product or architecture intent, or when checking a diff against recorded decisions.
---

# Decision records

Preserve important intent behind a feature without turning the repository into a changelog.
Decision records are living current-state documents; Git preserves their complete history. Code,
schemas, tests, and checks remain authoritative for facts they can enforce.

## Scope and trigger

Always finish with exactly one assessment: `Decision records: create`, `update`, or `no change`,
followed by a concise reason or record link. A narrow task may skip planning, but it still reports
`no change` when no durable intent is affected.

Record a decision when non-derivable intent exists and at least one signal applies:

- Feature success semantics could regress while the feature still appears functional.
- Behavior crosses package, compiler, CLI, web, or public-contract boundaries.
- The choice affects security, privacy, reliability, performance, availability, or data integrity.
- Reversal is expensive or dangerous.
- A plausible rejected alternative is likely to recur.
- The change establishes a reusable, blessed approach.
- A critical constraint cannot be encoded mechanically.

Do not record routine fixes, mechanical refactors, self-describing local code, progress notes, or
facts fully owned by code or checks. Prefer updating an existing concern record over creating a new
file; create a file only for a distinct stable concern.

## Discovery

1. Read `docs/decisions/index.md` first.
2. Use the index to discover applicable records, and independently inspect every changed path under
   `docs/decisions/**` whether or not it is indexed.
3. For a non-trivial plan, state the exact record and index changes before implementation. Do not
   write proposed record or index changes before developer approval; plan approval authorizes only
   those exact proposed changes.

Records live at `docs/decisions/<product-capability>/<stable-concern>.md`. Each record contains:
`Intent`, `Current decisions`, `Protected invariants`, `Rationale and tradeoffs`, and `Enforcement`.
`History` is optional and dated; use it only when evolution context is useful.

## Writing and evolution

- Keep current intent in the main sections; edit it when the decision changes or needs clarity.
- Append dated history only when the previous choice or timing explains the current one.
- Remove obsolete framing when a clearer current contract replaces it.
- Link enforcement to authoritative code, schemas, tests, or checks. If none can enforce it, say
  `Review-only` and state why.
- Update the index atomically with a created, renamed, moved, or removed concern file.
- Never append ordinary bug fixes, implementation progress, or PR-by-PR changes.

## Reconciliation

During cleanup of wholly uncommitted implementation work, use `HEAD` as the comparison base.
During review or shipping, use the target-branch merge base. In either case, inspect the full tracked
change from that base through the worktree plus untracked files; read both the base and current
versions of every applicable changed record. Verify every record or index mutation against the exact
approved plan. An unapproved removed or relaxed invariant is a `Conflict` even when the current code
matches the rewritten record. If the base or approval evidence cannot be resolved, pause.

Treat a missing or stale index entry for a created, moved, or removed record as
`Reconciliation: Pending`.

Compare changed behavior with applicable `Protected invariants`. If they conflict, do not infer
whether the difference is intentional. Show the developer:

1. The recorded requirement.
2. The implementation behavior and evidence.
3. These choices: revise the code, revise the record, or reopen planning.

Pause until the developer chooses. A code change requires the relevant review gate again; a record
change requires fresh review before shipping. Never silently rewrite a record to match code.

## Output contract

For assessment or planning, report:

```text
Decision records: <create|update|no change> — <reason or link>
Record changes: <exact paths and sections, or none>
Enforcement: <authoritative guard or Review-only>
```

For reconciliation, emit both an assessment and a reconciliation result. For conformance, use
`Decision records: no change — final implementation conforms to <record links>` followed by
`Reconciliation: Conforms — <records checked>`. For an unresolved conflict, use
`Decision records: no change — paused pending developer choice` followed by
`Reconciliation: Conflict — <record requirement, implementation evidence, and the choices to revise
the code, revise the record, or reopen planning>`. Do not claim conformance when a relevant record
was not found or read.

For a required create or update, use `Decision records: <create|update> — <reason>` followed by
`Reconciliation: Pending — <missing approval, record/index edit, or review evidence>` when the exact
record/index edits are not approved, present, indexed, and freshly reviewed.

## Examples

### Narrow task

> Fix a typo in an existing validation error.

```text
Decision records: no change — wording-only fix; no durable behavior or intent changes.
Record changes: none
Enforcement: existing validation code
```

### Significant feature

> Add a public compiler option that must preserve approval and output-format behavior across CLI and web entry points.

```text
Decision records: create — public contract and approval behavior cross CLI and web boundaries.
Record changes: docs/decisions/compiler/public-options.md — create with Intent, Current decisions, Protected invariants, Rationale and tradeoffs, and Enforcement; docs/decisions/index.md — add the concern link and one-line description.
Enforcement: CLI/web integration checks; remaining rationale is review-only.
```

### Conflict

> A record requires every proposal to receive human approval, but the diff compiles proposals automatically.

```text
Decision records: no change — paused pending developer choice
Reconciliation: Conflict — the compiler decision record requires human approval; the changed pipeline bypasses approval (pipeline evidence). Developer choice required: revise the code, revise the record, or reopen planning.
```

## Boundaries

Do not create product APIs, database tables, generated indexes, validators, dependencies, or
speculative capability folders as part of this skill. Do not resolve conflicts without developer
approval.
