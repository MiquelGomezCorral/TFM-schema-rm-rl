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
   templates and grounding. Its formulas are used for every pattern, unchanged.
3. **FL-AT fork** compiles each formula to a DFA with MONA and builds the synchronous product
   of all clause DFAs. One small addition: it also returns, for each product state, the tuple
   of per-clause DFA states (`sdict`).
4. **Our cleanup layer** turns that product into the final Reward Machine: hard pruning,
   minimization, and rewards.

Out of scope for this redesign: labeling functions, RM state descriptions and embeddings, and
the RM text format. Other pipeline steps own them.

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

### Current compiler

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
- **[code] Rewards today:** 0.1 once when a clause completes, +1.0 when the task completes.
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
  shaping + task completion +1 + soft bonuses and penalties. The clause 0.1 and the progress
  term reward the same thing.
- **[decision] Progress formula:** every edge adds `Phi(next) - Phi(current)`, with
  `Phi(u) = -k * (longest remaining steps from u to a final state)`, `k = 0.1`, and `Phi = 0` at
  final states. Moving forward pays, staying pays 0, going back costs the same amount, and any
  cycle sums to exactly 0, so loops cannot be farmed. Source: Ng, Harada & Russell 1999. With the
  learner's discount in the formula (`gamma * Phi(next) - Phi(current)`), self-loops pay a tiny
  `(1 - gamma)` amount instead of 0; both forms are policy-safe.
- **[decision] Longest path, not shortest,** for the shortcut reason above, and because the
  environment may never produce the shortcut. For RMs with cycles, compute it on the graph with
  each cycle collapsed to one node; edges inside a cycle get 0.
- **[decision] No infinities.** Wells get no progress score, only a fixed finite penalty
  (Ng's theorem also needs a bounded score). Some papers use -infinity for rejecting states; we
  do not need it.

### Hard and soft

- **[decision] Hard/soft is set per clause, independently,** by our prompt's output. The tag
  never changes the LTLf formula or the DFA. Soft only changes rewards; hard changes rewards
  and the RM's structure.
- **[decision] Soft is what FL-AT's product gives for free.** The agent may finish in a bad
  state but pays a penalty; preferred behavior gets a bonus. Preferences get both a bonus and a
  penalty, to push harder. An irreversible soft rule ("if possible never touch lava") keeps the
  clean and the touched section; entering the touched section pays one penalty.
- **[decision] Hard means the agent cannot finish in a bad state.** A permanent violation goes
  to one shared well (penalty, episode ends). A fixable one, such as a pending `Response`, only
  blocks finishing until it is fixed; it never ends the episode early.
- **[decision] Soft clauses never affect the final condition.** If the agent touches lava under
  a soft rule, it still has to open the door to finish. Final = every hard goal clause done and
  every hard rule clause satisfied. Soft clauses only change the reward on the finishing edge
  (bonus if satisfied, penalty if not) or on the edge where they break.
- **[decision] No end-of-episode check.** Reaching a final state ends the episode, so the rule is
  judged on that last edge. A task that never reaches final ends by the environment's time
  limit, and it has already missed the completion reward, so nothing more is added.
- **[decision] States are classified per clause, from each clause's own DFA** (through `sdict`),
  not from the merged RM's "can still reach the goal", which mixes hard and soft violations.
- **[decision] Regressions exist only if the task or environment states them.** "Drop the key"
  matters only when a proposition such as `key_lost` exists and a clause uses it. A plain
  `Existence(has_key)` (`F has_key`) never goes back.

### Cleanup passes, in order

1. **Label each clause's DFA states** as satisfied (accepting), pending (not accepting, accepting
   still reachable) or violated (accepting never reachable again). This is a reachability check
   on a small DFA, so it is exact, not a guess. (Matches the four-valued monitors of De Giacomo
   et al. 2020.)
2. **Redirect hard violations:** every edge whose target has a hard clause violated goes to one
   shared well instead.
3. **Remove "final" where a hard clause is not satisfied** (for example "goal done, `Response`
   pending"). The state already exists in FL-AT's product; it just stops counting as final.
4. **Send hopeless states to the well:** states from which no final state is reachable any more.
   Otherwise the agent could wander forever in a part of the RM that can never finish.
5. **Prune states unreachable from the start.** After the redirects, states that were targets can
   be left with no incoming edges.
6. **Minimization: deferred (decision 2026-10-12).** It works only with the right starting
   groups: one final group, one well group, and the other states split by which soft clauses are
   violated. **[run]** On FL-AT's RM for "reach the goal, if possible never touch lava", Moore's
   refinement (our `_equivalence_partitions`, `app/src/compiler/reward_machine.py:530`) started
   from final / not final only merges the clean and the touched sections (S1 with S2, S3 with S4):
   the mirror edge S1 -> S2 looks like "stay in my group", the same as S2's own lava self-loop.
   With the soft-violation split they stay apart. The gain (fewer states to describe and embed)
   is small next to that risk, so the first version skips it; FL-AT's product is kept as is
   after pruning.
7. **Compute rewards** on the pruned RM: progress, task completion, soft bonuses and penalties.

After passes 4 and 5, check that a final state is still reachable; if not, report the task as
having conflicting clauses.

### Episodes, rewards and critics

- **[code] Today the RM never ends an episode.** The RL wrapper takes `terminated` only from the
  environment and returns environment reward + RM reward
  (`app/src/arm_fm/runtime.py:177-202`).
- **[decision] The episode ends in any of these cases:** the environment terminates, the RM
  reaches a final state, the RM reaches the well, or the time limit / step limit is hit. Hitting
  the time limit penalizes the agent.
- **[decision] Reward source is a flag:** RM only, environment only (no RM), or both.
- **[decision] One critic, at the end.** There is one non-deterministic step (the LLM's clauses),
  so there is one thing to critique. The critic gets the task, the generator's clause output and
  the compiled RM, with the generator's guidelines plus critique guidelines. It replaces today's
  task critic and RM critic.
- **[decision] Rule-only tasks are allowed.** A task with no hard goal clause gets no final state;
  only the time limit ends it. The critic accepts it, and the UI and CLI warn the user.
  Preference-only tasks are worth exploring later.

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

Detailed research notes with quotes live in the project's private agent memory
(`agent-memory/plans/rm-reward-research/` and `agent-memory/plans/compiler-ibm-flat/`).

**How the pieces combine:** a PDDL3-style hard/soft split (Gerevini & Long 2005) over a
Camacho et al. (2019) product Reward Machine, with per-clause monitors (De Giacomo et al. 2020)
deciding hard pruning and soft costs, and potential-based progress shaping (Ng et al. 1999). No
single paper describes this exact scheme; the combination is ours.

## Still open

- Soft details per template (bonus and penalty values, where each is paid).
- Verify each template's RM shape against these rules, `ChainResponse` included.
- Test that our runtime's guard parser accepts FL-AT's guard strings (`!door_open&has_key`, `true`).
- Product size: the product grows as the product of the clause DFA sizes; reductions exist
  (De Giacomo et al. 2020 transducer merge) if it becomes a problem.
