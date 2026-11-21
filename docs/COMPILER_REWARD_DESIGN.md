# Compiler redesign: IBM nl2ltl, FL-AT, and the reward layer

Status: **implemented and merged.** This records what we checked, what we decided, and why,
from the design discussion of 2026-10-12, kept up to date as the reward layer changed (last
change 2026-11-15). The code is in `app/src/compiler/`; "Compiler before the redesign" below
describes the compiler it replaced.

Every claim is marked with how it was checked:

- **[run]**: we ran the code (FL-AT + MONA in `RM_RL_env`) and read the output.
- **[code]**: read in this repository's code, with `file:line`.
- **[paper]**: a research worker or we read the primary source; the PDF is in `docs/` where noted.
- **[decision]**: a choice the project owner made, with the reason.

## Pipeline

1. **LLM (our engine, our prompt)** reads the environment Markdown and the task and returns, in
   one answer, every clause the task needs. Each clause = one IBM DECLARE template, its
   propositions, and a hard/soft tag.
2. **IBM nl2ltl** turns each (template, propositions) into an LTLf formula with its own
   template classes and `to_ltlf()`. Its formulas are used for every pattern, unchanged. IBM's
   grounding helper is skipped: **[code]** `ground_notcoexistence` passes the second proposition
   twice (`dependencies/nl2ltl/nl2ltl/engines/grounding.py:108-111`), so building the template
   classes directly is both simpler and correct.
3. **FL-AT fork** compiles each formula to a DFA with MONA and builds the synchronous product
   of all clause DFAs. One small addition: it also returns, for each product state, the tuple
   of per-clause DFA states (`sdict`).
4. **Our cleanup layer** turns that product into the final Reward Machine: hard pruning and
   rewards, then a merge of equivalent states (`minimize_machine`, on by default since 2026-11-21).
5. **One critic** reviews the task, the clauses and the compiled RM before state descriptions.

Out of scope for this redesign: labeling functions, RM state descriptions and embeddings, and
the RM text format, except one new optional `REJECTING_STATES:` line, `FINAL_STATES:` being
allowed to be empty, and the end-judgment lines (see "The end judgment"). Other pipeline steps own
the rest.

## Why this shape

- **[decision] Our LLM only replaces IBM's engine.** The rest of nl2ltl (templates, grounding,
  formulas) is reused as IBM wrote it, so the work builds on theirs instead of rewriting it. We
  keep our own prompt because IBM's GPT prompt does not fit our domain (see facts below).
- **[decision] One LLM answer gives all the clauses.** IBM's engine maps one sentence to one
  pattern; our tasks need several clauses ("get the key, then open the door, then reach the
  goal").
- **[decision] IBM's formulas for every pattern.** Today's compiler replaced IBM's `Precedence`
  with custom soft/hard formulas. With hard/soft moved to the reward layer, there is no reason
  to keep a non-IBM formula.
- **[decision] Keep the FL-AT fork, add only `sdict`.** The fork does not change what FL-AT
  builds; it makes FL-AT a library and safer (facts below). Going back to upstream would mean
  redoing those fixes.
- **[decision] All new logic lives in one layer after FL-AT.** IBM and FL-AT stay as original as
  possible, so it stays clear what is theirs and what is ours.

## Facts we checked

### Compiler before the redesign (as of commit `3066c95`)

- **[code] It does not post-process FL-AT's Reward Machine.** It calls only
  `flat_tool.compile_dfa` per clause (`app/src/compiler/pipeline.py:102`) and rebuilds the RM
  itself: completion, minimization, per-pattern shape checks, rewards and the product in
  `app/src/compiler/reward_machine.py`. This is the part the redesign replaces.
- **[code] Its serializer leaves out 0-reward self-loops** (no matching edge means "stay"), so
  loops look "missing" next to FL-AT or ARM-FM output (`app/src/compiler/rm_format.py`).
- **[code] It supports 3 patterns** (`Existence`, `ExistenceTwo`, `Precedence`) and rejects the
  rest in three places: the LLM's output schema (`app/src/engines/structured.py:20`),
  `_validate_clause` (`app/src/engines/structured.py:216`), and the DFA step, which requires one
  accepting state that never leaves (`app/src/compiler/reward_machine.py:508`).
- **[code] Rewards then:** 0.1 once when a clause completes, +1.0 when the task completes.
- **[run] It almost always ends up hard.** In `docs/artifacts/ARM-FM-vs-COMPILER.md`, 9 of 12
  compiler RMs have an absorbing rejecting sink and none has a penalty edge.

### IBM nl2ltl

- **[code] IBM's GPT engine is not a general engine for our tasks**
  (`dependencies/nl2ltl/nl2ltl/engines/gpt/`). Its prompt is few-shot for app automation (Slack,
  Gmail...), its `ALLOWED_PATTERNS` lists only 5 patterns (existence, existenceTwo, response,
  chainResponse, respondedExistence), and it returns one `PATTERN:` + `SYMBOLS:` line per sentence.
- **[code] The reusable part:** `engines/utils.py:_get_formulas` matches the pattern name to
  IBM's template list and calls the grounding in `engines/grounding.py`; an optional filter
  follows (`filters/simple_filters.py`). An engine implements
  `Engine.translate(utterance, filtering) -> Dict[Formula, confidence]`.
- **[code] IBM's templates have no hard/soft notion.** "Never touch lava" and "if possible never
  touch lava" are both `Absence(lava)`. That is why the hard/soft tag must come from our prompt.

### FL-AT

- **[paper] FL-AT implements the product Reward Machine of Camacho et al. 2019** (its README
  links that paper; the research worker confirmed the construction matches,
  `dependencies/Flat/functions/functions.py:111,304,358`). Every formula only earns a reward;
  there is no hard/soft notion.
- **[run] FL-AT's original rewards repeat.** `add_reward` puts the formula's reward on every
  accepting DFA state, and each product edge pays the sum over clauses whose DFA is accepting
  after the step. A finished clause is paid again on every later step.
- **[run] Removing self-loop rewards is not enough with several clauses.** For "get the key and
  open the door" (two `Existence`), the edge that opens the door still pays 0.2 instead of 0.1,
  because the key is paid again. FL-AT renames product tuples to plain state names, so its
  output cannot show which part is the repeat. Evidence page:
  `.git/agent-memory/artifacts/flat-vs-ours-rm/` (scripts included).
- **[run] Under FL-AT's rewards, rule-like templates pay for doing nothing.** `Absence`,
  `RespondedExistence`, `Response`, IBM `Precedence`, `ChainResponse` and `NotCoExistence` all
  pay 0.1 every step the rule simply holds. `Response` and `ChainResponse` also have a rewarded
  cycle (S1 -> S2 -> S1) that stays farmable even after removing self-loop rewards.
- **[run] The product already has the "sections" a soft rule needs.** For
  `F goal` + `G !lava` there is a clean part (S1 -> S3) and a touched-lava part (S2 -> S4), and
  the goal is still reachable after lava. FL-AT only marks S3 accepting.
- **[run] Goal + Response needs no end-of-episode check.** For `F goal` + `G(a -> F b)`:
  S3 = goal done, nothing pending (the only accepting state); S4 = goal done, an `a` still
  waiting; S4 goes to S3 on `b`. Page: `.git/agent-memory/artifacts/response-goal-rm/`.
- **[code] The fork's changes are library and safety fixes**
  (`dependencies/Flat`, commit `d2708e0`): package imports, MONA via subprocess and temp files
  (upstream wrote `formula.mona` in the working folder through `os.system`), strict MONA output
  parsing, removal of MONA's provably do-nothing start state, regex-based proposition renaming
  (upstream split strings and ran `eval` on labels), and a plain dict output.
- **[code] The per-clause tuple already exists inside FL-AT's product** (`sdict`,
  `dependencies/Flat/functions/functions.py:315`); FL-AT just does not return it.

### Shaping and pattern behavior

- **[run] Goals vs rules can be told apart from the DFA alone:** is the clause satisfied when
  nothing happens? `Existence` and `ExistenceTwo`: no, so they are goals. The other six
  templates: yes, so they are rules. No hand-written template list is needed.
- **[run] Shortest distance to the goal is the wrong progress measure.** The product has
  shortcut edges where two events happen on the same step (key and door at once), so the start
  already looks one step from done and "get the key" pays nothing. The longest remaining path
  fixes it: in a scratch prototype the key step paid in all three examples (key and door;
  key strictly before door; key preferably before door), and opening the door first in the
  strict version cost -1.

## Decisions on the reward layer

### Rewards

- **[decision] Drop FL-AT's rewards and our per-clause 0.1.** Final rewards = progress
  shaping + task completion +1 + soft penalties. The clause 0.1 and the progress term reward the
  same thing.
- **[decision] Progress formula:** every edge adds `Phi(next) - Phi(current)`, with
  `Phi(u) = -k * sum over clauses i of w_i * remaining_i(u)`, `k = 0.1`, and `Phi = 0` at final
  states. `remaining_i(u)` is the longest path, in steps, from clause i's own DFA state to one of
  its accepting states (user, 2026-11-11). `w_i` is the chain weight of clause i: 1 plus the sum
  of `w_j` over every clause j that closing clause i opens in the same step, and 1 when it hands
  off to none (user, 2026-11-15). Clause i hands off to clause j when every edge that closes i and
  every edge that opens j force one shared proposition (the order is taken: it answers the arrival
  and starts the cooking); the start state of each DFA is left out, and a cycle of hand-offs counts
  once. Why: on a chain of rules (client arrives, order taken, food prepared, served) each step
  closes one rule and opens the next, so with every `w_i = 1` the middle steps paid 0. On the shop
  serve chain the pay is now arrive -0.3, order +0.1, cook +0.1, serve +0.1. The weights are fixed
  per clause, so the potential is still a difference of one function of the state, and without
  the learner's discount no loop gains. Think of each state as a to-do list: every goal and every
  rule is an item that counts the steps it still needs. A step pays 0.1 times the clause's chain
  weight (1 for a clause with no hand-off), and a new item or a step back costs the same, in
  tasks with and without a goal. Moving forward pays, staying pays 0, going
  back costs the same amount, and any cycle sums to exactly 0 (undiscounted). Source:
  Ng, Harada & Russell 1999.
- **[run + decision] The pay is undiscounted, the learner is not (gamma = 0.99).** A step pays
  `0.1 x weight x (owed_before - owed_after)`, with no discount, while the theorem above needs
  `gamma * Phi(next) - Phi(current)`. We keep the undiscounted difference for now; switching to
  the discounted one is not decided (user, 2026-11-15: decide after the shop runs). Two effects,
  measured in the process audit (2026-11-15; probes `follow_ups.py` and `sum_edges.py`):
  - **Starting a rule costs more than closing it pays.** A rule one step from closed, started and
    then closed k steps later, nets `-0.1 x w x (1 - gamma^k)` in discounted return, against 0
    for idling. C1-sum weights make `w` bigger. On a 3-stage chain of Response rules with the
    stages 20 steps apart, the net is -0.045 with every `w = 1` and -0.097 with C1-sum weights.
  - **A loop can pay a little.** The earlier claim that a cycle "cannot be farmed without limit"
    is true only undiscounted. On the 3-rule fork the best cycle nets +0.0195 per lap, and 80
    laps of a 640-step episode are worth about +0.25 in discounted return, against 0 for idling.
    Each lap is small, but the laps repeat until the time limit.
- **[decision] Longest path, not shortest, and per clause,** for the shortcut reason above, and
  because the environment may never produce the shortcut. Since 2026-11-19 this per-clause measure
  pays the soft clauses, and every clause when the machine has no final; the hard stages of a
  machine with a final read the machine's own distance (next entries). Each clause is measured on the DFA the
  product uses (for a soft rule, the re-armed one). Its accepting states absorb: their outgoing
  edges are left out, so a rule that is satisfied again and then opens again does not push the
  score away from it, and a rule that waits for an answer (`Response`) still has a distance. Each
  cycle of that DFA is collapsed to one node, so its states score alike. A violated clause counts
  0: a broken soft rule was already charged its break cost (`soft_break_cost`, 1), and a broken
  hard rule is the well. A clause's own break-and-repair loop passes through its accepting state, so the collapse does not
  touch it. The product is never collapsed, so a loop between two states that both owe something
  pays -x one way and +x the other; the old longest path of the whole product paid such a loop 0,
  and priced the same event differently depending on what else was pending. The sum around any
  loop is still 0, so nothing can be farmed without the learner's discount (with it, a loop can
  pay a little: see "The pay is undiscounted, the learner is not" above).
- **[decision] Known limit, accepted: a step that only a "before" rule names is never paid.** A
  `Precedence` is satisfied from the start, so it owes 0 and its first proposition pays nothing
  (`_steps_to_accept`, `_open_steps`); 6 of the 71 FARM main machines that store their clauses
  have such a step (user, 2026-11-15; list in the [RM execution record](decisions/arm-fm/rm-execution.md)).
  Lifted for a machine with a final state on 2026-11-19: its hard stages are read from the machine
  (next entry).
- **[decision] Hard progress reads the machine (2026-11-19).** With a final state, the pay for a
  hard stage is `Phi(source) - Phi(destination)` with `Phi(u)` the fewest events that take the
  product from `u` to a final state, one unit per event (`_events_to_final`). An edge costs the
  positive propositions its guard needs, at least 1, and self-loops and edges into the well are
  left out of that graph (the well edge is priced apart: next entry). Why: a chain "a, then b,
  then c" is `Existence(c)` + `Precedence(b, c)` + `Precedence(a, b)`, and only `Existence` owed a step, so the chain paid 0, 0, 0 and everything at
  the goal (doorkey 0, 0, +11). The machine already has the chain; the measure read the rules
  instead. A plain hop count is wrong: `Precedence` lets two events share a step, so the product
  keeps a direct start-to-final edge and the start looks one step from done; counting the events
  an edge needs fixes that (a prototype with plain hops fixed 0 and broke 15 to 26 passing sets).
  The per-clause soft stages and the no-final measure above stay as they were. No scaling: a chain
  of `n` events now pays `n` on the way and 10 at the end, so doorkey written as `Precedence` and
  as `Response` both pay 1, 1, +11 (13 in all, 11 before for both). Measured (MONA, no model
  calls): 87 of the 168 card sets pass the pay-order check before, 126 after on the same cards
  (127 of 167 once three cards were reworded to name every step); 39 failing sets were fixed and
  none newly failed. Of the 108 stored sets, 73 pass before and 80 after, 9 fixed and 2 newly
  flagged by the check's "started must pay more than not started" (a hard `Response` or
  `RespondedExistence` that opened for -1 now opens for 0, a tie with idling; a known false alarm
  of the check, postponed). The 40 card sets that still fail it all have that one reason: 26 with a
  final whose started state ties idling, and 14 rule-only, which the check now skips (see "What it
  does not fix"). With the refund and the skip below: 141 of 167 card sets and 91 of 108 stored.
  Superseded 2026-11-20: the false alarm is fixed and every set passes ("Started means closer to
  the goal", below).
- **[decision] A hard break takes back the progress made since the start (2026-11-19).** A chain
  pays on the way, and the edge into the well paid no progress, so a break after `k` events totalled
  `-H + k`: doorkey (form B) with lava after one key step paid -9 and after two steps -8, against -10
  for lava at once; with soft rules re-arming (the ceiling charge, -96.0959) 6 stored sets, all
  `cx-goal-many-rules`, had a break path that paid at least the soft ending (`~p3`: -94.0959 against
  -95.0959), so breaking the hard rule beat the soft stream. The check missed it: it reads the
  mildest well edge, not path totals. Now the edge into the well also pays
  `PROGRESS_REWARD * min(0, Phi(source) - Phi(start))`, added to the well charge, the finite end
  charge of the leaving state and the promise cost (the step limit's worth since 2026-11-20, see
  the promise cost decision). `Phi` is the potential `_progress` already
  uses and `start` the machine's real start (after `_drop_pre_step_start`), so a hard break totals
  the well charge plus the end charge of the state it leaves whatever came before (doorkey with lava
  after one and two steps: -10 and -10; `~p3` from the progress state: -98.0959 after +2). The clamp
  `min(0, ...)` takes back the progress since the start (the potential difference) and never pays a charge back: a hard `Response` trigger that
  leaves the machine further from done than the start charged -1, and the literal refund
  (`Phi(source) - Phi(start)`) pays that +1 back, which breaks the pay order in 3 stored sets
  (`shop-serve~p3`, no goal, pays +3 on a hard break; `cx-rules-only`, 2 sets, ties the soft and the
  hard break) and in every ceiling machine with a hard `Response` and a soft rule. The refund is the
  user's decision, and so is the clamp (approved 2026-11-19 23:57; dropping `min(0, ...)` in
  `_progress` gives the literal form). Measured on the 275 sets (MONA, no model calls): the break
  paths above `-H` fall from 51 to 0, those at or above the soft ending from 6 to 0, no set that
  passed the pay-order check fails now, and no card plan pay changes. Limits, both harsher and never milder: a
  soft break on the way withholds that clause's stages from the progress paid but not from the
  take-back, so the break then totals a little below `-H`. The learner discounts: the refund comes
  later than the progress it takes back, so a small share of the progress stays (a break episode
  still never beats the safe one in any real set).
- **[decision] With no final state, progress needs no other target.** A rule-only task has no
  final. A product state where each clause is satisfied (accepting) or violated, and none is
  waiting for something to happen, owes 0 in every clause, so it sits at `Phi = 0` without a
  special case. A state from which no such state (a final, in a goal task) can be reached, and
  the edge into it, pay no progress: otherwise a step into a dead end would pay for getting
  nowhere. An edge into a well is not paid progress either: it takes the progress made back
  (previous entry). A machine with a final pays the same
  per-clause progress (it used to be the longest path of the product to the final), and a soft
  clause that starts or stops waiting counts as paid there too. The simulation of the earlier
  rule, the numbers and the dead-end witness: [rule-only progress](paper/rule-only-progress/README.md);
  the new rule on three examples: [rule-only rewards](paper/rule-only-rewards/README.md).
- **[run + decision] The duplicate start is dropped, so an idle first step pays 0.** MONA gives
  each rule clause a "no step yet" start state that is left on the first step and never re-entered.
  On every input it goes where the state after an idle step goes, so the product carried one extra
  start that would sit one step further from the goal and pay +0.1 for doing nothing. After the hard
  passes, `_drop_pre_step_start` removes that start and makes its idle successor the start, but only
  when nothing re-enters it, the successor is neither the well nor a final, and both states go to
  the same state on every valuation; otherwise the RM is left as is. Same machine, one state fewer:
  19 of the 25 T2.1 RMs (every task with a rule clause) lost exactly that state, with every reward
  and walk total unchanged (`samples/start_merge_check.py`, 25/25). This replaced an earlier fix
  that only gave the start its successor's progress score.
- **[decision] No infinities.** An edge into a well gets a finite charge: the well's -1 plus the end
  charge of the state the edge leaves (user, 2026-11-11; see "The end judgment"), and since
  2026-11-19 the progress made since the start taken back, at most that much ("A hard break takes
  back the progress made"). Ng's theorem also needs a bounded score. Some papers use -infinity for
  rejecting states; we do not need it.

### Why no loop gains reward, undiscounted, and how we check it

Two things keep every loop at 0 or below, counting rewards without the learner's discount (with
the discount a loop can pay a little: see "The pay is undiscounted, the learner is not" above):
how the rewards are built, and one check on the finished RM.

- **[code] By construction.** Progress is a difference of one score per state, so around any loop
  the differences cancel. A loop that goes up one way comes down the same amount the other way
  (the cycles inside one clause's DFA are collapsed, so those states share a score and pay 0
  between them). The other rewards cannot repeat
  for gain: the finish reward (10) and the soft finish penalty are paid only on edges into the final, the well's
  charge (-10 plus the open promises, and the progress taken back) only on edges into the well,
  and both are absorbing. A soft
  break costs `soft_break_cost` (1) and is not refunded: the clause a step breaks pays no progress
  on that step, so the break step pays -1 at any chain weight W (1 plus the weights of the rules it
  hands off to). Until 2026-11-18 (commit `deff802`) a broken soft rule owed 0, so its weighted
  potential was refunded at the break and a soft rule one step from closing paid `0.1 W - 0.5`:
  -0.4 at W = 1, positive from W = 6 (probe `break_credit.py`); that refund is gone, and no
  current soft clause has W above 1 (scan of 2026-11-16 with `_chain_weights`; see the
  [RM execution record](decisions/arm-fm/rm-execution.md)). The trigger and the break together
  cost `W + 1` (-2 at W = 1), so a loop through a re-armed soft rule (see "Recurrent soft rules")
  loses reward on every lap. With the switch off a broken clause
  stays broken (its DFA cannot leave a violated state), so the break is paid once. Dropping the duplicate start removes a state and its edges
  and adds none, so it cannot open a loop.
- **[code] Checked on every RM.** After the rewards are set, `_has_positive_cycle` in
  `app/src/compiler/reward_layer.py` runs Bellman-Ford on the undiscounted rewards: if the best
  total reachable at some state still grows after as many rounds as there are states, a loop pays
  more than 0, and the compile fails with "Reward Machine has a positive reward cycle".
- **[run] Tested.** The T2.1 live test (27 clause sets, all eight templates, hard and soft)
  checked every RM for a positive loop with its own networkx code: none found, 253/253 checks.

### Why shorter RM paths get no extra reward

An idea raised on 2026-10-14: pay a bonus on routes that cross the RM in fewer transitions (the
direct edge from start to final would earn more than the three-step route). Decided against,
for three reasons.

- **[paper] The progress reward is potential-based and the bonus is not.** Progress pays
  `0.1 x` the drop in the longest remaining path, so every route from the start to the final pays
  the same total (the direct edge pays it at once, the long route in instalments). That is the
  shaping of Ng, Harada and Russell (1999, `docs/RMs/Reward-Shaping-Ng-1999.pdf`): a difference of
  one potential per state never changes which policy is optimal. The bonus makes routes pay
  different totals, so it would change the optimal policy, which is the thing the literature
  avoids; Icarte et al. (JAIR 2022, section 4.4) and Camacho et al. (IJCAI 2019) shape reward
  machines the same potential-based way.
- **[run] RM path length is not environment steps.** A short RM route means several facts became
  true on one environment step (key and door at once), which the environment decides far more
  than the agent; in DoorKey it is not a choice at all. The discount already prefers fewer
  environment steps.
- **[decision] Strictness is a template question, not a reward one.** Where "only after" must
  forbid "at the same step", the right tool is a strict precedence template
  (`(!b U (a & !b)) | G(!b)`), noted for a later iteration, not a reward that pays "at once" more.

### Graph passes and the library behind them

The reward layer runs its graph passes with [networkx](https://networkx.org/) 3.6 (declared in
`requirements.txt` and `pyproject.toml`; it also arrives through FL-AT's `dd`). Each call, where
it is used in `app/src/compiler/reward_layer.py`, and the algorithm behind it:

| Call | Used for | Algorithm |
|---|---|---|
| `nx.descendants` | prune states the start cannot reach (pass 5) | breadth-first search |
| `nx.ancestors` (in `_reaching`) | find states that can still reach a final or a clause's accepting states (passes 1 and 4) | breadth-first search on the reversed edges |
| `nx.condensation` | collapse every loop of one clause's DFA into one node before measuring what the clause still owes (`_steps_to_accept`) | strongly connected components: Tarjan's algorithm with Nuutila's changes (Tarjan 1972; Nuutila & Soisalon-Soininen 1994) |
| `nx.topological_sort` | visit that collapsed DFA from its accepting states backwards to get each state's longest remaining path | topological order (Manber 1989); the longest path itself is a short loop of ours: `steps = 0` at an accepting state, else `1 + max(steps of the successors)` |

The positive-loop check is our own Bellman-Ford (Bellman 1958), about ten lines, run on
the finished RM.

### Hard and soft

- **[decision] Hard/soft is set per clause, independently,** by our prompt's output. The tag
  never changes the LTLf formula. Soft changes rewards and, with recurrent soft rules on,
  re-arms a broken soft rule (edges only, no new states); hard changes rewards and the RM's
  structure.
- **[decision] Soft is what FL-AT's product gives for free.** The agent may finish in a bad
  state but pays a penalty. Keeping a preference earns nothing: the +0.25 finish bonus for a kept
  soft clause was removed in both switch positions (2026-10-23, user: it is redundant next to the
  penalty; it reversed 2026-10-12). A soft rule ("if possible never touch lava") keeps the clean
  and the touched section, and entering the touched section pays -0.5; with the recurrent soft
  penalty off that is the only charge, with it on the next break pays again (next section).
- **[decision] Hard means the agent cannot finish in a bad state.** A permanent violation goes
  to one shared well (penalty, episode ends). A fixable one, such as a pending `Response`, only
  blocks finishing until it is fixed; it never ends the episode early.
- **[decision] Soft clauses never affect the final condition.** If the agent touches lava under
  a soft rule, it still has to open the door to finish. Final = every hard goal clause done and
  every hard rule clause satisfied. Soft clauses change the reward on the finishing edge (-0.5 for
  a soft clause still pending: a soft goal, or an open obligation such as `ChainResponse`'s), on
  the edge where they break, on an edge where one more step of a soft clause is done or undone
  (the per-clause progress, 0.1 times the clause's chain weight, 1 for a clause with no
  hand-off), and when the environment ends the episode with the
  clause still open (the end judgment, -0.5 per open soft clause).
- **[decision] A final state judges on its last edge; an end the environment forces is judged where
  it happens.** Reaching a final state ends the episode, so the rule is judged on that last edge.
  An episode the environment ends first (the time limit, or a termination) is charged for each
  promise still open in the RM state, in every compiled machine, with or without a goal (see "The
  end judgment"). This reverses the earlier "no end-of-episode check in the RM", which left such a
  run with the flat time-limit penalty and nothing else.
- **[decision] States are classified per clause, from each clause's own DFA** (through `sdict`),
  not from the merged RM's "can still reach the goal", which mixes hard and soft violations.
- **[decision] Regressions exist only if the task or environment states them.** "Drop the key"
  matters only when a proposition such as `key_lost` exists and a clause uses it. A plain
  `Existence(has_key)` (`F has_key`) never goes back.

### Recurrent soft rules

- **[decision] Why.** An LTLf formula gives one verdict per trace: it says whether a rule was broken,
  not how often. So a soft rule's break was charged once per episode: an agent that broke a preference 15 times got the
  same reward as one that broke it once. With recurrent soft rules on (`--recurrent-soft-penalty`,
  the default, also a web checkbox, recorded in every run) each new break costs -0.5.
  `--no-recurrent-soft-penalty` keeps the single charge. Decided 2026-10-23 (user and supervisor).
- **[decision] What.** It applies to a soft clause of `Absence`, `Precedence`, `ChainResponse` or
  `NotCoExistence`, the four templates whose DFA has a violated state. The others stay as they were:
  - `Existence` and `ExistenceTwo` are goals; paying again would invite reward farming.
  - `RespondedExistence` never breaks in the middle of an episode and has no exact recurring
    version: the two close ones, `Precedence` and `Response`, each fix an order, and on `x y x`
    the rule holds while `Response` leaves the last `x` unanswered (see the
    [note](paper/recurrent-soft-rules/README.md#rules-that-only-say-eventually-no-repeat)).
  - `Response` already re-arms; its DFA has no violated state.
- **[code] How.** `_rearm_violated` (`app/src/compiler/reward_layer.py`) rewrites a copy of the
  soft clause's DFA before FL-AT builds the product:
  - The states are labeled first, on the original DFA. A re-armed state is no longer a trap, so
    labeled afterwards it would read as pending, and the -0.5 (a step from a not-violated state
    into a violated one) would never fire.
  - Each violated state drops its own edges and copies the edges of the DFA's start state (MONA's
    "no step yet" state). A copied edge keeps its destination, except that an edge into a violated
    state loops on the state instead: a step that breaks the rule again while it is still broken
    is charged again as a new break, and the rule is armed again on the next step.
  - No state is added and no table is needed. Hard clauses, and every clause with the switch off,
    reach FL-AT unchanged. The input DFAs are not mutated.
- **[run] Shape.** Each of the four templates has a start `S1`, an idle twin `S2` with the same
  successors, and one absorbing violated state; no copied edge points back at `S1`, so the start
  merge still applies. A single soft rule keeps its RM state count.
- **[code] A soft `Absence` folds its broken state.** The re-armed violated state has the same
  exits as `S2`, so `_violated_twins` pairs them and `_clause_product` folds each product state that
  differs only by that state into one. The break stays as an edge mark (`_Product.breaks`) that
  `_price_edges` charges and `_progress` does not refund, so every trace pays as before and
  `lanes-rules` shrinks from 5 states to 2 (start and well). It applies to a soft `Absence` only
  (`_is_absence`: one proposition, and every live state breaks on it, so a break is charged alike
  from all of them); `Precedence`, `ChainResponse` and `NotCoExistence` have the same twin and are
  left as they were.
  - The fold is the setting `fold_soft_absence` (on by default; `--no-fold-soft-absence` on
    `generate-rm` and `generate-larm`). It needs the recurrent soft penalty: with the penalty off
    nothing is re-armed and nothing folds. The manifest records it. With it off the machine is the
    one the layer built before the fold, state for state.
  - `rebuild-rewards` and `ablate-rm` keep the recorded value and cannot change the states, so
    they refuse a bundle that records no `fold_soft_absence` when the fold would change its
    states (a soft `Absence`): it was made without the fold, so it has to be rebuilt (generated
    again). `rebuild-rewards --charge-once` needs a bundle built with `--no-fold-soft-absence`:
    charging once brings back the broken state that the fold removed.
- **[run] The supervisor's examples** (`x` and `y` are the template's `a` and `b`, `-` is a step
  with neither). With the switch on, each row charges:

  | Template | Steps | Charges |
  |---|---|---|
  | `Absence(x)` | `x x` | 2 |
  | `Absence(x)` | `x !x x` | 2 |
  | `Precedence(x, y)` | `x y y` | 0 |
  | `Precedence(x, y)` | `y - y x` | 2 |
  | `ChainResponse(x, y)` | `x y` | 0 |
  | `ChainResponse(x, y)` | `x - x -` | 2 |
  | `NotCoExistence(x, y)` | `x y` | 1 |
  | `NotCoExistence(x, y)` | `x y x` | 1 |
  | `NotCoExistence(x, y)` | `x y x y` | 2 |

  With the switch off, each row charges at most 1.

- **[decision] The charge is per new break.** A step that breaks the rule again while it is still
  broken is charged again as a new break, and a clean step arms the rule again. `Absence(x)` on
  `x x x` charges 3, on `x - x x` charges 3; `Precedence(x, y)` on `y y` charges 2. The accepted
  `ChainResponse` result `x x -` = 1 stays: the first `x` opens the answer owed, the second `x`
  breaks it and is charged once, and the clean step after it breaks nothing.
- **[run] Progress is re-scored.** A violated clause counts 0 and the re-armed rule's clean state
  is accepting, so the rule owes 0 before and after a break and the break step pays -0.5 plus no
  progress for that rule. (Before 2026-11-11 the re-arm joined the clean and the broken product
  state into one loop, and `_progress` paid 0 inside the merged loop.) With a hard
  `Existence(at_goal)` and a soft `Absence(key_lost)`:

  | Case | Off | On |
  |---|---|---|
  | Clean finish | 1.1 | 1.1 |
  | Break step | -0.5 | -0.5 |
  | Break on the finishing step | 0.6 | 0.6 |

  Totals of the current compiler (rebuilt and walked on 2026-11-16, no model call). A single break
  costs the same On and Off; the switch only matters from the second break on (see "The
  supervisor's examples" above).
  The first version of this table, from before the per-clause progress of 2026-11-11, read
  1.45 / -0.4 / 0.7 without the change, 1.2 / -0.4 / 0.7 Off and 1.1 / -0.5 / 0.6 On. Off moved
  because the old longest path of the product paid progress on the break step and the per-clause
  count does not.
  The gap between a clean and a one-break finish stays 0.5. Against the off position a clean
  finish can lose 0.1 (`Absence`, `ChainResponse`) or 0.2 (`NotCoExistence`) of progress.
- **[run] The product can grow with several soft rules.** The re-arm adds edges between states
  that were separate, so the product of two or more rules can reach more states than before: 8 of
  the 12 pairs of the four templates grew, and all four with a goal went from 11 to 13 states.
- **[decision] Forced breaks.** Tasks are assumed free of contradictions (above), so a soft rule
  that every way of finishing must break is not checked. With n forced breaks, finishing pays
  1 - 0.5n plus progress: about a timeout's -1 (the goal still open) at n = 4, and no more than
  the well's -2 (-1 plus the open goal) from n = 6-7.
- **[decision] A soft clause already violated at the start pays nothing,** as before: it is inert,
  and the compile warning names it.

### Pricing the hard break against soft breaks

The pay is in whole units since 2026-11-17 (`Configuration.PROGRESS_REWARD` = 1, finish 10, flat
well -10); the 0.1 and 0.5 figures in the sections above are from before that change.

- **[run + decision] The defect.** With the old defaults (soft break cost 5, flat hard break -10,
  recurrent soft charging) a stream of soft breaks costs more than one hard break: the forcing
  card `lanes-rules` pays -475 at gamma 0.99 over 300 steps for the worst stream of soft breaks
  against -10 for letting a zombie through the top lane, so breaking the hard rule pays better.
  `check-pay-order` flags it ("soft break must pay more than hard break"); the E2 runs measured
  it. Of the 168 clause sets of the benchmark cards (expected clauses and every `also_ok`
  option), 9 failed that line, and none fails it with the defaults below (offline sweep,
  2026-11-19, MONA and no model call).
- **[decision] The default is the ceiling at a soft break cost of 1** (`Configuration.hard_ceiling`
  on, `soft_break_cost` 1). Where soft rules repeat, the edge into the well charges
  `-(max(10, N x S x (1 - g^T) / (1 - g)) + 1)`, with `S` the soft break cost, `N` the soft breaks
  one step can charge (`soft_breaks_per_step`, default 1: it depends on the environment and the
  task, so the user sets it), `g` the training discount and `T` the level's step limit; `g = 1`
  reads `(1 - g^T) / (1 - g)` as `T` (`hard_break_charge`, `app/src/compiler/reward_layer.py`).
  The worst stream of soft breaks, discounted from the first step, costs the ceiling, so one more
  unit makes the hard break always dearer. `S` 1, `N` 1, `g` 0.99, `T` 300 gives -96.0959; `T` 576,
  -100.694; at `T` 5 and `g` 0.9 the flat -10 is the larger and stays. A machine with no soft rule,
  or with `--charge-once`, keeps the flat -10: no stream to outweigh. `S` is 1 because at 2.5 and
  above the agents learned to idle (E2), and the ceiling already makes the stream safe.
- **[decision] `N` stays 1, also where two soft rules can break on one step** (user, 2026-11-21).
  Each broken soft rule still charges, so two on one step cost 2 (`lanes-rules`: a side breach and a
  trampled plant). The ceiling then covers one break per step only: a stream of double breaks on
  every step could, in theory, cost more than the hard break (-190.192 against -96.0959 at `g` 0.99,
  `T` 300), and the pay-order check run with `--soft-breaks-per-step 2` fails such a machine. No run
  comes near that stream (the `lanes-rules` guard loses 4.5 side-lane zombies in 300 steps), while
  doubling the hard price widens early returns, when most episodes end in the hard break, from about
  -97 to about -192, with no reward rescaling in training. Raising stays available:
  `--soft-breaks-per-step N` prices the ceiling for `N` breaks per step and the manifest records it.
- **[code] Where `g` and `T` come from.** `g` is `Configuration.gamma`, the discount the trainers
  use. `T` is the level's step limit, read from the environment (`gym_step_limit`, through
  `configured_step_limit`): `--gym-id` with `--env-kwargs`, or `--step-limit`. `generate-suite`
  passes each card's own `env.gym_id` and `env.env_kwargs`. A command that prices a repeating soft
  break without a level stops before any model call and says so; `--no-hard-ceiling` gives the
  flat -10 back for the settings study.
- **[code] The record and the check.** A bundle's manifest records `soft_break_cost`,
  `soft_breaks_per_step`, `gamma`, `step_limit` and `hard_ceiling` (`effective_settings`), and
  `train-rl` refuses a run whose gamma, step limit or breaks per step differ from them.
  `generate-larm` (compiler mode) and `rebuild-rewards` run the pay-order check on the bundle they
  built and store `effective_settings["pay_order"]` (`ok`, the hard break charge, the summary
  line); a broken order prints a warning and nothing is refused. With no step limit, or if the check
  itself fails, the record says `not checked: no step limit` or `check failed: <error>` (`ok` is
  null) and a warning prints, so a run that cost model calls never loses its bundle.
  `rebuild-rewards` keeps the pricing a bundle records (cost, ceiling, gamma, breaks per step)
  unless the command gives another, and its log names each value's origin; a bundle made with the
  old defaults needs `--soft-break-cost 1 --hard-ceiling` with the level to move to the new ones.
  A bundle that records no `hard_ceiling` was made before it existed, so it reads as flat.
- **[run] What it does not fix.** The order "started must pay more than not started" fails on
  clause shape, not on price: a machine with no `Existence` per milestone (a `Precedence` chain,
  a rule-only task) has no step that pays progress before the end. 56 of the 111 expected clause
  sets fail it with the new defaults and with every soft break free of charge, so pricing
  cannot cure it. The progress pay was unchanged at that point and these cards were only reported.
  Since 2026-11-19 a machine with a final pays the steps of a `Precedence` chain too (see "Hard
  progress reads the machine"); a rule-only task of `Precedence` rules still pays no progress
  before the end, because a machine with no final keeps the per-clause measure. The check no
  longer asks that of a machine with no final: with nothing to start, idle keeps every rule and a
  started state pays the same, so the "started must pay more than not started" line is skipped
  there and the summary says so (`skipped started > not started (no goal: idle keeps every rule)`).
  Every other line still counts. This clears the 14 rule-only card sets and the 11 stored ones that
  failed it; the 26 card sets and 17 stored sets that still fail it all have a final (superseded
  2026-11-20, next entry). Two
  soft-goal rule-only cards passed that line strictly and lose it: a soft goal with no final still
  pays its own progress, which no check reads now, so a test pins it.
- **[decision] Started means closer to the goal (2026-11-20).** The check's "started" state must
  owe fewer propositions than the start: the fewest that must still come true to reach a final
  state, on the shortest path that avoids rejecting states, each edge costing the positive literals
  its guard needs, so one step can make several true (`_owed`, `app/src/arm_fm/pay_order.py`; the
  guard count is `fewest_true` in `reward_machine.py`). The sets that still failed did so because
  their only started states remembered a trigger, such as the `a` of a soft `Precedence(a, goal)`,
  or of a `Precedence(a, b)` whose `b` the goal does not need, or an opened `Response`, and paid no
  more than idling; such a state owes as much as the start or more,
  so it no longer counts as started. A key the goal needs still counts, and paying 0 for it still
  fails.
  Measured on today's cards (MONA, no model calls): 106 of 130 card sets and 91 of 108 stored sets
  pass before, all after; with promise cost on, 125 of 130 before and after.

### Cleanup passes, in order

1. **Label each clause's DFA states** as satisfied (accepting), pending (not accepting, accepting
   still reachable) or violated (accepting never reachable again). This is a reachability check on a
   small DFA, so it is exact, not a guess (matches the four-valued monitors of De Giacomo et al.
   2020). Each clause DFA must be total, with exactly one transition per valuation; a missing or
   duplicated transition is a compile error naming the clause. The labels come from the original
   DFAs; with recurrent soft rules on, the soft clauses are then re-armed on a copy, and the product
   keeps those labels (see "Recurrent soft rules").
2. **Redirect hard violations:** every edge whose target has a hard clause violated goes to one
   shared well instead.
3. **Remove "final" where a hard clause is not satisfied** (for example "goal done, `Response`
   pending"). The state already exists in FL-AT's product; it just stops counting as final.
4. **Send hopeless states to the well:** states from which no final state is reachable any more.
   Otherwise the agent could wander forever in a part of the RM that can never finish.
5. **Prune states unreachable from the start.** After the redirects, states that were targets can
   be left with no incoming edges.
   Then **drop the duplicate start** when it matches its idle successor on every input (see
   Rewards above). Apart from joining the finals into one node and hard violations into one well,
   this is the only merge the layer does. It keeps every reward because no catalog template is
   broken by an idle step, so the soft terms price the old start and its successor alike.
6. **Minimization: deferred (decision 2026-10-12), on by default since 2026-11-21.** It works only with the right starting
   groups: one final group, one well group, and the other states split by which soft clauses are
   violated. **[run]** On FL-AT's RM for "reach the goal, if possible never touch lava", Moore's
   refinement (our former `_equivalence_partitions`, `app/src/compiler/reward_machine.py:530` at commit `5b74afe`) started
   from final / not final only merges the clean and the touched sections (S1 with S2, S3 with S4):
   the mirror edge S1 -> S2 looks like "stay in my group", the same as S2's own lava self-loop.
   With the soft-violation split they stay apart. The gain (fewer states to describe and embed)
   is small next to that risk, so the first version skips it; FL-AT's product is kept as is
   after pruning. A re-armed violated state keeps its violated label, so that split still holds.
   Since 2026-11-21 `minimize_machine` (`_merge_equivalent` in `app/src/compiler/reward_layer.py`) merges
   only states with the same pay on every step, the same end and the same next states, so the
   lava case above stays split. It does merge a soft rule's kept and broken states when the
   recurrent penalty makes them act alike (10 of 131 card answers); see
   `docs/decisions/arm-fm/rm-execution.md`.
7. **Compute rewards** on the pruned RM: progress, task completion, soft penalties.

After passes 4 and 5, check that a final state is still reachable; if not, report the task as
having conflicting clauses.

### Episodes, rewards and critics

- **[code] Before this redesign the RM never ended an episode.** The RL wrapper took `terminated` only from the
  environment and returned environment reward + RM reward (`app/src/arm_fm/runtime.py`, before Slice 1).
- **[decision] The episode ends in any of these cases:** the environment terminates, the RM
  reaches a final state, the RM reaches the well, or the time limit / step limit is hit, for all
  runs. Only declared finals count: the ARM-FM authors' released RMs declare none, so imported
  author bundles end on the environment or the time limit (an inferred final can come before the
  environment goal). Hitting the time limit adds -0.5 to the RM reward, except for a machine with an
  end judgment, which charges its open promises instead (see "The end judgment"). Source:
  Toro Icarte et al. 2022 end the episode on RM terminal states; ARM-FM never says it.
- **[decision] Reward source is a flag** `reward_source: rm | env | both`, default `rm`
  everywhere, paper-reproduction configs included (the original RM papers use the RM as the only
  reward; this departs from ARM-FM's environment + RM sum). `env` means no RM at all.
- **[decision] One critic, at the end.** There is one non-deterministic step (the LLM's clauses),
  so there is one thing to critique. The critic gets the task, the generator's clause output and
  the compiled RM, with the generator's guidelines plus critique guidelines. It replaces today's
  task critic and RM critic.
- **[decision] Rule-only tasks are allowed.** A task with no hard goal clause gets no final state;
  only a well, the environment's end, or the time limit ends it, and the machine judges that end
  itself (see "The end judgment"). The critic accepts it, and the UI and CLI warn the user.
  Preference-only tasks are worth exploring later.
- **[decision] A hard goal with no reachable final is an error,** reported as conflicting
  clauses (e.g. `Existence(p)` + `Absence(p)`), never compiled as a rule-only task.
- **[decision] Soft clauses without reward effect are allowed and named in the warning.** In a
  task with no hard goal, soft clauses never reach a finishing edge, so the soft finish penalty
  never applies. What a soft clause can still pay is its break penalty (at every new break when
  recurrent soft rules are on, once otherwise) and the progress step where it starts or stops
  waiting. A soft clause that pays neither on any edge is inert and named in the warning. The
  progress step is judged by a proxy (the clause's waiting flips on an edge that pays progress),
  approximate both ways: it can call a clause paid that changes nothing, or inert when it changes
  rewards. A machine with a final used to count only the break and the finish; since 2026-11-11 it
  counts the progress step too, like a machine with no final.

### The end judgment

- **[decision] A compiled machine judges an episode the environment ends.** On a step where the
  environment terminates or truncates the episode and the RM did not (no final and no well
  entered), the reward adds `hard x HARD_FAILED_REWARD + soft x SOFT_FAILED_REWARD`, with the
  counts of the RM state after that step's update (`RewardMachineEnvironment.step`). It is paid
  once, since the episode ends there, and never when the RM ended it. It replaces the flat -0.5
  time-limit penalty; `info["rm_reward"]` includes it. The user's framing: the machine "accepts" or
  "rejects" the string of propositions the environment generated, so the end judgment is the link
  between the environment and the language side of the RM. Until 2026-11-11 only a machine with no
  final state was judged this way; a machine with a final kept the flat -0.5.
- **[decision] A goal is a hard promise (user, 2026-11-11).** In a task with a goal, an episode the
  environment ends while the goal is still open is charged for it like any other open hard item:
  -1 for the goal and each hard rule still open, -0.5 for each soft one. `Open the door. Whenever
  the box falls off the shelf, preferably put it back.` charges -1 at the time limit in the start
  state (the goal) and -1.5 in the state where the box has fallen (the goal and the soft
  `Response`), instead of the flat -0.5 in both. The final state still ends the episode as before,
  so the charge is paid only when the environment ends the episode first. The check:
  `docs/paper/rule-only-rewards/check/todo_list_check.py`.
- **[decision] The RM text carries the judgment.** The compiler writes `ACCEPTING_STATES` (the
  states where no clause is pending), the two values `HARD_FAILED_REWARD: -1` and
  `SOFT_FAILED_REWARD: -0.5`, and last `PENDING_PROMISES`, one row `uN: hard H, soft S` per state
  that is neither accepting, final nor the well. It computes them from the product labels after the
  states are numbered (`_end_judgment` in `reward_layer.py`), never by hand and with no clause
  names. A soft rule broken for good was paid when it broke and counts as accepted; a hard rule
  broken for good is the well, which rejects, ends the episode on its own, and is in neither list.
  In a machine with a final state every other state has a hard clause open (the goal, or a hard
  rule that waits), so none of them accepts: `ACCEPTING_STATES:` is written empty, like
  `FINAL_STATES:` in a rule-only machine. An imported author bundle has none of these lines and
  keeps its text, rewards, flat -0.5, bootstrap and success rule.
- **[decision] The parser stays lenient on the old format and strict on the new lines.** A text
  without the new lines parses as before. A text without the two values takes the
  `Configuration` defaults (`HARD_FAILED_REWARD`, `SOFT_FAILED_REWARD`). A state that is both
  accepting and pending, a final or rejecting state that is listed, a state that is neither final,
  rejecting, accepting nor pending, or a row for an unknown state is rejected. `PENDING_PROMISES`
  must be the last section. Serialize, parse, serialize is byte-identical on both public paths (the
  paper text and the numeric structure). The two values are the only part meant to be edited.
- **[decision] Success of a rule-only run.** `rm_accept` is true on the last step of an episode the
  environment ended in an accepting state, and `is_success` (`success: rm`) is true whether the
  episode terminated or was truncated (user, 2026-10-27). A machine with a final keeps its rule:
  success needs the final, since it has no accepting state (user, 2026-11-11).
- **[decision] The trainers do not change.** PPO and DQN keep their time-limit bootstrap and receive
  the charge as part of the step reward ("keep it but add ours": user, 2026-10-27).
- **[decision] No loop gains reward.** The charge is paid once, at the end of an episode, outside
  any edge, so `_has_positive_cycle` and the cycle argument above are untouched and a loop cannot
  farm it.
- **[decision] An edge into the well also charges what is still open (user, 2026-11-11).** The
  edge pays the well's -1 plus the end charge of the state it leaves, `hard x HARD_FAILED_REWARD +
  soft x SOFT_FAILED_REWARD` with that state's `PENDING_PROMISES` counts (`_price_edges` in
  `reward_layer.py`). The user's words: the arrows into the wells "do get the today's point plus,
  or in this case minus, the same reward penalization that the agent would get by finishing the
  environment time limit on that state." A source state with nothing open keeps -1. The edge paid
  no progress then (since 2026-11-19 it takes back the progress made: "A hard break takes back the
  progress made"), and the episode ends in the well with no further charge, so the runtime needs
  no change: the number is in the edge's reward. Breaking a rule is now always strictly worse than
  timing out in the same state. With three hard items open, a break used to cost -1 against -3
  for idling to the time limit; now it costs -4. The check:
  `docs/paper/rule-only-rewards/check/todo_list_check.py`.
- **[decision, solved] Idling with two hard promises open used to cost more than breaking a hard
  rule on the last step.** Two open hard promises charge -2 at the time limit, and breaking a hard
  rule on that step cost only the well's -1, since the RM then ends the episode and the end is not
  charged again. The plan review found it and it was first disclosed and kept
  ([rule-only progress](paper/rule-only-progress/README.md)). The well charge above solves it: the
  same break now costs -1 plus the same -2.
- **[decision] An optional promise cost, off by default (user, picked 2026-11-15, go
  2026-11-16).** With `--promise-cost` (`reward_promise_cost`), every step taken while a hard
  promise is open pays an extra -0.01 (`PROMISE_COST_REWARD`, `_price_edges`), once however many
  are open and nothing when none is; the end charge and the well's -1 stay (since the x10 pay
  change: -0.1 per step and a well charge of -10). `rebuild-rewards
  --promise-cost` turns it on in a saved bundle. The reason is in
  [rm-execution](decisions/arm-fm/rm-execution.md). Since 2026-11-20 (user decision) the step into
  the well pays it once per step of the level's step limit, so a hard break never pays more than
  keeping the promise open to the end; the build needs a step limit, and `train-rl` refuses a level
  whose step limit differs from the one the bundle records.

### FL-AT change

- **[decision] Return `sdict`** from `dfa_intersection_to_rm` (about 3 lines in the fork) so every
  product state tells which state each clause is in.

## Sources

| Source | Local copy | What we take from it | Checked |
|---|---|---|---|
| Ng, Harada & Russell 1999, "Policy invariance under reward transformations" ([PDF](http://luthuli.cs.uiuc.edu/~daf/courses/games/aipapers/ml99-shaping.pdf)) | `docs/RMs/Reward-Shaping-Ng-1999.pdf` | The progress formula (Theorem 1, Eq. 2); differences of a potential sum to 0 around any cycle, which fixes the "bicycle riding in circles" farming (p.3); only potential-based shaping keeps the best policy unchanged | [paper], read by us |
| Toro Icarte et al. 2018, "Using Reward Machines for High-Level Task Specification and Decomposition in RL", ICML ([link](https://proceedings.mlr.press/v80/icarte18a/)) | `docs/RMs/RMs-ICML-2018.pdf` | Reward Machine definition: rewards live on transitions | [paper] |
| Toro Icarte et al. 2022, "Reward Machines: Exploiting Reward Function Structure in RL", JAIR ([arXiv](https://arxiv.org/abs/2010.03950)) | `docs/RMs/RMs-Paper.pdf` | Potential-based shaping over RM states; self-loops get a small non-farmable reward; a bad terminal state gets positive shaping unless penalized, which is why our wells need a real penalty | [paper] |
| Camacho et al. 2019, "LTL and Beyond", IJCAI ([PDF](https://www.ijcai.org/proceedings/2019/0840.pdf)) | `docs/RMs/LTL-and-Beyond-Camacho-2019.pdf` | The product Reward Machine that FL-AT implements; each formula only earns a reward (no "hard"/"soft" in the paper), so soft-by-default is the base construction | [paper] |
| De Giacomo et al. 2020, "Temporal Logic Monitoring Rewards via Transducers", KR ([link](https://proceedings.kr.org/2020/89)) | `docs/RMs/Monitoring-Rewards-DeGiacomo-2020.pdf` | Per-formula verdicts temporarily/permanently true/false, i.e. our satisfied / pending / violated labels, turned into rewards | [paper] |
| Gerevini & Long 2005, "Plan Constraints and Preferences in PDDL3" ([PDF](https://lpg.unibs.it/ipc-5/booklet/deterministic00.pdf)) | `docs/RMs/PDDL3-Gerevini-Long-2005.pdf` | The hard/soft split: "Strong constraints and goals must be satisfied by any valid plan, while soft constraints and goals express desired constraints and goals" | [paper] |
| De Giacomo et al. 2019, "Foundations for Restraining Bolts", ICAPS ([link](https://ojs.aaai.org/index.php/ICAPS/article/view/3549)) | `docs/RMs/Restraining-Bolts-DeGiacomo-2019.pdf` | Soft-only formula rewards; a failure state is one from which no formula can be satisfied (our "hopeless" pass) | [paper] |
| Castanyer et al. 2025/26, ARM-FM ([arXiv](https://arxiv.org/abs/2510.14176); authors' code [roger-creus/llms-rm-rl](https://github.com/roger-creus/llms-rm-rl)) | `docs/ARM-FM/ARM-FM.pdf` | The baseline: the LLM picks the reward numbers; the prompt only says "Densify the reward signal" (p.26); self-loops pay 0; negative "went backwards" edges; "no positive cycles" (Prop. 1) is checked only by the LLM critic, and the paper's own Meta-World RM has a +0.2 cycle. Motivates computing rewards and checking cycles in code | [paper] |
| Alshiekh et al. 2018, "Safe RL via Shielding", AAAI ([arXiv](https://arxiv.org/abs/1708.08611)) | none | Hard safety rules enforced by removing unsafe actions; the RL analogue of our hard pruning | [paper] |
| Hasanbeig et al., "Logically-Constrained RL" ([arXiv](https://arxiv.org/abs/1801.08099)) | none | Rejecting sink components in the product automaton | [paper] |
| Brafman, De Giacomo & Patrizi 2018, LTLf/LDLf non-Markovian rewards, AAAI | none | Pays a formula's reward on every step its DFA is accepting: the same repeating rule as FL-AT | [paper] |
| Prob-IRM, 2024 ([arXiv](https://arxiv.org/abs/2408.14871)) | none | Distance-based potential over RM states, with -infinity on rejecting states (we use a finite penalty instead) | [paper] |
| LARL-RM, 2024 ([arXiv](https://arxiv.org/abs/2402.07069)) | none | Another LLM-to-RM system: the LLM only gives the DFA shape; rewards are learned | [paper] |
| LTL2Action, 2021 ([arXiv](https://arxiv.org/abs/2102.06858)) | none | +1 when the formula is satisfied, -1 when falsified, then the episode ends | [paper] |
| Middleton et al. 2020, "FL-AT: A Formal Language-Automaton Transmogrifier", ICAPS demo ([PDF](https://www.cs.toronto.edu/~toryn/docs/MiddletonICAPS2020flat.pdf)) | none | The FL-AT tool itself | [paper] |
| IBM nl2ltl, Fuggitti & Chakraborti 2023 ([repo](https://github.com/IBM/nl2ltl)) | `dependencies/nl2ltl` | DECLARE templates, grounding and formulas, reused as is | [code] |
| networkx 3.6 ([docs](https://networkx.org/documentation/stable/reference/algorithms/component.html)) | installed package | The graph passes above; the algorithm references below come from its docstrings | [code], read by us |
| Tarjan 1972, "Depth-first search and linear graph algorithms", SIAM J. Computing 1(2):146-160 | none | Strongly connected components in linear time, behind `nx.condensation` | [paper], cited by networkx |
| Nuutila & Soisalon-Soininen 1994, "On finding the strongly connected components in a directed graph", Information Processing Letters 49(1):9-14 | none | The memory-saving change to Tarjan's algorithm that networkx uses | [paper], cited by networkx |
| Manber 1989, *Introduction to Algorithms: A Creative Approach*, Addison-Wesley | none | The topological sort behind `nx.topological_sort` | [book], cited by networkx |
| Bellman 1958, "On a routing problem", Quarterly of Applied Mathematics 16(1):87-90 | none | Bellman-Ford relaxation; our check keeps the largest total instead of the smallest, so a total that still grows after n rounds means a loop that pays | [paper] |

Detailed research notes with quotes live in the project's private agent memory
(`agent-memory/plans/rm-reward-research/` and `agent-memory/plans/compiler-ibm-flat/`).

**How the pieces combine:** a PDDL3-style hard/soft split (Gerevini & Long 2005) over a
Camacho et al. (2019) product Reward Machine, with per-clause monitors (De Giacomo et al. 2020)
deciding hard pruning and soft costs, and potential-based progress shaping (Ng et al. 1999). No
single paper describes this exact scheme; the combination is ours.

## Still open

- ~~Soft details per template (bonus and penalty values, where each is paid).~~ Decided
  2026-10-23: no bonus anywhere; -0.5 at a break (at every new break for `Absence`, `Precedence`,
  `ChainResponse` and `NotCoExistence` when recurrent soft rules are on); -0.5 at the finish
  for a soft clause still pending (a soft goal, or an open obligation such as `ChainResponse`'s).
  See "Recurrent soft rules".
- ~~Verify each template's RM shape against these rules, `ChainResponse` included.~~ Done in the
  T2.1 live test (27 clause sets, all eight templates, hard and soft).
- ~~Test that our runtime's guard parser accepts FL-AT's guard strings (`!door_open&has_key`, `true`).~~
  Done: the T3.5 live test ran a compiled bundle's FL-AT guards through the runtime for one episode.
- Product size: the product grows as the product of the clause DFA sizes; reductions exist
  (De Giacomo et al. 2020 transducer merge) if it becomes a problem.
