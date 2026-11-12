# Thesis benchmark

## Intent

The thesis compares three ways to reward the same agent on the same tasks: no reward machine (the
environment's own reward), fresh ARM-FM machines, and FARM machines. The comparison must be fair,
repeatable, and judged by something that belongs to neither pipeline, so a result means the same
thing whichever arm produced it.

## Current decisions

- **Arms and rewards.** The no-RM arm trains on the environment reward. The ARM-FM and FARM arms
  train on the RM reward only (`reward_source: rm`). Every arm also reports environment success.
- **Fresh ARM-FM machines.** ARM-FM bundles come from `generate-larm --mode arm-fm` with their own
  labeling and state descriptions, from the same small generator and critic pair as FARM (through
  the explicit `arm_fm_critic` opt-in), with no human fix. A failed or unlearnable ARM-FM machine
  is "no data" for that card. The first version and the authors' bundles are not arms.
- **Task cards first.** Every task is a card in `experiments/benchmark/<suite>/tasks.json`, fixed
  before generation and approved by the user: the wording both pipelines receive, the expected
  clauses, solving and wrong plans, and whether the environment reward matches the task.
- **Independent judge.** A card's clauses are evaluated with direct finite-trace rules for the eight
  DECLARE templates, on reference labels computed from the environment, never on a pipeline's own
  labeling. Judged success (every hard clause holds) is the primary task metric for every card and
  arm; environment success is reported beside it.
- **Statuses.** A bundle is `complete`, `pipeline-failed` (final: its runs are `no-data`),
  `provider-error` or `incomplete` (both retried on the next run). A run is `finished` (skipped on
  rerun), `interrupted` (restarted from zero), `timed-out` (kept; retried only on request) or
  `no-data`.
- **Ablation.** Six switches each turn off one FARM reward part: progress, well, soft break, soft
  pending, end judgment, and the recurrent soft penalty. Completion is never turned off. Turning off
  the recurrent penalty changes the machine's structure. A part the task does not contain makes that
  switch a documented no-op, which is not trained.
- **Time-limit asymmetry.** FARM machines charge the items still open at any episode end; ARM-FM
  machines get 0 at the time limit, as in the ARM-FM paper. Every results table and page says so.
- **Cross-critic.** Each pipeline's critic also judges the other pipeline's machines. The two
  directions are reported apart, never pooled, each with a note on what its critic could see.
- **Spending gate.** Full suites wait until the user records the prompt-example budget decision in
  `experiments/benchmark/prompt-budget.md`.
- **Provenance.** Every bundle carries a stamp: commit, dirty flag, models, and counts taken from
  per-call records (`null` when unknown). Only bundles generated from one clean, frozen `main`
  commit are final; all others are provisional.
- **What is committed.** Cards, bundles, trace records and result summaries under
  `experiments/benchmark/` are committed; run folders, logs, checkpoints, Plotly HTML and GIFs are not.
- **Event room.** `MiniGrid-ServiceRoom-v0` has fixed geometry; its seeded event schedule (the siren
  and the falling box) is its only randomness.

## Protected invariants

- RM arms never train on the environment reward, and the no-RM arm never uses an RM.
- The judge never reads a pipeline's labeling or RM and never calls `nl2ltl`.
- A pipeline failure stays "no data": no arm gets a human fix or retries the others do not get.
- Both pipelines receive the same card wording, environment file, generator and critic.
- A results table without the time-limit asymmetry line, or with pooled cross-critic numbers, is wrong.
- With every reward switch at its default, compiled RM text is byte-identical to the text from
  before the switches existed.

## Rationale and tradeoffs

Judging on reference labels keeps each pipeline's labeling mistakes inside its own results instead
of inside the yardstick. Evaluating the eight templates directly is smaller than parsing LTLf and
keeps the judge apart from the stack FARM itself uses; the cost is a second definition of the
templates, cross-checked against nl2ltl's formulas. Fresh ARM-FM machines from the same small
models compare generation methods, not models; the authors' bundles would mix both. Counting a
wrong machine as "no data" measures what each pipeline delivers on its own. Skipping finished runs
and restarting interrupted ones from zero was chosen over checkpoint resume because runs are short
and a restart is easier to trust.

## Enforcement

- `app/src/benchmark/declare_judge.py` with `tests/test_declare_judge.py`: the judge rules.
- `trace-bank`, `replay-traces`, `rm-facts` and `test-rl --judge`: card checks and judged results.
- `generate-suite` and `run-suite`: statuses, skip and retry rules, arm settings, call caps.
- `ablate-rm`: which term each switch owns, and no-op detection.
- `aggregate-suite`: the asymmetry line on every table and per-direction cross-critic summaries.
- Card approval, no human fixes, equal model pairs and the prompt-budget decision are Review-only:
  they are rules about how the experiment is run, which no check can observe.

## History

- 2026-11-12: Created for the thesis testing program (user decisions at gate 1 and the plan
  critique of workflow run `testing-plan-2026-11`).
