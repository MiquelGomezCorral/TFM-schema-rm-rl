# Reward Machine execution

## Intent

Give both generation modes the same step semantics so comparisons change RM generation
without changing how labels, transitions, and rewards are interpreted.

## Current decisions

- Supply the complete valuation of declared propositions once per environment step.
  Document whether each proposition is a persistent condition or a one-step event.
- Negation means false now. A moment-of-loss event needs its own explicit definition;
  it is not automatically equivalent to an absent possession condition.
- Evaluate outgoing guards only from the old RM state, select one transition, and update
  the RM exactly once per environment step. Do not reevaluate from the destination state.
- A guard depends only on propositions it mentions. Ignore irrelevant propositions and
  use an implicit zero-reward self-loop when no ordinary guard or explicit fallback applies.
- Our parser rejects an ARM-FM reward row on a transition the machine never declared
  (`app/src/compiler/rm_format.py`, `_with_rewards`). The parser error goes back to the model as the
  next ARM-FM round, within its attempt limit. The authors' code accepts such a row and never pays it;
  we keep rejecting.
- Baseline RM text retains the paper's per-state `else` self-loop convention. Compiler
  generation omits `else` rows and declares a zero default reward. Both modes apply
  an explicit `else` when present, otherwise the implicit zero-reward self-loop.
- Compiler imports accept explicit self-loops and `else` rows, including an `else`
  destination different from the source. Preserve their destinations and rewards;
  the fallback applies only when no ordinary guard matches.
- Expect disjoint ordinary guards. If several match, select the first stored transition
  and emit a warning. An `else` row applies only when no ordinary guard matches.
- Reset the RM and episode-local labeling memory on environment reset. The previous valuation at the
  first step of every episode holds every proposition as false, in both pipelines.
- Only declared final states accept the task. A machine with no final may declare
  `ACCEPTING_STATES` instead: an episode the environment ends in one of them is accepted
  (`rm_accept`; a success when the run uses `success: rm`), and being there never ends the
  episode. A compiled machine with a final carries the judgment lines (only with the end judgment
  on, see below) but lists no accepting state (every other state has a hard clause open), so its
  success still needs the final. A declared rejecting state (`REJECTING_STATES`) marks an irreversible violation;
  RMs without that line (such as ARM-FM paper RMs) have none.
  States remember earlier events; a false proposition now does not erase recorded progress.
  The one exception is a broken soft rule when recurrent soft rules are on: its state takes the
  start state's edges, so the rule watches for the next break. That break was already paid, and
  recorded goal progress is kept; only the progress reward is re-scored. A folded soft `Absence`
  (`fold_soft_absence`, on by default) never leaves its state; its break is only charged.
- Entering a final or rejecting state ends the episode, as do the environment's own termination
  and its time limit, for every RM-wrapped run. When the environment ends the episode and the RM
  text has a `PENDING_PROMISES` section, that step adds the end judgment: `HARD_FAILED_REWARD`
  times the hard promises still open in the RM state after the step, plus `SOFT_FAILED_REWARD`
  times the soft ones (0 in an accepting state). An RM without that section keeps the flat -5 on
  a truncated step that did not terminate. An episode the RM ended itself gets neither. A compiled
  machine carries `ACCEPTING_STATES` and `PENDING_PROMISES` only when it is built with
  `reward_end_judgment` on, off by default since 2026-11-18 (`deff802`): a machine built with the
  defaults has neither, so one with no final never reports `rm_accept`.
- The learner reward follows the run's `reward_source`: `rm` (default) the RM reward only,
  `both` environment + RM reward, `env` no RM at all. `info["env_reward"]` always holds the raw
  environment reward and `info["rm_reward"]` the RM reward, including the time-limit penalty or
  the end judgment. The trainers are unchanged: a judged time limit still bootstraps as before,
  and the end judgment is part of the step reward they receive.
- App graphs, exported SVGs, the standalone graph script, and the interactive HTML export share
  the same fallback display. Show explicit fallback edges with an `else` label. For every declared state
  without an outgoing `else`, draw a zero-reward self-loop labeled `else`, including
  accepting and rejecting states. An explicit `else` to another state suppresses that
  default loop; ordinary guarded self-loops do not.
- These graph defaults are display-only. Preserve explicit guards and rewards when
  grouping edges with the same source and destination. Do not enumerate valuations
  or analyze guard exhaustiveness to decide whether to show a default loop.
- App graphs, standalone SVGs, and the HTML export use one deterministic top-down layout and
  shared sibling-label spacing, with states drawn as circles. A state's rank is its longest path
  from the initial state, so forward edges point down; final states sit in the bottom rank;
  rejecting states sit in a lane beside the main flow, so edges into them may point up. The layout
  keeps states off edges they are not part of. The app starts from those positions rather than a force
  layout. Self-loops appear on the right with horizontal labels below them; users may still pan,
  zoom, drag states, inspect transitions, and export their placement (SVG or HTML).
- Hover, click, and the transition panel have one owner shared by the app and the HTML export,
  so a change to the interaction reaches both.

- The authors' released runtime chains every triggered event inside one step. Paper-reproduction
  runs keep our one-update rule. The authors apply `else` only when no event is true and none of
  their four released RMs rewards `else`; their stages need distinct actions, so the difference
  does not change those RMs (only UnlockToUnlock u4 can see two events at once, and both
  runtimes take the first listed one).

## Protected invariants

- Simultaneous true propositions never cause multiple RM updates in one environment step.
- Do not enumerate every proposition combination or retain irrelevant conditions merely
  to make transitions explicit.
- Do not reject overlapping guards solely because they overlap, silently reorder them,
  or treat `else` as a competing ordinary guard.
- A proposition that no longer matters to task progress may become false without changing
  the RM state or reward unless that state's guards explicitly depend on it.
- Graph fallback edges must not mutate the input machine, serialized output, or
  execution semantics. An explicit `else` destination and reward must remain intact.
- The end judgment applies once, only on an episode end the RM did not cause, and only to RMs
  whose text has `PENDING_PROMISES`: a compiled machine built with `reward_end_judgment` on, with
  or without a final state (a goal is a hard promise). RMs without it, such as compiled machines
  built with the defaults, imported author bundles and fresh ARM-FM machines, pay the run's
  `time_limit_penalty` at the time limit (default -5, the reproduction value; the [thesis
  benchmark](../benchmark/thesis-benchmark.md) sets 0) and get no end judgment. Superseded on
  2026-11-18 by `deff802` (the end judgment off by default): "every compiled machine" carries it,
  with the "Test exception: an ablation variant with `reward_end_judgment` off carries none; every
  non-ablation machine still does."
- The compiler never removes states or transitions on environment facts. The critic judges every
  clause against the environment file (`## Constraints`, the truth table, what the agent can and
  cannot do) and rejects a clause that rests on an event that cannot occur there; the whole flow
  then runs again with a new clause set. An order the task states stays and is required even when
  the environment guarantees it: the critic rejects a set that leaves out its `Precedence` (prompts
  since `42003cf`). An order the task does not state is never added from environment facts. When
  the critic doubts, the clause stays. Spare states are accepted: they cost
  nothing in learning, while a wrong cut fails silently (the machine keeps its state and pays 0).

## Rationale and tradeoffs

Complete valuations support possession, loss, and penalties without forcing every RM state
to model irrelevant cases. Exactly one update follows the chosen paper semantics. Ordered
first-match execution makes overlap deterministic and visible while avoiding rejection of
otherwise usable artifacts; disjoint guards remain the intended output.

Implicit zero-reward loops keep compiler text compact while explicit `else` remains
usable for imported paper-style machines and fallbacks to other states. Drawing these
defaults makes missing rows understandable, including final and rejecting sinks,
without expanding the machine or adding a guard-coverage calculation.

## Known limits of the chain-weighted progress

Accepted and recorded (user picks of the process audit, 2026-11-15). None is protected behaviour:
each is a gap to close when a card needs it.

- **A rule closed (or opened) by either of two events hands off to nobody.** `_forced_propositions`
  intersects the forced propositions over all closing (and opening) edges
  (`app/src/compiler/reward_layer.py:359-390`), so `G(a -> F(b | c))` forces nothing, gets weight 1,
  and its middle steps pay 0. The function's docstring states it. No current card has such a rule.
  Fix (per-edge-pair detection) when a card needs it.
- **A step that only a "before" rule names can still go unpaid** (user-approved 2026-11-20).
  `Precedence` is satisfied from the start, so the per-clause measure owes 0 for it: accepting
  states owe 0 (`reward_layer.py:355`) and violated states owe 0 (`:424`). The hand-off does not
  cover it. Since 2026-11-19 a machine with a final reads its hard stages from the fewest events
  still needed to reach the final (`_events_to_final`), so a step on a path to the final pays. Left:
  a machine with no final, which keeps the per-clause measure, and a step that no path to the final
  needs; whether that step pays then depends on the generator also writing an `Existence` for it.
  6 of the 71 FARM main machines that store their clauses (the 73 FARM bundles without a `~pN`
  paraphrase suffix, minus the 2 pilot bundles, which store none) had this shape. 3 now pay the
  step (reward +1 when only that event happens): base-key-corridor (`target_room_entered`),
  tpl-precedence-1-goal (`blocker_moved`) and tpl-precedence-1-nogoal (`switch_toggled`, whose
  stored machine has a final through `Existence(at_exit)`). 3 still pay 0: tpl-precedence-2-nogoal
  (`door_open`) and tpl-precedence-3-nogoal (`blocker_moved`), with no final, and
  tpl-precedence-2-goal (`door_open`), whose final needs only `at_goal`. Checked 2026-11-20 on main
  `9bd6aeb` by running the machines the compiler builds from those stored clauses (no model call).
  Fix when a card needs it: an `Existence` per step in the generated clauses, or the machine's
  distance to the final for a machine with no final.
- **A soft break forgets a trigger on the break step.** Since 2026-11-18 (commit `deff802`) a broken
  soft clause's debt is not refunded, so the break step pays minus the break cost at any chain
  weight, and not reacting always costs (weight + 1) more than reacting. Left: a re-armed soft
  `ChainResponse` starts watching one step late, so a trigger on the break step itself is not counted
  (`_rearm_violated`, `reward_layer.py:262-288`). At an episode end not reacting then pays 3 to 4
  more. Only a soft `ChainResponse` has this shape. The 4 soft template cards
  (`ChainResponse(box_fell, holding_box)`: `tpl-chain-response-soft-1-goal`, `-2-goal`, `-3-goal` and
  `-1-nogoal`) cannot reach it: `box_fell` is an event and the break step is the step after a fall,
  where the box cannot fall again. The dev card "ChainResponse, soft"
  (`experiments/dev/benchmark/tasks.json`, `ChainResponse(has_key, door_open)`) can: `has_key` is a
  condition that stays true. The other ChainResponse cards (6 hard template cards, the box-carry and
  shop cards) and every stored bundle declare it hard, which never re-arms. Fix when a card needs it: the break step goes where the start would go on that
  step, the same mark the Absence fold uses. A soft clause of weight 2 or more with a trigger every
  step would also cost more than the hard ceiling assumes; the last scan (2026-11-16) found none
  above 1.

## Enforcement

- `app/src/arm_fm/runtime.py` owns guard evaluation, explicit fallback selection,
  zero-reward implicit loops, ordered overlap warnings, one update per step, episode termination
  on final or rejecting states, the time-limit penalty, the end judgment, and the reward source.
  `tests/test_arm_fm.py` checks the earlier runtime contracts. `app/src/arm_fm/environments.py`
  owns the success rule. The end judgment and the no-final success rule have no repository test:
  Review-only, checked live when they change.
- `app/src/compiler/rm_format.py` owns the shared text parser and serializer, including the
  optional accepting states, failed rewards, and `PENDING_PROMISES`; the compiler
  and the runtime both import it, and it never imports `src.arm_fm`.
  `tests/test_reward_machine_format.py` checks zero-reward progress, imported guards,
  explicit self-loops, and `else` fallbacks to other destinations.
- `app/src/utils/visualization.py` owns display-only fallback edges for the app and
  `app/scripts/render_rm.py`; `app/src/utils/svg.py` renders the shared elements.
  `tests/test_reward_machine_format.py` checks fallback destinations, rewards,
  visible SVG labels, and unchanged input transitions.
- `app/src/utils/layout.py` and `settle.py` own the positions (`reward_machine_positions`);
  `visualization.py` owns the elements, the stylesheet, and sibling-label offsets, and sizes
  come from `GraphStyle`. `app/src/web/components.py` selects Cytoscape's preset layout.
  `app/assets/rm_graph.js` and `rm_graph.css` own hover, click, and the transition panel for the
  app and `app/src/utils/html_graph.py` (`render_elements_html`, `render-rm --html`), which
  inlines them with the vendored Cytoscape.js 3.28.1 (`app/vendor/cytoscape/`, the version
  `dash_cytoscape` bundles). `tests/test_web.py` checks initial app placement against the
  standalone SVG, the layout rules (final lowest, well aside, forward edges down, no state on a
  foreign edge), the HTML document, and keeps pan and zoom enabled.
- The meaning of event versus persistent propositions remains Review-only against
  each environment definition; runtime evaluation cannot establish that grounding.

## History

- 2026-09-18: Confirmed complete valuations, relevant guards, implicit self-loops, ordered
  overlap handling with warnings, and exactly one RM update per environment step.
- 2026-09-21: Kept published-style `else` rows for baseline output while making
  compiler output's implicit self-loop and zero default reward explicit.
- 2026-10-12: Recorded that paper-reproduction runs keep one update per step although the
  authors' runtime chains events.
- 2026-10-12: Added declared rejecting states, episode end on RM final or rejecting states and on
  the time limit (-0.5), and `reward_source` (default `rm`), following Toro Icarte et al. (JAIR
  2022), where reaching an RM terminal state ends the episode (user decisions).
- 2026-10-14: Added the interactive HTML export with one shared interaction script, and the
  circle-state layout: longest-path ranks, final last, rejecting states in a side lane, no state
  on a foreign edge (user requests).
- 2026-10-15: Added a deterministic constraints pass that removed the states and transitions no
  constraint-respecting run reaches (coordinator-approved plan, iteration 2).
- 2026-10-17: Removed that pass. The compiler never removes states on environment facts: random
  episodes can only disprove a constraint, never prove one, and a wrong cut fails silently. The
  critic judges clauses against the environment and the flow reruns; spare states are accepted
  (user decision).
- 2026-10-23: A broken soft rule re-arms when the recurrent soft penalty is on (user and
  supervisor).
- 2026-10-26: Added the end judgment for RMs with `PENDING_PROMISES` (rule-only tasks): every
  episode end the environment causes, termination or time limit, pays for the promises still open,
  at values the RM text sets. Machines with a final and author bundles keep the flat -0.5 (user
  decisions).
- 2026-10-27: The trainers keep their time-limit bootstrap and the end judgment is added on top
  ("keep it but add ours"); a machine with no final is accepted when the environment ends it in
  an accepting state (user answers to the plan critique).
- 2026-11-11: The end judgment now covers machines with a final state too: a goal is a hard
  promise, so an episode the environment ends with the goal open is charged for it (-1) with the
  other open items, instead of the flat -0.5. Such a machine lists no accepting state; success
  still needs the final. Author bundles keep the flat -0.5. Reward progress became a per-clause
  to-do count, each clause weighted by the chain it hands off to (2026-11-15, see below)
  ([reward layer](../../COMPILER_REWARD_DESIGN.md)) (user decision).
- 2026-11-15, user-approved: progress is `Phi(u) = -0.1 * sum over clauses i of w_i *
  remaining_i(u)`, where `w_i` is 1 plus the sum of `w_j` over every clause j that closing clause
  i opens in the same step (1 when it hands off to none). Why: on a chain of rules each step closes
  one rule and opens the next, so the middle steps paid 0. It stays a potential, so no loop gains.
- 2026-11-11: An edge into the rejecting well pays its -1 plus the end charge of the state it
  leaves, the same counts `PENDING_PROMISES` holds, so breaking a rule always costs more than
  timing out in that state. This solves the disclosed corner where idling with two hard promises
  open (-2) cost more than a hard break (-1). The number is in the edge's reward, so the runtime
  does not change and the well adds no charge at the end (user decision). Since 2026-11-18 that end
  charge on the well edge is off by default with the end judgment (see below).
- 2026-11-16, user-approved (D4 picked 2026-11-15 20:27; go on 2026-11-16 00:13, "okey add the D4
  thing, like is having a constant -0.01 on each step, right? either do something or get
  penalized", and 00:16, "ok go with it"): a setting, off by default (`--promise-cost`,
  `reward_promise_cost`), charges `PROMISE_COST_REWARD` (-0.01) on every step taken while at least
  one hard promise is open, once however many are open, and nothing when none is. The step out of
  such a state into the well or a final pays it too; the end charge and the well's -1 are
  unchanged. Why: breaking a rule pays -1 plus the end charge now, idling pays the same end charge
  only at the time limit, the shop's 600-step limit and a discount of 0.99 later, so waiting costs
  almost nothing today. The cost is not charged when nothing is owed: a cost on every step
  (-0.01 x 600) would make breaking (-1 now) the cheaper way out of waiting.
  The idle self-loops of a state with a promise open become priced edges, so `rebuild-rewards`
  checks that states, finals, end judgment and every edge that moves are unchanged instead of the
  text; `rebuild-rewards --promise-cost` turns it on in a saved bundle, and a copy is
  `cp -r BUNDLE COPY` first. The setting is recorded in `effective_settings`; ablation does not
  offer it (user). Since 2026-11-20 (user decision: a hard break is charged the promise cost still
  open) the step into the well pays it once per step of the level's step limit (-0.1 x 600 = -60
  on the shop), so a hard break never pays more than keeping the promise open to the end; the end
  charge and the well's own charge are unchanged. The build refuses the promise cost without a
  step limit, the bundle records it, and `train-rl` refuses a level with another step limit.
- 2026-11-12: The flat -0.5 at the time limit becomes the run setting `time_limit_penalty`
  (default -0.5, so reproduction runs keep it); the thesis benchmark sets 0 for ARM-FM machines,
  as the ARM-FM paper pays nothing there. FARM's end judgment is unchanged (user decision).
- 2026-11-12: An ablation variant with `reward_end_judgment` off carries no end judgment, as a test
  exception; every non-ablation machine keeps it (user). Superseded on 2026-11-18: the end judgment
  is off by default, so a machine built with the defaults carries none either.
- 2026-11-12: Kept rejecting an ARM-FM reward row on an undeclared transition; the parser error is the
  next ARM-FM round's feedback (user).
- 2026-11-15, user picks of the process audit: recorded three known limits of the chain-weighted
  progress (either-or hand-offs, steps only a `Precedence` names, progress paid into a soft break),
  all accepted for now. The undiscounted progress stays; switching to discounted shaping is decided
  after the shop runs ([reward layer](../../COMPILER_REWARD_DESIGN.md)).
- 2026-11-17, user decision: pay in whole units, ten times the earlier numbers (`PROGRESS_REWARD` 1,
  finish 10, well -10; in the code since 2026-11-18, commit `deff802`); older entries keep the numbers
  of their date ([reward layer](../../COMPILER_REWARD_DESIGN.md)).
- 2026-11-19: Soft `Absence` folds into an edge charge by default (`fold_soft_absence`), so it adds no
  state; kept as a switch for the later settings study (user).
- 2026-11-19, user-approved: the default pay prices a hard break above any stream of soft breaks. A
  soft break costs 1 and the hard ceiling is on, so a hard break costs
  `-(max(10, N*S*(1-g^T)/(1-g)) + 1)`, with `S` the soft break cost, `N` the soft breaks one step can
  charge (1), `g` = `Configuration.gamma` and `T` the level's step limit (`--gym-id` with
  `--env-kwargs`, or `--step-limit`): -96.0959 at T300 for one soft clause. A machine with no soft
  rule keeps -10; `--hard-ceiling/--no-hard-ceiling` sets it. Generation refuses before the LLM call
  without a level, and every bundle records its pay-order verdict in
  `effective_settings["pay_order"]` (`ok`, or `not checked: no step limit` or
  `check failed: <error>` with a warning). Why: with the old defaults (soft break cost 5, flat -10) the
  worst stream of soft breaks cost more than one hard break, so breaking the hard rule paid better:
  the forcing card `lanes-rules` paid -475 for that stream against -10
  ([reward layer](../../COMPILER_REWARD_DESIGN.md)).
- 2026-11-19, user-approved 2026-11-20 (focus: a required chain "a, then b, then c" paid 0, 0, 0 and
  everything at the goal; rule: "do not add a new reward term, stage or switch on top", read the
  distance from the machine, the same idea as the soft `Absence` fold): in a machine with a final,
  a hard stage pays `PROGRESS_REWARD` times the fewest events still needed to reach a final from
  the source state, minus the same count from the destination (`_events_to_final`, `_progress`,
  `reward_layer.py:708` and `:725`). An edge costs the positive propositions its guard needs, at
  least 1; self-loops and edges into the well are left out of that count. Soft clauses and machines
  with no final keep the per-clause measure of 2026-11-15. No scaling: a chain of `n` events pays `n`
  on the way and 10 at the end, so doorkey written as `Precedence` pairs and as `Response` both pay
  1, 1, +11 (13 in all, 11 before for both). Why: a chain is `Existence(last)` plus `Precedence`
  pairs and only the `Existence` owed a step, so the pay read the rules while the machine already
  holds the chain. A plain hop count is wrong: `Precedence` lets two events share a step, so the
  machine keeps a start-to-final edge. Pay-order sweep (MONA, no model calls): 87 of 168 card sets
  pass before and 126 after (127 of 167 once three cards were reworded to name every step), 39
  fixed, none newly failing; stored sets 73 to 80 of 108, 9 fixed and 2 newly flagged by "started
  must pay more than not started", a known false alarm of that check. With the refund and the
  no-goal skip of the next entry: 141 of 167 cards and 91 of 108 stored sets; the 26 cards and 17
  stored sets that still fail all have a final and fail on that same line
  ([reward layer](../../COMPILER_REWARD_DESIGN.md)). Superseded 2026-11-20: that false alarm is
  fixed and every set passes (entry "started is closer to the goal" below).
- 2026-11-19, user-approved (refund: "simple, stylish... reuses part of what we had"; clamp, 2026-11-19
  23:57: "go for clamp, take back only gains, never return a charge"): an edge into the rejecting well
  also takes back the progress since the start, as measured by `potential` below; a charge already
  paid is never paid back as a reward. It adds `PROGRESS_REWARD * min(0, potential(source) - potential(start))` to the
  well price, `potential(u)` being the events still needed to reach a final (`_events_to_final`) plus
  the stages still owed (the soft clauses' with a final, every clause's without one); the finite
  charge, the end charge of the state it leaves and the promise cost (since 2026-11-20 the step
  limit's worth, see the promise cost entry) stay. So a hard break costs the
  same however far along the agent was: on doorkey with lava, breaking at once, after the key, or
  after the door all total -10. A charge paid after some progress (a Response trigger, for example)
  cancels that progress, so the take-back is net: in a chain of 2, `e0` pays +1, `alarm` pays -1, then
  `lava` takes back 0, and the break totals the same as one at once. Accepted: a step whose state
  machine only sees the state cannot track a path-dependent sum of progress. The `min(0, ...)` keeps a
  charge already paid from coming back: without it, a break after a client arrives paid +3 on
  `shop-serve~p3`, and a soft and a hard break tied on `cx-rules-only`. Limit, harsher and never
  milder: a soft break on the way withholds that clause's stages from the progress paid but not from
  the take-back, so such a break can cost more than the hard price, never less.
  This reverses the 2026-11-11 choice of no progress score into the well
  ([reward layer](../../COMPILER_REWARD_DESIGN.md)). Why: on a long chain the progress collected (11
  steps) outgrew the hard price (-10), so starting and then breaking paid more than never starting.
  Pay-order sweep: 141 of 167 cards and 91 of 108 stored sets pass, none lost (counts superseded
  2026-11-20, see below); break paths that paid
  more than the hard price went from 51 to 0. Also, the pay-order check skips "started pays more than
  not started" for a machine with no final state, where idling keeps every rule; its summary names the
  skip (user). Such tasks only make sense in a level that forces the agent to act.
- 2026-11-20 (user): the critic no longer rejects a clause for restating an order the environment
  guarantees; a task-stated order stays and is required (see [task and RM
  identity](task-and-rm-identity.md)).
- 2026-11-20: Record brought up to date with `deff802` (2026-11-18): the end judgment, its
  accepting states and the owed charge on the well edges are off by default (`reward_end_judgment`),
  so a compiled machine built with the defaults pays the run's `time_limit_penalty` like an author
  bundle. A hard and a soft copy of one rule can then compile to the same machine (`keygift-hard`
  and `keygift-soft`); only `reward_promise_cost`, off by default, separates them. Probe of
  2026-11-20: KeyGift's hard rule held on 3 of 3 seeds with the promise cost on and off. Also: the
  critic rejects a set that drops a stated order, and an unstated order is never added from
  environment facts (prompts since `42003cf`).
- 2026-11-20 (user), started is closer to the goal: in the pay-order check a "started" state must
  owe fewer propositions than the start, where a state owes the fewest propositions that must still
  come true to reach a final state (shortest path avoiding rejecting states; an edge costs the
  positive literals its guard needs, so one step can make several true; `_owed`,
  `app/src/arm_fm/pay_order.py`). A state that only remembers a trigger, such as the `a` of a soft
  `Precedence(a, goal)`, or of a `Precedence(a, b)` whose `b` the goal does not need, or an opened
  `Response`, owes as much as the start or more and is not started; a machine with no final keeps
  the no-goal skip. Why: the line "started must pay more than not started" flagged machines whose
  only started states were such memories, which by design pay no more than idling. Pay-order sweep
  (MONA, no model calls, today's cards): 106 of 130 card sets and 91 of 108 stored sets pass
  before, all 130 and 108 after; the 41 fixed sets all failed that line, none lost. Six soft
  `Existence` or `ExistenceTwo` card sets lose "started" from their summary, since the goal does
  not need that event. With promise cost on,
  125 of 130 pass before and after. Limit, kept on purpose: on the shop the promise-cost stall (a
  hard promise left open costs -19.0, a hard break -10.1) still reads "ok" in `check-pay-order`,
  whose summary only notes it ("stall, hard promise open"); only the plan pay shows the stall. The
  check does not change for it. Resolved 2026-11-20 by the well price of the promise cost entry: a
  hard break on `shop-serve` now costs -70, below the -19.0 stall (`check-pay-order`: "hard break
  -70; ok; stall, hard promise open -19.0117").
