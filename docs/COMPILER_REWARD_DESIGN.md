# Compiler redesign: IBM nl2ltl, FL-AT, and the reward layer

Status: **planned, not implemented.** This records what we checked, what we decided, and why,
from the design discussion of 2026-10-12. The current compiler still works as described in
"Current compiler" below until the redesign lands.

Every claim is marked with how it was checked:

- **[run]**: we ran the code (FL-AT + MONA in `RM_RL_env`) and read the output.
- **[code]**: read in this repository's code, with `file:line`.
- **[paper]**: a research worker or we read the primary source; the PDF is in `docs/` where noted.
- **[decision]**: a choice the project owner made, with the reason.

## Planned pipeline

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
   rewards (minimization deferred).
5. **One critic** reviews the task, the clauses and the compiled RM before state descriptions.

Out of scope for this redesign: labeling functions, RM state descriptions and embeddings, and
the RM text format, except one new optional `REJECTING_STATES:` line, `FINAL_STATES:` being
allowed to be empty, and the end-judgment lines of a machine with no final state (see "The end
judgment"). Other pipeline steps own the rest.

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
  `Phi(u) = -k * (longest remaining steps from u to a final state)`, `k = 0.1`, and `Phi = 0` at
  final states. Moving forward pays, staying pays 0, going back costs the same amount, and any
  cycle sums to exactly 0, so loops cannot be farmed. Source: Ng, Harada & Russell 1999. With the
  learner's discount in the formula (`gamma * Phi(next) - Phi(current)`), self-loops pay a tiny
  `(1 - gamma)` amount instead of 0. We use the undiscounted difference while the learner uses
  `gamma = 0.99`: an accepted approximation, since a cycle can then net a small, bounded
  positive shaping `(1 - gamma) * (Phi(v) - Phi(u))`; it cannot be farmed without limit.
- **[decision] Longest path, not shortest,** for the shortcut reason above, and because the
  environment may never produce the shortcut. For RMs with cycles, compute it on the graph with
  each cycle collapsed to one node; edges inside a cycle get 0.
- **[decision] With no final state, progress aims at the states where no clause is pending.** A
  rule-only task has no final, so the target is every product state where each clause is satisfied
  (accepting) or violated, and none is waiting for something to happen. The rest of the formula is
  the same: `Phi(u) = -k * (longest remaining steps to a target)`, `Phi = 0` at a target, loops
  collapsed to one node. Targets absorb: their outgoing edges are left out when the distance is
  measured, so a rule that is satisfied again and then opens again does not push the score away
  from it. A state from which no target can be reached scores 0, and an edge into it pays no
  progress, like an edge into a well: otherwise a step into a dead end would pay for getting
  nowhere. Wells still pay no progress. A machine with a final is unchanged. The simulation, the
  numbers and the dead-end witness: [rule-only progress](paper/rule-only-progress/README.md).
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
- **[decision] No infinities.** Wells get no progress score, only a fixed finite penalty
  (Ng's theorem also needs a bounded score). Some papers use -infinity for rejecting states; we
  do not need it.

### Why no loop gains reward, and how we check it

Two things keep no loop above 0: how the rewards are built, and one check on the finished RM.

- **[code] By construction.** Progress is a difference of one score per state, so around any loop
  the differences cancel. States on the same loop share one score (the loop is collapsed to one
  node before scoring), so edges inside a loop pay 0 progress. The other rewards cannot repeat
  for gain: `+1` and the soft finish penalty are paid only on edges into the final, the `-1` only
  on edges into the well, and both are absorbing. A soft break costs -0.5 and nothing pays it
  back, so a loop through a re-armed soft rule (see "Recurrent soft rules") loses reward on
  every lap. With the switch off a broken clause stays broken (its DFA cannot leave a violated
  state), so the break is paid once. Dropping the duplicate start removes a state and its edges
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
| `nx.condensation` | collapse every loop into one node before scoring progress (`_progress`) | strongly connected components: Tarjan's algorithm with Nuutila's changes (Tarjan 1972; Nuutila & Soisalon-Soininen 1994) |
| `nx.topological_sort` | visit the collapsed graph from the finals backwards to get each state's longest remaining path | topological order (Manber 1989); the longest path itself is a short loop of ours: `steps = 0` at a final, else `1 + max(steps of the successors)` |

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
  every hard rule clause satisfied. Soft clauses only change the reward on the finishing edge
  (-0.5 for a soft clause still pending: a soft goal, or an open obligation such as
  `ChainResponse`'s) or on the edge where they break.
- **[decision] A final state judges on its last edge; with none, the end is judged where the
  environment ends the episode.** Reaching a final state ends the episode, so the rule is judged on
  that last edge. A task with no final state (rule-only) ends on the environment or the time limit,
  and the RM then charges each promise still open in its state (see "The end judgment"). This
  reverses the earlier "no end-of-episode check in the RM", which left such a run with the flat
  time-limit penalty and nothing else.
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
    is free, and the rule is armed again on the next step.
  - No state is added and no table is needed. Hard clauses, and every clause with the switch off,
    reach FL-AT unchanged. The input DFAs are not mutated.
- **[run] Shape.** Each of the four templates has a start `S1`, an idle twin `S2` with the same
  successors, and one absorbing violated state; no copied edge points back at `S1`, so the start
  merge still applies. A single soft rule keeps its RM state count.
- **[run] The supervisor's examples** (`x` and `y` are the template's `a` and `b`, `-` is a step
  with neither). With the switch on, each row charges:

  | Template | Steps | Charges |
  |---|---|---|
  | `Absence(x)` | `x x` | 1 |
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
  broken is free, and the rule is armed again on the next step. `Absence(x)` on `x x x` charges 1,
  on `x - x x` charges 2; `Precedence(x, y)` on `y y` charges 1. The accepted `ChainResponse`
  result `x x -` = 1 is one instance of this.
- **[run] Progress is re-scored.** The re-arm joins the clean and the broken state into one
  strongly connected component, so `_progress` scores the merged component and pays 0 inside it.
  The break step is therefore -0.5 plus that step's progress, which is zero inside the merged
  component. With a hard `Existence(at_goal)` and a soft `Absence(key_lost)`:

  | Case | Before | Off | On |
  |---|---|---|---|
  | Clean finish | 1.45 | 1.2 | 1.1 |
  | Break step | -0.4 | -0.4 | -0.5 |
  | Break on the finishing step | 0.7 | 0.7 | 0.6 |

  "Before" is the compiler without this change; "Off" differs from it only by the removed +0.25.
  The gap between a clean and a one-break finish stays 0.5. Against the off position a clean
  finish can lose 0.1 (`Absence`, `ChainResponse`) or 0.2 (`NotCoExistence`) of progress.
- **[run] The product can grow with several soft rules.** The re-arm adds edges between states
  that were separate, so the product of two or more rules can reach more states than before: 8 of
  the 12 pairs of the four templates grew, and all four with a goal went from 11 to 13 states.
- **[decision] Forced breaks.** Tasks are assumed free of contradictions (above), so a soft rule
  that every way of finishing must break is not checked. With n forced breaks, finishing pays
  1 - 0.5n plus progress: about a timeout's -0.5 at n = 3, and no more than the -1 well from
  n = 4-5.
- **[decision] A soft clause already violated at the start pays nothing,** as before: it is inert,
  and the compile warning names it.

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
6. **Minimization: deferred (decision 2026-10-12).** It works only with the right starting
   groups: one final group, one well group, and the other states split by which soft clauses are
   violated. **[run]** On FL-AT's RM for "reach the goal, if possible never touch lava", Moore's
   refinement (our former `_equivalence_partitions`, `app/src/compiler/reward_machine.py:530` at commit `5b74afe`) started
   from final / not final only merges the clean and the touched sections (S1 with S2, S3 with S4):
   the mirror edge S1 -> S2 looks like "stay in my group", the same as S2's own lava self-loop.
   With the soft-violation split they stay apart. The gain (fewer states to describe and embed)
   is small next to that risk, so the first version skips it; FL-AT's product is kept as is
   after pruning. A re-armed violated state keeps its violated label, so that split still holds.
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
  waiting. A soft clause that pays neither on any edge is inert and named in the warning. With a
  final state only the break and the finish count, as before. With none, the progress step is
  judged by a proxy (the clause's waiting flips on an edge that pays progress), approximate both
  ways: it can call a clause paid that changes nothing, or inert when it changes rewards.

### The end judgment

- **[decision] A machine with no final state judges an episode the environment ends.** On a step
  where the environment terminates or truncates the episode and the RM did not (no final and no
  well entered), the reward adds `hard x HARD_FAILED_REWARD + soft x SOFT_FAILED_REWARD`, with the
  counts of the RM state after that step's update (`RewardMachineEnvironment.step`). It is paid
  once, since the episode ends there, and never when the RM ended it. It replaces the flat -0.5
  time-limit penalty; `info["rm_reward"]` includes it. The user's framing: the machine "accepts" or
  "rejects" the string of propositions the environment generated, so the end judgment is the link
  between the environment and the language side of the RM.
- **[decision] The RM text carries the judgment.** The compiler writes `ACCEPTING_STATES` (the
  states where no clause is pending), the two values `HARD_FAILED_REWARD: -1` and
  `SOFT_FAILED_REWARD: -0.5`, and last `PENDING_PROMISES`, one row `uN: hard H, soft S` per state
  that is neither accepting nor the well. It computes them from the product labels after the states
  are numbered (`_end_judgment` in `reward_layer.py`), never by hand and with no clause names. A
  soft rule broken for good was paid when it broke and counts as accepted; a hard rule broken for
  good is the well, which rejects, ends the episode on its own, and is in neither list. A machine
  with a final state, and an imported author bundle, gets none of these lines and keeps its text,
  rewards, flat -0.5, bootstrap and success rule.
- **[decision] The parser stays lenient on the old format and strict on the new lines.** A text
  without the new lines parses as before. A text without the two values takes the
  `Configuration` defaults (`HARD_FAILED_REWARD`, `SOFT_FAILED_REWARD`). A state that is both
  accepting and pending, a non-final non-rejecting state in neither list, or a row for an unknown
  state is rejected. `PENDING_PROMISES` must be the last section. Serialize, parse, serialize is
  byte-identical on both public paths (the paper text and the numeric structure). The two values
  are the only part meant to be edited.
- **[decision] Success of a rule-only run.** `rm_accept` is true on the last step of an episode the
  environment ended in an accepting state, and `is_success` (`success: rm`) is true whether the
  episode terminated or was truncated (user, 2026-10-27). A machine with a final keeps its rule:
  success needs the final.
- **[decision] The trainers do not change.** PPO and DQN keep their time-limit bootstrap and receive
  the charge as part of the step reward ("keep it but add ours": user, 2026-10-27).
- **[decision] No loop gains reward.** The charge is paid once, at the end of an episode, outside
  any edge, so `_has_positive_cycle` and the cycle argument above are untouched and a loop cannot
  farm it.
- **[decision, kept] Idling with two hard promises open costs more than breaking a hard rule on the
  last step.** Two open hard promises charge -2; breaking a hard rule on that step costs the well,
  -1, since the RM then ends the episode and the end is not charged again. The plan review found
  it; it is disclosed here and not changed ([rule-only progress](paper/rule-only-progress/README.md)).

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
