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
- **Attempts.** Both pipelines get up to 10 reward-machine generation attempts, the first included.
  Labeling, descriptions and FARM tagging keep their own limits.
- **Labeling repair.** Before any repair, `repair-labeling` gives each bundle one class from replays of
  its card's traces: `missing`, `load`, `crash`, `wrong` or `ok`. That class is the measured failure
  rate and is never overwritten. A failed labeling is then repaired by the bundle's own generator
  (`deepseek-v4.1-flash` or `glm-5.3-flash` only) in up to 10 rounds, each shown the failure
  evidence. The Reward Machine is never touched. A bundle still failing after the loop is `unfixed`
  and goes to an outside agent step; if the agent changes the labeling and it then checks `ok`, the
  bundle is `fixed-by-agent` and still counts as failed.
- **Prompts.** Each pipeline keeps its own prompts. ARM-FM runs as its authors ran it, without worked
  examples; FARM keeps its examples as part of the method. The paper states the asymmetry and any gain
  from the examples is a result to show. No control run.
- **Layouts.** Training uses procedural layouts. Evaluation uses a fixed set of eval seeds per
  environment, the same for every run and arm.
- **Paraphrases.** The claim is clause identity: the same clauses give the same machine and so the same
  training. The paraphrase suite only generates.
- **Card misses.** A pipeline's miss on a card counts as its failure only when the coordinator and an
  adversarial agent that has not seen the pipeline's output agree the card's expected result is right.
  Otherwise the card is flagged "review later" and is not counted.
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
- A pipeline failure stays "no data": no arm gets a human fix or retries the others do not get; both
  get the same attempt limit (up to 10).
- Both pipelines receive the same card wording, environment file, generator and critic.
- A results table without the time-limit asymmetry line, or with pooled cross-critic numbers, is wrong.
- With every reward switch at its default, compiled RM text is byte-identical to the text from
  before the switches existed.
- Labeling repair never edits a Reward Machine and never replaces the class recorded before repair.
  A repaired or agent-fixed bundle is still a failure in the failure rate.

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
- `repair-labeling` with `app/src/benchmark/labeling_repair.py`: the classes, the 10-round limit, the
  small-model gate, and the record beside each bundle (it keeps the machine's hash and the first class).
- `aggregate-suite`: the asymmetry line on every table and per-direction cross-critic summaries.
- Card approval, no human fixes, equal model pairs and the prompt-budget decision are Review-only:
  they are rules about how the experiment is run, which no check can observe.

## History

- 2026-11-12: Created for the thesis testing program (user decisions at gate 1 and the plan
  critique of workflow run `testing-plan-2026-11`).
- 2026-11-12: Result-page answers (user): both pipelines get up to 10 generation attempts; each keeps
  its own prompts and the paper states the asymmetry; procedural training layouts with fixed eval seeds;
  paraphrases claim clause identity and only generate; a card miss counts only when its expected result
  is confirmed. The progress-ablation control and the -0.5 sensitivity run are dropped (no record
  listed them as planned).
- 2026-11-12: Labeling repair rule added with the `repair-labeling` command (testing program slice
  `labeling-repair`).
