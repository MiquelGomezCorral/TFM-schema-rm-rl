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
  the explicit `arm_fm_critic` opt-in), with no human fix. A failed or unlearnable machine of
  either pipeline counts as not learned on that card, with its reason (user, 2026-11-22; until then
  "no data"). The first version and the authors' bundles are not arms.
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
- **Soft-rule quality.** Judged success says whether the task was solved, not how well the agent
  kept the soft rules (user, 2026-11-20: "it solves the task, but how well? Is it really following
  the human preferences?"). A card with a soft clause also reports, per episode and as run means,
  `soft_break_count`, how many times the episode broke a soft rule, and `any_soft_break`,
  whether it broke one at least once (`mean_any_soft_break` is the share of such episodes). The
  user asked for every break ("how many of the rules have been broken along the way"), and since
  2026-11-21 the count is what the machine charges (user decision D8: count every step, as the
  machine does, so the number is what the agent was charged for). The machine re-arms a broken
  soft rule and reads the step after a break as a fresh start, so the judge restarts the rule on
  that step and every step that breaks it again counts, also straight after a break. So an
  Absence counts each step its event is true, a Precedence each step with `b` before any `a`, a
  ChainResponse each trigger left unanswered (a trigger on the break step itself is not read: `a`
  on three steps in a row with no `b`, then a clean step, counts 2), and a NotCoExistence each
  time both events turn up again after a break. The restarted NotCoExistence forgets the earlier
  side, so one side recurring alone is not a new break: `a=1000, b=0101` counts 1. The count
  follows the default machine (recurrent soft penalty on); with the penalty off the machine
  charges a rule at most once and the judge still counts every break. Existence, ExistenceTwo,
  Response and RespondedExistence never break; they stay open (`soft_open`). `soft_breaks` still
  counts each broken clause once, and judged success is unchanged. The judge owns the count
  (`_break_count`, `app/src/benchmark/declare_judge.py`); `judge.json` and the results table
  show it for every arm side by side. A soft-only card (no hard clause) is learned when neither the every-break
  count nor `soft_open` is above an idle plan's on the same reset seeds, one of them is below it, and the agent
  changes labels more often than idle; every arm is compared this way (user, 2026-11-22). The judge's
  `soft_only` block compares the once-per-rule count, which saturates when a world floods (Lanes: 2.0 for both
  FARM and idle); the idle every-break figure comes from `FP/tools/soft_every_break.py` in agent memory.
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
  (user, 2026-11-14). The paper reports ARM-FM's start-final machines as a limit of its format, not a model error: its prompts
  define a final state as accepting and its runtime ends the episode there, so a recurring rule with no goal
  has no way to say "keep going" (46 of 133 no-goal machines, none of 131 goal machines; user, 2026-11-22).
- **Shop served success.** Shop cards also record `served_count` and `served_success` (at least one
  client served) per test episode, from the reference labels. It is the shop's reported success;
  promises open at the 600-step limit do not affect it. `judged_success` and the columns built on it
  are unchanged (user, 2026-11-16).
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
  pending, end judgment, and the recurrent soft penalty; the `none` control turns nothing off and is
  the machine the six are built from. For `lanes-rules` the control and the variants use the
  hand-built reference machine (`forcing/reference/lanes-rules`), since the ablation studies reward
  parts, not the language side; the `cx-goal-*` cards use their FARM bundles. Completion is never
  turned off. Turning off
  the recurrent penalty changes the machine's structure. A part the task does not contain makes that
  switch a documented no-op, which is not trained. The end judgment is off by default since
  2026-11-18 (`deff802`), so its switch is a no-op on a machine built with the defaults (`ablate-rm`
  names it).
- **Time-limit asymmetry.** Since 2026-11-18 (`deff802`) the end judgment and the owed charge on the
  well edges are off by default (`reward_end_judgment`), so a FARM machine built with the defaults
  charges nothing for the items still open at an episode end. Benchmark runs set
  `time_limit_penalty` to 0 for every RM run (`RM_TIME_LIMIT_PENALTY` in `run_suite.py`), so with
  the defaults FARM and ARM-FM machines both get 0 at the time limit. FARM bundles stored before
  that date still carry the judgment; they are provisional (see Provenance). With the end charge off,
  a hard and a soft copy of one rule can compile to the same machine: `keygift-hard` and
  `keygift-soft` do, and only `reward_promise_cost` (off by default) separates them. Probe of
  2026-11-20: KeyGift's hard rule held on 3 of 3 seeds with the promise cost on and with it off.
  Since 2026-11-20 (user) every results table states how its runs pay a time-out (`time_out_line`
  in `aggregate_suite.py`): with the defaults, "neither method is charged when time runs out"; a
  run whose machine carries an end judgment, or whose penalty is not 0, is named with what it paid.
  Open: the replay page note (`ASYMMETRY_NOTE` in `traces.py`) still states the old asymmetry.
  Until 2026-11-18 (superseded): FARM machines charge the items still open at any
  episode end; ARM-FM machines get 0 at the time limit, as in the ARM-FM paper. Every results table
  and page says so.
- **Cross-critic.** Each pipeline's critic also judges the other pipeline's machines. The two
  directions are reported apart, never pooled, each with a note on what its critic could see.
- **Attempts.** Both pipelines get up to 10 reward-machine generation attempts, the first included.
  Labeling, descriptions and FARM tagging keep their own limits.
- **Reasoning level.** The generator and the critic always run at the same reasoning level, and
  every bundle's stamp records it. The default is `max` since 2026-11-20 (user: "max is still cheap
  enough to use it. dont care about the speed. users wont run this as much as we do"); it was
  `none` before.
- **Seeds.** Every training test runs seeds 1 to 3, forced-start cards included: the final
  `runs.yaml` of every suite says `seeds: [1, 2, 3]` since 2026-11-20 (`ab27c07`, user rule). The
  pilot and tuning runs keep their own seeds.
- **Which cards train.** A card that an idle agent passes, or whose goal already forces its rule,
  does not train (`train: false`); its rule is tested on a card where the trigger comes by itself
  (the forcing suite, a forced-start copy, the siren room). The card fixes of 2026-11-20
  (`ab27c07`) stopped `cx-rules-only`, `tpl-absence-1-nogoal`, `tpl-response-1-nogoal`,
  `tpl-responded-existence-1-nogoal`, `tpl-responded-existence-1-goal`, `tpl-existence-two-1-goal`
  and `tpl-responded-existence-1-nogoal-forced`, and started `tpl-responded-existence-2-nogoal` and
  the new `tpl-existence-two-4-goal` and `tpl-responded-existence-4-goal`. On 2026-11-21 (user)
  `tpl-responded-existence-2-goal` started training. Each card's `notes` and its suite README give
  the reason.
- **One training set for every arm.** FARM, ARM-FM and no-RM train the same 60 cards (user,
  2026-11-22): FARM's 59 trained runs (54 cards, plus the 5 shop cards again under `shop-reward`)
  and `tpl-precedence-soft-2-goal`, picked for coverage (a soft `Precedence` in a third world). The
  two box-carry fall-world cards train on each pipeline's own carry machine. A card where doing
  nothing beats or ties every arm is dropped; none of the 60 is. Each arm's result is over all 60:
  a machine that fails its gates counts as not learned.
- **Side tests.** Failed ARM-FM machines that still let the agent act (a soft rule priced as hard,
  or a wrong plan accepted) train as a labeled side test and never enter the counts; a machine
  whose episode ends before the agent moves never trains (user, 2026-11-22).
- **Reporting by test.** Results are reported per test, never mixed: generation (own wordings and
  rewordings: right machine, same machine across wordings), training on the 60 cards, and side
  tests. Each says how its set was chosen and uses one denominator per row (user, 2026-11-22).
- **No-help count.** A FARM bundle counts as built with no human help when its machine passes the
  gates with no repair, hand retry, reworded card or edited labeling. A state text that is off (it
  names an objective the task lacks) with a right machine does not count against it: the
  state-text stage is inherited from ARM-FM unchanged (user, 2026-11-22).
- **Stated orders.** Since 2026-11-20 (user) every order the task states is required, even when the
  level already forces it: FARM's generator writes its `Precedence`, and FARM's critic rejects a set
  that leaves it out (prompts since `42003cf`). A card answer that drops a stated clause or order is
  no longer an `also_ok` answer (`ab27c07`). An order the task does not state is never added from
  environment facts. What states an order (user, 2026-11-21; FARM's `declare-templates.md` holds
  the rule text): order words; commanded actions with their own verbs in one sentence, joined by
  commas or "and", in their written order, ending at a full stop, a semicolon or a new condition;
  and a compound verb or tool phrase whose second step needs the first ("find and take", "open
  with"). A new sentence is a separate point unless an order word ("Then") opens it. A rule (a
  ban, a preferred order, a condition rule) is never a step of a chain, and several objects under
  one verb, states, counts and items under "in any order" or "both" get no order. Every cue list
  gives examples of a meaning, never a closed set. A condition means the same on either side of
  its sentence: "`b` must happen if `a`" is `Response(a, b)`, and only a no-timing cue ("also", "at
  some point", "before or after") makes it `RespondedExistence`. After "if / whenever `x`, (also)
  `y`", a sentence opened by an order word makes its step `z` required: `Existence(z)`,
  `Precedence(y, z)` and `Response(x, z)`, the last left out when `z`'s own sentence already puts
  `x` first. Every wording of a card states the same task, and an `also_ok` answer is the same task as `expect` or
  stronger only on behaviour the task never needs, never weaker (MONA-checked). Since 2026-11-22 (user) an
  `also_ok` answer may also be stronger where the wording itself reads that way, as long as its machine still
  trains the task in the card's world: the model gets the environment description, so world knowledge in its
  choice is fine. The readings are listed in `docs/LTLF_TASK_LANGUAGE.md` ("Wordings that read two ways").
- **Card scoring.** `rm-facts` scores FARM's stored clauses against the card: `exact` (the `expect`
  clauses, `forced` ones optional), `also_ok` (one listed alternative), `equivalent` or `mismatch`.
  Since 2026-11-21 (user) a clause list that states the same task as one of those answers counts as
  right like `exact` and `also_ok`, under its own status `equivalent`: over the same propositions,
  MONA finds no finite trace that satisfies one side and not the other. Hard clauses are compared
  with hard and soft with soft, so a soft rule written as hard stays a `mismatch`. The hard clauses
  are compared as one conjunction; the soft ones are paired one to one, repeats counted, each
  equivalent to its own clause on the other side, because the compiler prices each soft clause on
  its own: an extra implied soft rule or a repeated one changes the soft-break pay and stays a
  `mismatch`. Examples of `equivalent` are hard `Existence` clauses the goal and the chain already
  force (`base-doorkey`) and `NotCoExistence` with its arguments swapped. A missing, wrongly
  ordered or unimplied extra rule stays a `mismatch`. With the default settings (end judgment off)
  the `base-doorkey` card machine and the stored one with the implied `Existence` clauses are
  identical; only with the end judgment on do the well edges (-40 and -31 instead of -21 and -20)
  and the end charge (up to -30 instead of -10) differ.
- **Labeling repair.** Before any repair, `repair-labeling` gives each bundle one class from replays of
  its card's traces: `missing`, `load`, `crash`, `wrong` or `ok`. The traces are the card's plans
  and, for the four MiniGrid envs, seeded random walks on layouts the plans never use (user, 2026-11-16: "replay
  random walks against the reference labels before a labeling counts as ok or fixed"); a labeling is `ok`
  only when plans and walks both agree with the reference labels. ServiceRoom is out of scope of the
  replay: it has no reference labeler and hands its events to the labeling, so it keeps the plan check.
  That class is the measured failure rate and is never overwritten. A failed labeling is then repaired by the bundle's own generator
  (`deepseek-v4.1-flash` or `glm-5.3-flash` only) in up to 10 rounds, each shown the failure
  evidence and graded on a fresh block of walks, never on the layouts that showed its failure. The
  Reward Machine is never touched. A bundle still failing after the loop is `unfixed`
  and goes to an outside agent step; if the agent changes the labeling and it then checks `ok`, the
  bundle is `fixed-by-agent` and still counts as failed. A repaired bundle whose generation stopped
  at labeling, after its Reward Machine was accepted, then gets the stages it never reached: state
  descriptions from its generator and embeddings from `embed-larm`. Its status becomes `complete`,
  with the generation outcome kept in `generation_status` and `generation_reason` and who repaired it
  in `labeling_repaired_by` (`small-model` or `agent`), so it is trained. A bundle whose machine was
  never accepted stays `pipeline-failed`.
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
- **Environment descriptions.** A description is written as by someone who knows little about reward
  machines: plain world facts, no rule names, machine examples or hints toward an expected machine.
  FARM's generator prompt may gain general, environment-agnostic rules and examples before the
  method freeze; each change and its date are recorded here (2026-11-16: one trigger followed by
  ordered steps becomes a chain of Responses; 2026-11-20: a stated order keeps its `Precedence`,
  see Stated orders; 2026-11-21: the state tagger reads each state's role beside it and answers
  one text keyed by each state id, not a list in node order; 2026-11-21: the order rules, see
  Stated orders) (user, 2026-11-16).
- **One-hot machine state.** `rm_state_encoding: one_hot` gives the learner the machine state as one
  slot per state instead of the text embedding. It is a diagnostic learner input, not an arm: its
  runs are labeled one-hot and never pooled with embedding runs (user, 2026-11-16).
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
  keep the wording and clauses of their originals, and the originals stay as they are. Trained:
  `tpl-chain-response-1-goal-carry`, `tpl-chain-response-1-nogoal-carry` and `cx-box-carry`. Their
  originals `tpl-chain-response-1-goal` and `-1-nogoal` stopped training on 2026-11-19 (a fall in the
  plain service room does not turn the agent, so the next-move rule is unfair there); `cx-box` still
  trains. Until 2026-11-19 (superseded): the carry cards keep the `train` flags of their originals.
  Since 2026-11-21 (user) the env setting `fall_turn` (with `carry` only) changes where the box
  lands and how the agent turns: `face` (default, every card above) turns the agent to face it;
  `none` draws the landing side from the seed and keeps the agent's direction; `side` makes the same
  draw, turns the agent to face a box at its right or left, and to its right or left for a box
  behind it. Since 2026-11-22 (user) `half` makes the same draw and a fair coin turns the agent
  either to face the box or to have it on its right, one turn short, so about half the falls allow
  a next-move pickup wherever the agent stands (a rule tied to the landing side gave 75% to 94%:
  walls send blocked sides to the front). Three copies of `tpl-chain-response-1-goal-carry` with
  only that setting changed, `-noturn` (`none`), `-backturn` (`side`) and `-half` (`half`), test
  training when the world can force a missed next-move pickup. They have no paraphrases and no
  bundle of their own: `bundle_of` makes `run-suite` train them on that card's machine (FARM:
  3 seeds, 1.5M steps, `box-carry/runs-fall-turn.yaml`), and `generate-suite` skips them. A
  box-rule break after such a fall is the world's, not the machine's.
- **Forced cards.** Seed-1 judging with the empty-pass check showed two trained cards whose rule never
  triggered, so doing nothing passed: `tpl-response-1-nogoal` (`Response(blocker_moved, has_door_key)`,
  no-RM judged 1.00, non-empty 0.00) and `tpl-responded-existence-1-nogoal`
  (`RespondedExistence(has_door_key, door_open)`, no-RM judged 1.00, non-empty 0.00). Both also exist as
  forced versions (`<id>-forced`, suite `forced-start`; the name is not the card field `forced`)
  whose environment starts the episode with the trigger already true: `MiniGrid-BlockedUnlockPickup-Cleared-v0` (the ball starts away from the door, so
  `blocker_moved` is true at the first step) and `MiniGrid-UnlockPickup-KeyHeld-v0` (the agent starts
  holding the matching key, and `drop` does nothing on the first step). The environment enforces the
  trigger, not the machine; the forced cards keep the wording, clause and paraphrases of their
  originals, and the originals stay as they are. Only cards whose rule seed 1 showed untested get a
  forced version. The forced cards give the trigger at reset, so they test keeping an obligation, not
  reacting to an event. Of the forced cards, only `tpl-response-1-nogoal-forced` trains (3 arms, seeds 1
  to 3), labeled "trigger given"; the runs that had not started were dropped (user, 2026-11-14). Since
  2026-11-20 (`ab27c07`) neither original trains (an idle agent passes both), and
  `tpl-responded-existence-1-nogoal-forced` has `train: false`: `tpl-responded-existence-2-nogoal` (siren
  room, where the trigger comes during the episode) trains in its place. Until 2026-11-20 (superseded):
  the forced cards keep the `train` flags of their originals, and only `tpl-response-1-nogoal-forced`
  seed 1 trains. Reactive cards, where the trigger happens during the episode, are proposed as the real
  test of conditional rules.
- **Shop.** The reactive test the forced cards could not give: `MiniGrid-Shop-v0` and
  `MiniGrid-Shop-Pot-v0` (suite `shop`, six cards by level of difficulty, `envs/shop/`, `envs/shop-pot/`).
  A rule "whenever X happens, do Y" passes when X never happens; in the shop X belongs to the world (a
  siren that rings, clients that arrive, food that slips out of the hands, a pot that boils over), at
  times drawn from the reset seed and recorded in `info`, so doing nothing breaks every card (user,
  2026-11-14: the rules are "for environments on which things happen and the agent has to react").
  Always busy: the siren, the clients and the food slips run in every episode of every card, and the
  cards differ only in their rules, so a policy trained on one card sees the world of every other (the
  transfer experiment). The siren is heard everywhere: while it rings every plain wall and counter
  cell turns red, the same for every arm, card and level, so the 7x7 view shows it from 232 of 232
  poses (66 with the switch alone). The stove cooks only to an order taken (no preparing ahead), and
  one slip is pending, owned by the food in hand. No goal: the episode ends only at the time limit,
  600 steps. Two optional settings, both off by default so the default shop stays as it is: `small`
  (a 7 x 7 room with the counter, pantry and stove close together; `N_x` 11, 27, 15 and fines at 21
  and 18 steps) and `easy_start_prob` (a share of episodes starts at the counter with a client
  arriving on step 1). Runs that use either are labeled so and are never pooled with default-shop
  runs, since the late-fine thresholds and the reward scale differ. Quiet end: event x
  does not start in the last 3 x N_x steps, N_x being the fewest actions that handle x from the worst
  start pose, found by search (ring 15, client 37, pot 20, slip 1; the client's search lets the food be
  fetched before the order, and the stove cooks only after it). Shop reward (the environment
  reward): +1 per served order, -0.5 for every further 30 steps a waiting client keeps hearing one
  ring, -0.5 for every further 24 steps of one boil, nothing for a food slip (the penalty repeats and
  the stove cooks only to an order, so that no plan that breaks `shop-full` or `shop-boil` out-earns
  the solving worker: 7.2 on Shop and 5.8 on Pot over 300 seeds, the nearest rival, leaving fallen
  food, scores 7.0 and 5.7; a worker that holds raw food at the stove keeps every rule, is no wrong
  plan, and earns more). Runs, user's "we try with and
  without it": FARM with the RM reward only (suite `shop`) and with the RM reward plus the shop
  reward (`reward_source: both`, suite `shop-reward`), and no-RM on the shop reward. Since
  2026-11-22 (user) ARM-FM trains the shop cards too, on bundles regenerated on the code freeze and
  gated like its others; a machine that fails counts as not learned. From 2026-11-15 to 2026-11-22
  the shop ran FARM and the no-RM baseline only: 12 of ARM-FM's 22 shop machines then had a final
  start state (1-step episodes), and when final states do not end the episode it farms the loops of
  its own machine (probe, stopped at 2.4M steps). Final and rejecting states keep ending the episode.

## Protected invariants

- RM arms never train on the environment reward, except the scoped `shop-reward` runs below, and the no-RM arm never uses an RM.
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
- The shop world is the same for every card of its level: the siren, the clients, the pot and the
  food slips run whatever the card says, the same reset seed gives the same schedule, and no event
  starts in its quiet end. Doing nothing never passes a shop card.
- Runs that add the shop reward to the RM reward (`reward_source: both`) exist only in the suite
  `shop-reward` and stay labeled "RM + shop reward"; they are never pooled with RM-only runs. This is
  the one place an RM arm trains with the environment reward, by the user's choice of 2026-11-14; the
  first invariant holds for every other suite.
- Judged success keeps its definition (every hard clause holds); the empty-pass check is reported
  beside it, never folded into it. The results table's verdict column is the exception the user
  chose on 2026-11-15 20:27: judged success counted only in episodes where a hard rule's trigger fired
  (`aggregate_suite.fired_success`), with env success beside it for every arm. A card none of whose
  hard rules can fire (Absence only, no trigger in any episode) gets no verdict: its cell reads
  "n/a", the judged column beside it is its score, and the not-learning list skips it (parent
  ruling of 2026-11-16, flagged to the user, who picked nothing for Absence). `judge.json` itself is
  unchanged.
- A long PPO run keeps two models besides the final `agent.pt`: `last.pt` and `best.pt`
  (`arm_fm/ppo.py:_keep_models`), overwritten at each periodic evaluation (`best` when greedy
  success ties or beats the best so far). A timed-out run has no `agent.pt`; its table row says
  `timed-out` with a flag and its judge columns come from `test-rl --model last|best`
  (`model-last/`, `model-best/`). The final save and the default `test-rl` model are unchanged.
  `last.pt` is written before `best.pt`, so a kill between the two saves at a new-best evaluation
  can leave `best.pt` one evaluation behind `last.pt`.
- An episode the machine ended in a final state at once (the rule above) never counts as judged
  success, and the judge's raw value stays recorded beside the corrected one.
- A shared no-RM run is only shared between cards whose training configuration is identical,
  checked against the owner's saved configuration, never against the request that found it.
- One no-RM training per configuration and seed across suites and existing runs; two drivers never
  train the same key.
- A pipeline failure counts as not learned (until 2026-11-22: "no data"): no arm gets a human fix
  or retries the others do not get; both get the same attempt limit (up to 10). A failed machine
  trained as a side test never enters the counts.
- Both pipelines receive the same card wording, environment file, generator and critic.
- A results table that does not state how a time-out is paid for both methods, or with pooled
  cross-critic numbers, is wrong. Until 2026-11-20 (superseded): "A results table without the
  time-limit asymmetry line ... is wrong."
- With every reward switch at its default, the compiler builds one reference machine; a switch set
  away from its default changes it and is recorded in the bundle. Since 2026-11-19 (user) the
  default pay is a soft break cost of 1 with the hard ceiling on: a hard break costs `-(max(10, N*S*(1-g^T)/(1-g)) + 1)`, with `S`
  the soft break cost, `N` the soft breaks one step can charge (1), `g` = `Configuration.gamma` and
  `T` the level's step limit, so -96.0959 at T300 for one soft clause; a machine with no soft rule
  keeps -10 (`--hard-ceiling/--no-hard-ceiling`). The level comes from `--gym-id` and `--env-kwargs`
  or `--step-limit`; `generate-suite` passes each card's own, and generation refuses before the LLM
  call without one. Every bundle records its pay-order verdict in
  `effective_settings["pay_order"]`: `ok`, or `not checked: no step limit` or
  `check failed: <error>` with a warning.
- Labeling repair never edits a Reward Machine and never replaces the class recorded before repair.
  A repaired or agent-fixed bundle is still a failure in the failure rate.
- A MiniGrid labeling is `ok`, `fixed` or `fixed-by-agent` only when the plan check and the random-walk
  replay both agree, and a repair is graded on walks whose layouts did not produce its failure evidence.
  A record made before the replay existed has no `replay` entry and is replayed once.
- Finishing a repaired bundle leaves the generation numbers as they were: a count of generation
  successes reads `generation_status` (else `status`), and the manifest's attempt metadata, `calls`
  and `wall_time_s` are not changed. `evaluate-larm` keeps such a bundle among the generation
  failures, never as a judged first-attempt or refined win; only training reads the current `status`.
- A labeling is never asked to cover a proposition the machine does not use, and no pipeline throws away
  an accepted machine because a later stage failed. Regenerating a labeling never changes the machine.

## Rationale and tradeoffs

Judging on reference labels keeps each pipeline's labeling mistakes inside its own results instead
of inside the yardstick. Evaluating the eight templates directly is smaller than parsing LTLf and
keeps the judge apart from the stack FARM itself uses; the cost is a second definition of the
templates, cross-checked against nl2ltl's formulas. Fresh ARM-FM machines from the same small
models compare generation methods, not models; the authors' bundles would mix both. Counting a
wrong machine as not learned, over every card both pipelines were asked to train, measures what
each pipeline delivers on its own; comparing only the cards both trained hides the cards one
pipeline could not start (user, 2026-11-22). Skipping finished runs
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
- `experiments/benchmark/scripts/check_shop.py`: the shop's schedule, quiet end, `N_x`, plans, labels
  and reward on seeds 1 to 300; the `reward_source` key (`rm` or `both`; `env` is refused) of
  `run_suite.run_config` gives `shop-reward`.
- `generate-suite` and `run-suite`: statuses, skip and retry rules, arm settings, call caps.
- `check-plans` with `app/src/benchmark/plan_check.py`: the card's plans through each bundle's machine,
  the record `<bundle>.plan_check.json` beside the folder, and the `plan-check-failed` reason that
  `generate-suite` gives a failing bundle.
- `ablate-rm`: which term each switch owns, and no-op detection.
- `repair-labeling` with `app/src/benchmark/labeling_repair.py`: the classes, the 10-round limit, the
  small-model gate, and the record beside each bundle (it keeps the machine's hash and the first class);
  `app/src/benchmark/walks.py` makes the random walks and their fresh blocks, and the check's
  `coverage` counts the steps the reference sets each proposition true.
- `regenerate-labeling` and `generation-table`: the labeling-only rerun and the per-arm acceptance table.
- `aggregate-suite`: the time-out line on every table (`time_out_line`, the asymmetry line until
  2026-11-20) and per-direction cross-critic summaries.
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
  The seed was superseded on 2026-11-20: it trains on seeds 1 to 3 (see below).
- 2026-11-14: Cannot-start exception confirmed (user): the judge's rule that reads the run's own machine,
  its episode end and its labeling at reset is needed.
- 2026-11-14: Shop added (user, after the box and forced cards still let idle agents pass: a level where
  the world acts, always busy, no goal, quiet end, the shop reward with and without; testing program
  slice `shop`). It adds `reward_source: both` runs in the suite `shop-reward`, the one exception to
  the first invariant, scoped as written there.
- 2026-11-14: Labeling vocabulary and accepted-steps rules added (user: "the labeling function generations only
  worry about those used by the reward machine"; "we do always keep all the steps that have been
  accepted"); testing program slice `lf-code`.
- 2026-11-14: Vocabulary widened to what the used propositions' definitions read (correction 1 of `lf-code`:
  an RM-only labeling of `key_lost` crashed on the previous `has_door_key`).
- 2026-11-15: Shop options added, `small` and `easy_start_prob`, off by default and never pooled with
  default-shop runs (user decision of 00:35 on the serving change and the smaller shop).
- 2026-11-16: Results columns (user, audit decisions D3 and D5; testing program slice `results-cols`):
  the verdict column counts judged success only where a hard rule fired, env success beside it for
  every arm; long PPO runs keep `last.pt` and `best.pt`, and timed-out runs are listed with a flag and
  judged from one of them. D9 (each card's spread across wordings) is a results column only.
- 2026-11-16: Labeling check gains a random-walk replay for MiniGrid cards (user: "Yes, for MiniGrid cards:
  replay random walks against the reference labels before a labeling counts as ok or fixed"; testing program
  slice `labeling-replay`). The plan check saw only the states the card's plans visit, and a repair was graded
  on the traces that showed its failure.
- 2026-11-20: Card fixes and seeds (`ab27c07`). Every training test runs seeds 1 to 3, forced-start
  cards included. A card an idle agent passes, or whose goal forces its rule, stops training; the carry
  and forced cards no longer share their originals' `train` flags. Stated orders are required, and card
  answers that drop one left `also_ok` (user, 12:28: "like the task says to get order, do keep it. try to
  get the LLM to say the right order and all"); FARM's prompts ask for every stated order (`42003cf`).
- 2026-11-20: Record brought up to date with the end judgment off by default since 2026-11-18
  (`deff802`): the time-limit asymmetry and the ablation no-op changed, and the KeyGift probe (hard rule
  held on 3 of 3 seeds with the promise cost on and off) is recorded.
- 2026-11-20: Default reasoning level `max` for the generator and the critic, which always share one
  level (user).
- 2026-11-20: The results-table invariant now asks for the sentence on how a time-out is paid for
  both methods, not the time-limit asymmetry line, which the end judgment off by default made false
  (user: "Yes, okay, change the wording"). `aggregate-suite` prints that sentence from each run's
  machine and the suite's time-limit penalty; the results column `time_limit_asymmetry` and the
  JSON key `asymmetry` became `time_out`.
- 2026-11-20: Soft-rule quality added (user: "it solves the task, but how well? Is it really following
  the human preferences?"; "how many of the rules have been broken along the way"): separate soft
  breaks per episode and the share of episodes with one, for every arm. What counts as one break (it
  lasts while its labels stay as on the break step) is the implementation's reading. Recomputed from
  the saved test traces of the judged runs, with no training.
- 2026-11-20: What states an order (user): only order words ("then", "after", "before") give an
  order, and "and" and commas do not, except a compound whose second verb needs the first ("find
  and acquire the key"). A plain list of facts is one `Existence` per fact, and the ordered chain is
  also accepted (`also_ok`). `base-unlock-pickup` (with its pilot and smoke copies) and
  `base-key-corridor` follow it, `tpl-responded-existence-2-goal` requires its "Then" orders (read
  on 2026-11-21 as key before box and box after any ball move, below), and no card uses `forced`
  any more; the scorer keeps the field.
- 2026-11-21: Same-task machines count as right (user): the scorer's new `equivalent` status, by
  MONA equivalence of the hard clauses and, one to one, of the soft ones, over the same propositions.
  Of the 169 FARM bundles on main, 9 moved from `mismatch` to `equivalent` (implied `Existence`:
  `base-doorkey`, `base-blocked-unlock-pickup`, `tpl-precedence-1-goal~p1` to `~p3`; swapped
  `NotCoExistence`: `tpl-not-co-existence-1-nogoal` and its 3 wordings); no `exact` or `also_ok`
  changed.
- 2026-11-21: Forcing machines and the Q4 reading (user). The forcing cards are generated by the
  model at the freeze, into `forcing/bundles/farm/`, like every suite; the hand-built right-answer
  machines move to `forcing/reference/` (outside `bundles/`, so no arm-scanning tool sees them),
  rebuilt with no model call under the default switches, and stay as the reference the FARM
  machines are compared with and the reward ablation of `lanes-rules` reads. In
  `tpl-responded-existence-2-goal` the box is required and the key comes before it, the ball is
  optional, and if the ball moves the key must be taken too, with the key and the box after the
  ball move; no Precedence from the ball. The card's clauses are Existence(target_picked_up),
  Precedence(has_door_key, target_picked_up), RespondedExistence(blocker_moved, has_door_key) and
  Response(blocker_moved, target_picked_up), all hard. Known limit: they also accept key, then
  ball, then box with no key after the ball, which the level cannot produce; no 8-template answer
  rejects that trace and keeps key then box with no ball. Its FARM bundle lacks the Response and
  stays `mismatch`.
- 2026-11-21: The judge counts every soft break the machine charges (user decision D8). The old
  reading, one break while the labels stay as on the break step, counted an open door under a soft
  `Absence(door_open)` once, while the machine charges it every step. `_break_count` now restarts
  the rule on the step after each break, the way the re-armed machine reads it. Checked with no
  model call: for each of the eight templates a one-clause soft machine (MONA, today's reward
  layer) and the judge agree on about 300 random traces (`docs/paper/soft-break-quality/check/
  judge_vs_machine.py`); the old count disagreed on 150 Absence, 24 Precedence, 18 ChainResponse and 42
  NotCoExistence traces. Stored results keep the old count; only the soft-break-quality paper
  entry was recounted from its traces (counts up to 10% higher, ranking unchanged).
- 2026-11-21: Order rule (user). It replaces the 2026-11-20 reading above: commanded steps in one
  sentence, joined by commas or "and", now keep their written order; a full stop or a semicolon
  starts an unordered point; a condition reads the same on either side; the "Then" reading of
  `tpl-responded-existence-2-goal` holds for every "if / whenever ..., (also) ... Then ..." card; an
  `also_ok` answer is never weaker than `expect`. Cards: `base-unlock-pickup` (pilot and smoke
  copies) and `base-key-corridor` require their one-sentence orders; `tpl-existence-two-3-goal`
  requires door before goal; `tpl-response-2/3-goal` and `tpl-responded-existence-1/3-goal` gain
  the `Precedence` and `Response` of their "Then" step; `tpl-absence-1/2/3-goal` lose the weaker
  `NotCoExistence` answer, and the tuning copies of `base-doorkey` and `base-unlock-pickup` their
  Response chains, which do not keep the stated orders; `tpl-existence-2/3-goal`, `cx-siren`, `cx-box`, `cx-box-carry`,
  `smoke-doorkey-response` and three other wordings were reworded so every wording states the card's
  task; the third wording of `tpl-responded-existence-1-goal` was dropped;
  `tpl-responded-existence-2-goal` trains. FARM's generator and critic prompts gained the order
  rules.
- 2026-11-21: Any-lane Lanes cards and the box-fall setting (user). `tpl-absence-soft-1-nogoal` and
  `tpl-precedence-soft-1-nogoal` now speak of zombies through any lane, not the side lanes; the
  world keeps `top_breach` and `side_breach` and gains no any-lane proposition, so each answer has
  one soft rule per proposition (`Absence` of both, `Precedence` of `zombie_killed` over both), and
  a top breach now breaks the rule too. Their trace bank was rebuilt. `MiniGrid-ServiceRoom-v0`
  gained `fall_turn` (default `face`, the world every stored trace and card already used), and the
  box-carry suite two copies of `tpl-chain-response-1-goal-carry` that train on its FARM machine
  under `none` and `side` (see Box-carry cards).
- 2026-11-22: Readings the user accepted after the final-run generation (8 FARM bundles differed from their
  card at maximum thinking). New `also_ok` answers: `tpl-not-co-existence-soft-1-nogoal` (two soft `Absence`s:
  "both" read as "neither"), `tpl-precedence-soft-1-goal` and `tpl-precedence-soft-3-goal` (an extra soft
  `Existence` of the first step beside the soft `Precedence`), `tpl-precedence-1-nogoal` (a hard
  `Existence(at_exit)` beside the order) and `tpl-not-co-existence-soft-1-goal` (a soft `Absence(key_lost)`, as
  on its hard twins; `key_lost` fires only with the door closed), and a second answer for `tpl-not-co-existence-1-goal`
  (a hard `Existence(door_open)` beside the `Absence`, for wording ~p2). Rule: an answer may be stronger where the
  wording reads that way, as long as its machine still trains the task in the card's world. `shop-boil~p2` stays
  held: its extra `Response(stove_fixed, holding_food)` fails the plan check, and the shop world has no "put the food
  down" fact to state the pick-up exactly.
- 2026-11-22: Two check rules changed, no machine changed (user rulings D1 and D3). D1: the plan
  check and the trace bank's R43 pass a soft break that ends like the solve of its layout and pays
  less (user: "you have the right at 12, since you got 7 -> 7-12 = -5 and that is the charge the
  agent got"). D3: R43 judges the solve of a machine with no final state and no end judgment by pay,
  as the plan check does ("Judge them by pay, as the plan check does"). The FARM soft `Existence`,
  `ExistenceTwo` and `Precedence` bundles that failed only those rules now pass.
- 2026-11-22: A labeling may compute helper facts that only feed a machine fact (user ruling D2: "yeah we allow
  it"). `key_lost` needs `has_door_key` (and `door_open`) from the step before; the machine reads only `key_lost`.
  The gate's review still holds a labeling fact that no machine fact and no other fact reads. The 19 `key_lost`
  bundles the old rule held (cx-goal-one-rule, tpl-absence(-soft)-1-goal, tpl-not-co-existence(-soft)-1-goal and
  their wordings) count as right.
- 2026-11-22: One training set for every arm (user): FARM, ARM-FM and no-RM on the same 60 cards, the 60th
  `tpl-precedence-soft-2-goal`. A failed machine now counts as not learned (was "no data"), over every card both
  pipelines were asked to train. Failed ARM-FM machines that let the agent act train only as a labeled side test.
  ARM-FM returns to the shop on bundles regenerated on the freeze. Results are reported by test. An off state text
  with a right machine does not count against FARM's no-help count (the stage is inherited from ARM-FM). The two
  soft-only no-goal cards stay in the set: the idle agent breaks their soft rule (2.0 and 1.0 times per episode) and
  no-RM beats it, so they are not idle-passable.
- 2026-11-22: Later rulings (user). Soft-only cards compare every break with the idle plan, for every arm (the
  once-per-rule count saturates in Lanes). ARM-FM's start-final machines are reported as a format limit. FARM's
  state tagger reads the critic's information by default (off state texts 11 of 18 runs to 5 of 18 on the six
  bundles with an off text). New tests of a right machine on a hard task: the KeyCorridor world size, more
  training steps, a soft box-carry card on the fall worlds and a replay after a missed pickup.
- 2026-11-22: A fourth fall world at about 50% (user). `fall_turn` gained `half` (a coin decides whether the
  agent faces the fallen box), and box-carry the copy `tpl-chain-response-1-goal-carry-half`, trained like
  `-noturn` (see Box-carry cards). The first rule tried (only a box at the right turns the agent) gave
  94% of next-move pickups for the solving policy and 75% for an exit walker, since walls send blocked sides to
  the front; the coin gives 52% and 53%. `face`, `none` and `side` play the same episodes as before.
- 2026-11-22: Suite `armfm-paper` (user): the ARM-FM paper's MiniGrid tasks the benchmark lacked, for all three
  arms, `train: false` (outside the counted 60). DoorKey 5x5 and 16x16 with new maps get machines of their own;
  their fixed-map copies, and DoorKey 8x8 on a fixed map, train on the new-map card's machines through
  `bundle_of` (8x8 borrows `base/base-doorkey`: `bundle_of: <suite>/<card-id>` now reads a sibling suite's
  bundles). A fixed map is the existing `layout: fixed` with `layout_seed` 1. BabyAI UnlockToUnlock gets the
  dev catalogue's env pages and a reference labeler; its layout stays procedural. 1.5M steps for 5x5 and 8x8,
  5M for 16x16 and UnlockToUnlock (user D3).
- 2026-11-22: XLand-MiniGrid is back as a family (user, ARM-FM baseline B2), so the three arms run the ARM-FM
  paper's XLand tasks (Figures 9 and 10): `xland` family, `XLand-R4-13x13-v0` (one ruleset per env, 13x13, 507
  steps), `xminigrid==0.9.3` pinned, 8 cards in `experiments/benchmark/xland/` (`train: false`; their task texts
  are reconstructed from the rulesets). Runs are 5M steps; mixes of cards whose rulesets differ get a no-RM arm.
  Two 5-task-mix ablations add the smallest switches: `rm_state_encoding: none` (the machine pays, the policy
  never sees its state) and `reward_source: env_rm_state` (env reward, the machine only gives its state).
- 2026-11-23: Closer zombie lanes (user). `LanesEnv(lane_spacing=k)` is the row distance between lanes, 1 to 4,
  default 4 (the counted world, byte-identical); width 11, grid height `2k + 3`. Spacing 2 leaves one free row
  between lanes (11x7 grid), spacing 1 puts them side by side (11x5 grid), so no plant sprouts and the plant clause
  is vacuous there. Suite `lanes-spacing` copies four counted Lanes cards at spacing 2 and 1 (`bundle_of`,
  `train: false`, outside the counted 60). The Lanes environment pages stay unchanged, because bundles store them.
- 2026-11-23: Shop world curriculum and back falls (user, after FARM never served with slips: "let it start
  learning first without slipping ... same run"). A card's env block may list `env_stages`: each stage sets shop
  attributes on every training env and the run moves on when its last 100 training episodes serve 10 orders on
  average (and, before back falls, catch 90% of falls on the next move). Machine, policy, optimizer and step count
  carry on; evaluation and the judge use the card's own world, the last stage; switches go to `stages.csv`.
  `back_fall_chance` p (default 0, byte-identical): a slip lands the food behind the agent and turns it 90 degrees,
  so the next move cannot pick it up. Cards `shop-ladder-{deliver,order-deliver}-curriculum[-back]` (`bundle_of`,
  `train: false`, FARM only: `env_stages` is not a no-RM share setting), outside the counted 60.
- 2026-11-23: Shop size curriculum (user: "3x3, then 5x5, then 7x7 (stop there, 7x7 the biggest)"). The shop
  reads `area` at every reset, so an `env_stages` stage may set it; the observation stays 7x7x3 at every area.
  Cards `shop-ladder-{deliver,order-deliver}-grow` grow 3x3 -> 5x5 -> 7x7 inside one run (10 served to move on)
  on the base card's FARM machine; evaluation and the judge play the 7x7 world. Defaults byte-identical. Outside
  the counted 60.
