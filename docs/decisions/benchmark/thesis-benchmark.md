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
- **Empty pass.** Each clause has an activation: whether its trigger happened in the episode
  (`a` for Existence, ExistenceTwo, RespondedExistence, Response and ChainResponse; `b` for
  Precedence; `a` or `b` for NotCoExistence; none for Absence, a pure prohibition). A conditional
  clause that holds without its trigger is an empty pass. `judge.json` records the activations per
  episode and the share of episodes that activated each clause, and reports non-empty judged
  success (judged success and every hard clause with a trigger activated) beside judged success,
  which keeps its definition. Judged episodes also report the positive and the negative part of
  the machine reward and of the environment reward, beside the total.
- **Episodes that cannot start.** A machine whose start state is final, or reaches a final state
  from the start, ends every episode after the first action, so its rules pass untested
  (`machine_too_simple`, with the reason, in `judge.json`; a rejecting state stops the walk). The
  judge walks the machine with the labeling's valuation at reset held fixed, once per test reset
  seed, and flags the run when any seed reaches a final state (the reason names the seeds); the
  static scan of machine files, with no layout, follows only `else` and always-true guards.
  `judge.json` says which form ran (`machine_too_simple_check`). A guard that needs a proposition
  the labels at reset do not give is unknown: it does not fire (neither `a` nor `!a`) and
  `machine_too_simple_unknown` names it; the check never crashes a run. A test episode the machine
  ended in a final state, with the environment not done, within
  `max(1, ceil(0.10 * expected))` steps cannot start, where `expected` is the median length of the
  card's solving plan over its reset seeds: that episode is judged failed whatever its clauses say.
  `raw_judged_success` keeps the judge's value before this rule, `mean_judged_success` and
  non-empty success follow the corrected one, and a run is flagged when more than half of its test
  episodes cannot start. The 5% limit is reported beside, not applied. Same rule for every arm
  (user, 2026-11-14).
- **Shared no-RM run.** The no-RM agent never sees the card text, so one no-RM run is trained per
  identical training configuration (the `train-rl` config without the name, and the seed) and
  judged against every card sharing it, whatever suite asks. The owner of a key is, in order: a
  finished run under the runs root whose *saved* `config.yaml` (minus the name) and seed match
  (last night's closed-set runs count), a run another driver has claimed, or the first open card,
  claimed in a file per key. A follower waits for a claimed owner; while the owner is stopped
  (timed out, interrupted, failed) the follower's row names the owner, its state and exit code.
  Each card still has its own run folder, linked to the owner's files, so results are read per
  card. Any config difference (environment options, events, required items, timesteps, learner)
  is a separate run. A run with an undecided learner (`TBD`) is never grouped.
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
- **Labeling vocabulary.** In both pipelines a labeling covers the propositions the accepted
  machine's guards mention (`PaperRewardMachine.used_propositions`) plus, transitively, the
  propositions their facts-page definitions read: `key_lost` reads the previous `has_door_key` (or
  `has_key`) and `door_open`, so an event used by a guard pulls those in
  (`EnvironmentDescription.labeling_propositions`). The generation
  coverage check, FARM's prompt and critic list, and every reader that loads a labeling (training,
  replay, labeling check, judge inputs) use that set. The ARM-FM prompt wording is unchanged; only
  what the code passes and checks changed. The paper is about Reward Machine generation, so the
  labeling only has to be decent for the machine it serves.
- **Accepted steps are kept.** A failure keeps every step a critic or check accepted. A FARM run that
  fails after the critic accepted its machine saves the machine, clauses, compiler attempt, state
  descriptions and the failed stage's tries; `stage_status` says which stage failed and `status.json`
  stays `pipeline-failed` with a reason that names the stage. `repair-labeling` checks, repairs and
  finishes such a bundle like an ARM-FM one, and `regenerate-labeling` reruns only the labeling loop on
  it (old labeling and tries kept in a sidecar). A bundle rebuilt from a log is marked
  `restored_from_log`.
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
- **Box-carry cards.** Trained agents never picked the box up on the box cards, so the box rule
  never triggered and the card passed by doing nothing. The environment now provides the pickup:
  the box-fall cards (`tpl-chain-response-{1,2,3}-{goal,nogoal}`, `cx-box`) also exist as carry
  versions (`<id>-carry`, suite `box-carry`) in `MiniGrid-ServiceRoom-v0` with `carry=True`, where the
  agent starts holding the box and it falls at a seeded step from 2 to 8, whatever the agent does: the
  drop action does nothing before that fall, and the fall turns the agent to face the box.
  The machine is not asked to reward the first pickup; the environment enforces it. The carry cards
  keep the wording, clauses and `train` flags of their originals, and the originals stay as they are.
- **Forced cards.** Seed-1 judging with the empty-pass check showed two trained cards whose rule never
  triggered, so doing nothing passed: `tpl-response-1-nogoal` (`Response(blocker_moved, has_door_key)`,
  no-RM judged 1.00, non-empty 0.00) and `tpl-responded-existence-1-nogoal`
  (`RespondedExistence(has_door_key, door_open)`, no-RM judged 1.00, non-empty 0.00). Both also exist as
  forced versions (`<id>-forced`, suite `forced-start`; the name is not the card field `forced`)
  whose environment starts the episode with the trigger already true: `MiniGrid-BlockedUnlockPickup-Cleared-v0` (the ball starts away from the door, so
  `blocker_moved` is true at the first step) and `MiniGrid-UnlockPickup-KeyHeld-v0` (the agent starts
  holding the matching key, and `drop` does nothing on the first step). The environment enforces the
  trigger, not the machine; the forced cards keep the wording, clause, paraphrases and `train` flags of
  their originals, and the originals stay as they are. Only cards whose rule seed 1 showed untested get a
  forced version. The forced cards give the trigger at reset, so they test keeping an obligation, not
  reacting to an event. Of the forced runs, only `tpl-response-1-nogoal-forced` seed 1 trains (3 arms),
  labeled "trigger given"; the runs that had not started were dropped (user, 2026-11-14). Reactive cards,
  where the trigger happens during the episode, are proposed as the real test of conditional rules.

## Protected invariants

- RM arms never train on the environment reward, and the no-RM arm never uses an RM.
- The judge's clause verdicts never read a pipeline's labeling or RM, and the judge never calls
  `nl2ltl`. Only the cannot-start rule reads the run's own machine, its episode end and its
  labeling at reset.
- `carry` defaults to off: the original service-room cards and runs behave exactly as before, and a
  carry card's clauses never ask for the first pickup of the box. A carry episode never skips its first
  fall by dropping the box.
- The forced starts live in their own gym ids: `MiniGrid-BlockedUnlockPickup-v0` and
  `MiniGrid-UnlockPickup-v0` build the same envs as before, so the original cards and runs are
  unchanged. A forced episode never loses its trigger at the first step: the ball starts away from the
  door and the key starts in the hands, and `drop` cannot put it down on the first step.
- Judged success keeps its definition (every hard clause holds); the empty-pass check is reported
  beside it, never folded into it.
- An episode the machine ended in a final state at once (the rule above) never counts as judged
  success, and the judge's raw value stays recorded beside the corrected one.
- A shared no-RM run is only shared between cards whose training configuration is identical,
  checked against the owner's saved configuration, never against the request that found it.
- One no-RM training per configuration and seed across suites and existing runs; two drivers never
  train the same key.
- A pipeline failure stays "no data": no arm gets a human fix or retries the others do not get; both
  get the same attempt limit (up to 10).
- Both pipelines receive the same card wording, environment file, generator and critic.
- A results table without the time-limit asymmetry line, or with pooled cross-critic numbers, is wrong.
- With every reward switch at its default, compiled RM text is byte-identical to the text from
  before the switches existed.
- Labeling repair never edits a Reward Machine and never replaces the class recorded before repair.
  A repaired or agent-fixed bundle is still a failure in the failure rate.
- A labeling is never asked to cover a proposition the machine does not use, and no pipeline throws away
  an accepted machine because a later stage failed. Regenerating a labeling never changes the machine.

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

- `app/src/benchmark/declare_judge.py` with `tests/test_declare_judge.py`: the judge rules and the
  activation of each template.
- `app/src/benchmark/early_end.py` with `tests/test_early_end.py`, called by `test-rl --judge`:
  the too-simple machine, the expected length and the cannot-start rule.
- `share_owners`, `find_owner` and `link_shared` in `app/scripts/run_suite.py`: who owns each no-RM
  training and the link; `owner_note` in `app/scripts/aggregate_suite.py`: the owner's state on followers.
- `trace-bank`, `replay-traces`, `rm-facts` and `test-rl --judge`: card checks and judged results.
- `generate-suite` and `run-suite`: statuses, skip and retry rules, arm settings, call caps.
- `ablate-rm`: which term each switch owns, and no-op detection.
- `repair-labeling` with `app/src/benchmark/labeling_repair.py`: the classes, the 10-round limit, the
  small-model gate, and the record beside each bundle (it keeps the machine's hash and the first class).
- `regenerate-labeling` and `generation-table`: the labeling-only rerun and the per-arm acceptance table.
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
- 2026-11-14: Empty-pass check, positive/negative reward split and shared no-RM run added (user,
  after FARM's `tpl-chain-response-1-nogoal` runs 200 steps with reward 0 and judged 1.00; testing
  program slice `judge-metrics`).
- 2026-11-14: Shared no-RM run corrected after review: saved-config check, one owner across suites and
  existing runs, claims, owner state on followers (testing program slice `judge-metrics`, correction 1).
- 2026-11-14: Cannot-start rule added (user: ARM-FM's `tpl-absence-1-nogoal` machine has its start
  state final, so every episode ends after one action and judged 1.00 tested nothing); a waiting
  driver now claims and trains an owner whose other driver died (testing program slice
  `judge-metrics`, correction 2).
- 2026-11-14: Too-simple check walks the machine with the labels true at reset, per test reset
  seed, instead of treating every proposition as false: a `!door_locked` guard on a locked door is
  no longer flagged, an `in_room_a` guard true in the start room is; the static scan keeps only
  `else` and always-true guards (testing program slice `judge-metrics`, correction 3).
- 2026-11-14: Hotfix: a guard that needs a proposition missing from the labels at reset is unknown
  and does not fire, named in `machine_too_simple_unknown`, after the walk crashed 9 of 77 RM
  runs. The invariant "the judge never reads a pipeline's labeling or RM" now covers the clause
  verdicts only, following the user's 12:00 cannot-start rule, which reads the run's machine and
  labeling at reset (testing program slice `judge-metrics`, hotfix 1).
- 2026-11-12: Labeling repair rule added with the `repair-labeling` command (testing program slice
  `labeling-repair`).
- 2026-11-14: Box-carry cards added (user request: enforce the pickup in the environment, not in the
  machine; `carry` option, `experiments/benchmark/box-carry/`, `envs/service-room-carry/`).
- 2026-11-14: Forced cards added (user rule: build forced versions only where seed 1 shows the rule
  untested; enforce the trigger in the environment, not the machine; `MiniGrid-BlockedUnlockPickup-Cleared-v0`
  and `MiniGrid-UnlockPickup-KeyHeld-v0`, `experiments/benchmark/forced-start/`, `envs/minigrid-*-cleared`
  and `envs/minigrid-*-key-held`; testing program slice `forced-cards`).
- 2026-11-14: Forced runs cut to one (user): the forced cards give the trigger at reset, so they test
  keeping an obligation, not reacting; only `tpl-response-1-nogoal-forced` seed 1 trains (3 arms),
  labeled "trigger given", and reactive cards are proposed as the real test of conditional rules.
- 2026-11-14: Cannot-start exception confirmed (user): the judge's rule that reads the run's own machine,
  its episode end and its labeling at reset is needed.
- 2026-11-14: Labeling vocabulary and accepted-steps rules added (user: "the labeling function generations only
  worry about those used by the reward machine"; "we do always keep all the steps that have been
  accepted"); testing program slice `lf-code`.
- 2026-11-14: Vocabulary widened to what the used propositions' definitions read (correction 1 of `lf-code`:
  an RM-only labeling of `key_lost` crashed on the previous `has_door_key`).
