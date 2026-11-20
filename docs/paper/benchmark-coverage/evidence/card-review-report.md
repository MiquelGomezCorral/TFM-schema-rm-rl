# Card review, baseline pass (Opus 5.5, 2026-11-20)

Copied by the root from the reviewer's text return (the harness refused the reviewer's own write of this file).
`groups.json` beside it was written by the reviewer: 9 groups covering the 53 trained cards, plus the ablation.

All 111 cards reviewed; the final run is not ready to freeze yet.

What was run (no model calls, no training):
- Plan traces: the scripted plans of every suite were rerun. All 660 behave as their cards say.
- Answer sweep: all 165 accepted answers compiled with main's code, pay order checked, every plan trace paid step by
  step, an idle plan judged on each card's seeds. 0 errors.
- Loop 2 comparison: its uncommitted card edits in `tp-llm-loop2` compared where they touch the same fields.

## Verdict counts

| Verdict | All 111 | Trained 53 |
|---|---|---|
| OK | 46 | 24 |
| OK, generation only (covered by a trained card) | 14 | 0 |
| Only the pay-order flag, class A (F3) | 18 | 3 |
| Soft rule not judged, next to a hard goal (F4) | 10 | 10 |
| Card issue | 23 | 16 |

Clean:
- No wrong plan earns as much as the solve plan on any answer. Idle beats or ties solve only on the idle-passable cards.
- No trap answer is left on main except `cx-rules-only`. Every `cx-goal-many-rules` answer now has `Existence(has_door_key)`.
- The Lanes ceiling works: on `lanes-rules`, solve pays -2 to -4 and idle -96 to -97.
- Every forcing world fires before the agent can leave. The siren starts at step 1-4 and the carried box falls at step
  2-8, but the earliest exit is 11 actions away. KeyGift and Shop have quiet ends.

## Fixes, ranked

1. Seeds: every final `runs.yaml` has `seeds: [1]`; rule 6 needs [1, 2, 3]. Card-only.
2. Idle-passable cards still train (rule 1). Set `train: false`; each is covered by another card. Card-only.
   - `cx-rules-only`: replaced by Lanes (decision C3) but still trained and listed in `closed-set.json:11,24`.
   - `tpl-absence-1-nogoal`: covered by `lanes-guard`.
   - `tpl-response-1-nogoal`: covered by `keygift-hard` and the forced copy.
   - `tpl-responded-existence-1-nogoal`: replace with `tpl-responded-existence-2-nogoal` (siren room, idle fails on seeds 1-3).
3. The pay-order check will block 7 trained answers. It fails "started must pay more than not started" on 25 answers.
   - Trained: `cx-siren`, `tpl-not-co-existence-1-goal`, `tpl-responded-existence-1-goal`, the three soft goal cards
     for Precedence, RespondedExistence and NotCoExistence, and `tpl-absence-1-goal` also_ok#0.
   - All class A: the user ruled these machines fine and postponed the check change (`plan.md:65`). The mandatory
     pre-training gate (`plan.md:57`) will still refuse them.
   - User decision: land the drafted check change, or write a class-A exemption for the gate.
4. The soft rule next to a goal is never judged. On the 8 `tpl-*-soft-1-goal` cards, `cx-goal-one-rule` and
   `cx-goal-many-rules`, success means the goal only; soft breaks are just a column. Only soft-only cards have a pass
   rule (`app/scripts/test_rl.py:139-151`). Test design plus user decision: for example, goal reached and fewer soft
   breaks than the breaking plan or the no-RM arm.
5. Unsolved level. KeyCorridorS6R3 learned 0 of 71 runs (`workflow.md:596,604`). It holds `base-key-corridor`,
   `cx-sequence` and `tpl-responded-existence-1-goal`. For the RespondedExistence card, a hard copy of
   `tpl-responded-existence-soft-1-goal` on the siren room fits. The base and sequence cards need a smaller
   KeyCorridor checked for learnability. User decision on the level.
6. Shop final settings are untested. `reward_promise_cost` is off by default (`app/src/config/config.py:273`), yet the
   shop learned only with promise cost or end judgment on. The final run uses the embedding default (`config.py:339`);
   every shop result so far is one-hot. No learning result for levels 3-5.
7. Forced-start mismatch. `tpl-responded-existence-1-nogoal-forced` trains, but the record says only the Response copy
   trains (`thesis-benchmark.md:156-157`). User decision: `train: false` or update the record.
8. Accepted answers that drop a stated "if" rule or template (record `task-and-rm-identity.md:353-356`). Card-only.
   `tpl-existence-two-3-goal` ok0; `tpl-responded-existence-1-goal`, `-2-goal`, `-3-goal` ok0 (loop 2 keeps `-2-goal` ok0).
9. A stated "then" has no order clause in `tpl-existence-two-1-goal` and `-2-goal`. Precedence can only say "held once
   before", so rewording "then" to "and" is the simple fix. Card-only.
10. Weak trained tests (the level or goal forces the rule, so any goal-reaching policy passes).
    `tpl-existence-two-1-goal`: move it to a hard copy of the ServiceRoom box card. `tpl-response-1-goal` and
    `tpl-existence-1-goal`: keep (hard Response with a goal is tested for real by `cx-siren` and `cx-box`).
11. Soft Absence is counted once per episode, so halving the breaches shows no gain (`tpl-absence-soft-1-nogoal`, the
    soft rules of `lanes-rules`). Count breach steps instead. Test design.
12. Optional: hard no-goal Precedence and NotCoExistence cards on Lanes, as hard copies of the soft no-goal cards. Today
    the goal companions cover them (decision C2). User decision.
13. Stale notes (card-only): `forcing/README.md:29-31` and `:62-72` (the "ending early beats guarding" section is false
    under the ceiling); `complex/README.md:4,9` lists `cx-rules-only` as trained; `complex/ablation.json:9-10` quotes
    the old -1 and -0.5 pays; the `tpl-response-3-nogoal` note at `templates/tasks.json:1105` names the old goal card;
    `closed-set.json` lists `cx-rules-only`.
14. Bundles are stale; regenerate at the freeze. The soft and forcing cards have no ARM-FM bundle, yet
    `templates/runs.yaml` runs ARM-FM on all 28 trained cards. User decision: should ARM-FM skip the soft cards?

Open question carried from loop 2: does "Then ..." after an "if" rule state an order? Affects `tpl-response-2/3-goal`
and `tpl-responded-existence-1/2/3-goal`.

Loop 2 and rule 2: agrees with every also_ok answer loop 2 removes. Disagrees where it keeps an answer without the
stated order: `base-doorkey` ok0 (a Response pair, also in pilot and smoke), `cx-goal-one-rule` ok0,
`tpl-responded-existence-2-goal` ok0. Leaving the orders optional on `base-unlock-pickup` and `base-key-corridor` fits
rule 2: their tasks state no explicit "then".

## Coverage matrix (trained cards)

Result tests: hard cards, every hard clause holds; soft-only cards, compared against an idle agent; soft rule plus
goal, goal only (fix 4); shop, clients served, at least 7.5 per episode.

| Template | Hard, goal | Hard, no goal | Soft, goal | Soft, no goal |
|---|---|---|---|---|
| Existence | `tpl-existence-1-goal`: OK | `tpl-existence-1-nogoal`: OK | soft not judged | OK |
| ExistenceTwo | weak, level forces it | OK | soft not judged | Lanes: OK |
| Absence | `tpl-absence-1-goal`: OK | `lanes-guard`: OK | soft not judged | Lanes: counted once per episode |
| Response | `cx-siren`, `cx-box`: OK | KeyGift, Shop: OK | soft not judged | `keygift-soft`: OK |
| Precedence | `-1-goal`, `-4-goal`: OK | gap | soft not judged | Lanes: OK |
| ChainResponse | carry box: OK | carry box: OK | soft not judged | carry box: OK |
| RespondedExistence | gap (unsolved level, weak) | gap (only the forced start) | soft not judged | siren: OK |
| NotCoExistence | `-1-goal`: OK | gap | soft not judged | Lanes: OK |

Of 32 cells, 15 are tested well. Eight soft-goal cells have no soft test, 4 hard cells are gaps, 2 are weak.

## Final run

| Suite | Arms | Cards | Steps |
|---|---|---|---|
| base, complex, templates, box-carry, forced-start | no-RM, ARM-FM, FARM | every trained card (4, 6, 28, 3, 2) | 1.5M |
| forcing | no-RM, FARM | 4 | 1.5M |
| shop | FARM on RM reward, FARM on RM plus shop reward, no-RM | level 1 `shop-siren`; levels 2-5 `shop-serve`, `-full`, `-quiet-first`, `-boil`; no-RM all 6 | 1.5M level 1, 5M otherwise |
| ablation | FARM, 6 variants | `lanes-rules`, `cx-goal-one-rule`, `cx-goal-many-rules` | 1.5M |

Every row runs seed 1 only. Pilot and smoke are not final. Breaks the rules: seeds (1), idle-passable cards (2), the
unsolved level (5), forced-start (7), ARM-FM on soft cards (14); the regression set of FARM-solved tasks is written
nowhere in the repository. Not in the final run: 49 template cards and 4 box-carry cards are generation-only (fine);
`tpl-responded-existence-2-nogoal` should train; `cx-rules-only` trains but should not.

## Per-card issues

Cards with a defect, plus the loop-2 cards where the reviewer disagrees on rule 2. The line is the card's `"id"` line
in its suite's `tasks.json` on main `d4e09fe`.

| Card | Train | Issue |
|---|---|---|
| `base-doorkey`:6 | yes | OK; ok0 drops the stated "then" (loop 2 keeps it) |
| `base-key-corridor`:163 | yes | unsolved level (5) |
| `cx-sequence`:6 | yes | unsolved level (5) |
| `cx-rules-only`:72 | yes | idle-passable, replaced, trap shape (2) |
| `cx-goal-one-rule`:147 | yes | soft rule not judged (4); ok0 drops the stated "then" |
| `cx-goal-many-rules`:233 | yes | soft rules not judged (4) |
| `cx-siren`:351 | yes | pay-order flag only (3) |
| forced-start `tpl-responded-existence-1-nogoal-forced`:102 | yes | trains against the record (7) |
| `lanes-guard`:6 | yes | stale README (13) |
| `lanes-rules`:56 | yes | stale notes (13), soft rules not judged (4), counted once (11) |
| `shop-serve`:86, `shop-full`:210, `shop-quiet-first`:338, `shop-boil`:489 | yes | untested under final settings (6) |
| `tpl-existence-2-goal`:104, `-3-goal`:187 | no | ok0 drops a stated step and ok1 adds an unstated order |
| `tpl-existence-two-1-goal`:273 | yes | "then" missing (9), weak (10) |
| `tpl-existence-two-2-goal`:366 | no | "then" missing (9) |
| `tpl-existence-two-3-goal`:454 | no | ok0 drops the template (8) |
| `tpl-absence-1-nogoal`:612 | yes | idle-passable, unsolved level (2) |
| `tpl-response-1-nogoal`:899 | yes | idle-passable (2) |
| `tpl-response-3-nogoal`:1075 | no | stale note at :1105 (13) |
| `tpl-responded-existence-1-goal`:1716 | yes | unsolved level (5), weak, ok0 drops the "if" rule (8), pay-order flag |
| `tpl-responded-existence-1-nogoal`:1779 | yes | idle-passable (2) |
| `tpl-responded-existence-2-goal`:1816 | no | ok0 drops the "if" rule (8) |
| `tpl-responded-existence-3-goal`:1913 | no | ok0 drops the "if" rule (8), pay-order flag |
| `tpl-absence-soft-1-nogoal`:2724 | yes | counted once per episode (11) |
| the 8 `tpl-*-soft-1-goal` cards | yes | soft rule not judged (4); 3 also have the pay-order flag |

Pay-order flag only (Gate): trained `tpl-absence-1-goal` and `tpl-not-co-existence-1-goal`; generation-only
`tpl-absence-2/3-goal`, `tpl-response-2/3-goal`, `tpl-precedence-2/3-goal`, `tpl-not-co-existence-2/3-goal`, the soft
Precedence, RespondedExistence and NotCoExistence `-2/-3-goal` cards, and `smoke-doorkey-response`.

Scratch: `scratch/review_sweep.py`, `scratch/show.py`, `scratch/sweep.jsonl`, `scratch/sweep-idle.json`,
`scratch/dump.txt`, `scratch/tb/`.
