# ARM-FM catalogue and evidence

## Intent

Keep the ARM-FM recreation set reproducible without presenting inferred environment
details or reconstructed prompts as if they were published artifacts.

## Current decisions

- Each environment lives under `examples/arm-fm/<environment>/` and has an
  `environment.md` describing its runtime and proposition vocabulary.
- Every environment has `tasks.md`. It contains paper-reported tasks, source-recovered
  task wording or semantics, and clearly labelled atomic probes.
- Add `reward-machines.md` only when a complete RM is printed in the paper or available
  in the released ARM-FM repository. Add `task-rm-pairs.md` only when both task and RM
  evidence exists.
- Preserve published RM text, including format defects, in the RM file. Explain defects
  next to the block; do not silently repair the evidence used for comparison.
- Use three evidence labels: `source-recovered` (the source associates the task and RM),
  `inferred` (the task or mapping is reconstructed from separate evidence), and
  `paper-associated` (the paper names the task and RM family but does not release the
  original generator pair).

### Environment coverage

| Environment | Task evidence | RM evidence | Pair status |
|---|---|---|---|
| DoorKey | released generator trace | released final RM | source-recovered |
| BlockedUnlockPickup | released generator trace | released final RM | source-recovered |
| UnlockToUnlock | released generator trace | released final RM | source-recovered |
| KeyCorridor S6R3 | paper description and official task | released final RM; trace has wrong mission | inferred |
| UnlockPickup | paper intervention table and official task | no complete RM | task-only |
| Craftium diamond | paper task description | paper Appendix A.9 block | paper-associated |
| Meta-World five tasks | paper Appendix A.2.3 | one generic Appendix A.9 RM | paper-associated |
| XLand-MiniGrid | first 1,000 `medium-1m` rulesets and Figure 16 example | no task-specific RM artifact | task-only |

Official runtime IDs and repository links are maintained in the catalogue README and
the corresponding environment files, not duplicated in this record.

## Protected invariants

- Evidence level is stated for every task–RM association; inferred content is never
  labelled exact.
- Missing artifacts remain missing. A task description must not manufacture a finalized
  RM, and a generic RM must not be presented as task-specific when the source does not do
  so.
- The released KeyCorridor S6R3 artifact is used despite the paper table's S3R3 typo;
  the discrepancy remains documented.
- The XLand first-1,000 set is treated as benchmark data, not expanded into invented
  natural-language prompts.

## Rationale and tradeoffs

This layout makes the recreation useful for experiments while preserving what can be
verified. It intentionally tolerates duplicated generic Meta-World RM blocks in each
task directory so each environment example is standalone; the source of truth remains
the paper Appendix A.9 block.

## Enforcement

- Environment proposition syntax is enforced by `EnvironmentDescription` in
  `app/src/models/environment.py`.
- Catalogue structure and evidence labels are review-only, checked by the Markdown
  validation command used for `examples/arm-fm`.
- Source artifacts: `docs/ARM-FM/ARM-FM.md` and the repository linked from
  `examples/arm-fm/README.md`.
