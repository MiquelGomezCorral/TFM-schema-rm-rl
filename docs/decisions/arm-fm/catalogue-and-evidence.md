# ARM-FM catalogue and evidence

## Intent

Keep the ARM-FM recreation set reproducible without presenting inferred environment
details or reconstructed prompts as if they were published artifacts.

## Current decisions

- Each environment lives under `examples/arm-fm/<environment>/` with two description files
  (`docs/ENVIRONMENT_AUTHORING.md`). `environment.md` holds the facts an agent building a
  Reward Machine needs: the environment, the proposition semantics in plain words, the
  constraints, what can and cannot happen, one real trace, the propositions and example tasks,
  and what is not known. `environment-code.md` holds all implementation (labeling functions,
  adapters): the `## Labeling API`, sources, runtime setup, truth conditions in code, the
  evidence for each fact, links and build steps. It refers to `environment.md` and never
  repeats a fact.
- Every environment has `tasks.md`. It contains paper-reported tasks, source-recovered
  task wording or semantics, and clearly labelled atomic probes.
- Every environment also has `tasks.json`, a machine-readable companion with exactly
  `env`, `env_description`, and `tasks` fields. Its task strings mirror the natural-
  language inputs in `tasks.md`; evidence prose and benchmark metadata are excluded.
- Add `reward-machines.md` only when a complete RM is printed in the paper or available
  in the released ARM-FM repository. Add `task-rm-pairs.md` only when both task and RM
  evidence exists.
- Preserve published RM text, including format defects, in the RM file. Explain defects
  next to the block; do not silently repair the evidence used for comparison.
- Use three evidence labels: `source-recovered` (the source associates the task and RM),
  `inferred` (the task or mapping is reconstructed from separate evidence), and
  `paper-associated` (the paper names the task and RM family but does not release the
  original generator pair).
- Generated per-task bundles are separate from the published evidence catalogue. They keep
  task/environment inputs, generated artifacts, attempts, settings, validation, and provenance.
  Reconstructed prompts and artifacts are explicitly identified; they are not source recovery.

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
- `tasks.json` uses repository-relative paths for `env_description`, and every listed
  path resolves to the environment's `environment.md`.
- `environment.md` holds no implementation: no `## Labeling API`, source links, gym ids, package
  versions, code expressions, file paths, citations, run counts, build steps, or reasons that
  cite the labeling code or prompts. It has exactly these sections: Environment; Objective and
  episode boundary; Proposition semantics; Constraints; What the agent can and cannot do;
  Example trace; Propositions; Example tasks.
- `environment-code.md` holds all implementation (the list above) and adds to the facts file
  without copying it.
- The clause generator and the critic read only `environment.md`. Steps that write code read both
  files as one text: the facts file, a blank line, then the code file. Those are the ARM-FM
  baseline generator and every labeling stage, including labeling in ARM-FM compiler mode.
- The ARM-FM judge reviews generated code, so every ARM-FM bundle manifest (baseline, compiler and
  failed compiler) stores that same joined text as `environment_markdown`. The opt-in state
  embedding context stays facts-only.
- Missing published artifacts remain missing in the evidence catalogue. New task-specific
  RMs may be generated in reconstructed bundles, but must not be presented as released
  artifacts. A published generic RM must not be presented as a recovered task-specific RM.
- The released KeyCorridor S6R3 artifact is used despite the paper table's S3R3 typo;
  the discrepancy remains documented.
- The XLand first-1,000 set remains benchmark data. Deterministic task rendering and
  reconstructed generator prompts are permitted and labelled as reconstructed; they are
  never presented as the authors' unpublished original prompts.
- Catalogue entries are task and RM evidence only. Runtime environments are generic
  (`make_environment` is `gym.make` on a registered id); the XLand-MiniGrid and Meta-World
  integrations were removed and will be rebuilt when training uses them. Compiler labeling
  targets any environment whose `environment-code.md` declares a labeling API (MiniGrid by default).
- Craftium is rebuilt for training as a reconstructed diamond task (`Craftium/Diamond-v0`: Lua
  tool grants per milestone, sparse diamond reward, per-step state snapshot for labeling). It is
  not the paper's unpublished configuration.
- `babyai-chosen-mission` is this project's own catalogue entry (missions written for the
  experiments, not paper evidence).

## Rationale and tradeoffs

This layout makes the recreation useful for experiments while preserving what can be
verified. It intentionally tolerates duplicated generic Meta-World RM blocks in each
task directory so each environment example is standalone; the source of truth remains
the paper Appendix A.9 block.

## Enforcement

- Environment proposition syntax is enforced by `EnvironmentDescription` in
  `app/src/models/environment.py`.
- `EnvironmentDescription.from_file(path, code=True)` in `app/src/models/environment.py` owns the
  join. The callers that pass `code=True` are `generate_larm` in `app/scripts/generate_larm.py`
  (the baseline generator and the failure manifest; `app/scripts/evaluate_larm.py` re-parses the
  stored text) and the `--labeling` stage of `_Pipeline` in `app/scripts/generate_rm.py`, which
  loads it from `CONFIG.environment` and keeps it in the result so the bundle manifest stores it
  (compiler labeling, used by `generate-larm --mode compiler` too).
  `setup_environment_and_engines` (`app/src/utils/generation.py`) loads the facts file alone for
  the clause generator and the critic, so joined text never reaches their prompts. The web app
  takes the code file as a second optional input (upload or paste), writes it as
  `environment-code.md` beside the facts file in the run's temporary folder, and refuses a
  labeling run without it. The split between the two files is Review-only: no check tells
  implementation from fact.
- Catalogue structure and evidence labels are review-only, checked by the Markdown
  validation command used for `examples/arm-fm`.
- Source artifacts: `docs/ARM-FM/ARM-FM.md` and the repository linked from
  `examples/arm-fm/README.md`.
- Separation of reconstructed bundles from recovered evidence is Review-only until bundle
  provenance checks are implemented; provenance claims still require source review.

## History

- 2026-09-18: Distinguished missing published evidence from newly reconstructed artifacts;
  authorized explicit XLand prompt reconstruction and inspectable per-task bundles.
- 2026-10-11: Rebuilt Craftium as a reconstructed diamond task and added the project's own
  BabyAI chosen-mission entry.
- 2026-10-18: Split each environment description into `environment.md` (facts, read by the
  generator and the critic) and `environment-code.md` (sources and code, for code agents), so
  agents that only build Reward Machines get no code context (user decision). The pipeline is
  unchanged for now; the Labeling API stays in `environment.md` until it reads the code file.
- 2026-10-23: `environment.md` holds no implementation and `environment-code.md` holds all of it,
  including the `## Labeling API` (user decision: "no code references on the normal environment
  file"). Steps that write code (the ARM-FM baseline generator and every labeling stage) load the
  two files as one text, so the Labeling API no longer has to stay in the facts file; the clause
  generator and the critic still read the facts file alone (user decision: the code file exists
  for steps that generate code). ARM-FM bundles store the joined text because the judge reviews
  code, and the web app gained a code-file input so web labeling keeps working.
