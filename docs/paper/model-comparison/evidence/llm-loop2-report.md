# LLM loop 2: stated orders and the reasoning sweep (2026-11-20)

Worktree `tp-llm-loop2` (branch `MiquelGomezCorral/tp-llm-loop2`, from main `d4e09fe`), not committed.
Evidence: `llm-loop2-evidence/` (tools, runs, rescore, re-labelled `items.json`, local-soft card copy).
Pair: deepseek-v4.1-flash generator, glm-5.3-flash critic, both at the same level, OpenCode.

## Result in short

- **Card audit:** 11 cards had `forced` orders. 8 state every order and lost `forced`; 3 keep it
  (`base-unlock-pickup`, `base-key-corridor`, G12). 16 `also_ok` answers that drop a stated order left
  the repo cards, 10 more left the local soft-card copy.
- **Rescore:** B4 stays 46/46 right. Its first proposals drop from 39 to 38 right (O2's lone goal
  Existence is now wrong). m1 drops from 19/20 to 18/20 (S2 r2 has no door-to-goal order), and the
  `none` row of the model comparison drops from 42/46 to 40/46 (S3, S4).
- **Prompts:** two generator lines and two critic lines changed. At medium the full run is 46/46
  right, 0 wrong. The critic set catches 28/30 on call 1 (adjusted baseline 24/30), with 0/8 false
  alarms. The bar is met.
- **Sweep:** every level ends 46/46 right, 0 wrong. Cost and first proposals are what changes. Max
  takes 4.5x the medium wall time, gives 14 one-clause first proposals (8 at medium) and hit two
  600 s generator timeouts (G12). On a 21-item critic subset, glm flags 81% of the defects on call 1
  at low and medium and 96% at high and max.
- **Recommendation:** if the default moves, move it to `high`. The final result matches medium, the
  critic flags more defects on call 1, and the cost is +32% wall time and 2.7x critic tokens. Not
  `max`. `CONFIG.reasoning` is unchanged.

## Phase 1: card audit

Reading rule. A task states `a` before `b` when an order word sets it ("then", "and then", "first
... then", "before", "after", "after that", "finally", "finish by", "only after", "until"), when both
are steps of a list that such a word marks as a sequence ("..., unlock the door, and then pick up the
box"), or when the task names the means ("use the key to open the door", "open the door with it").
Not stated: goals joined by "and" or a list with no order word ("Acquire the key, unlock the door,
and pick up the box"), and a "Then" that follows an "if" rule sentence ("If a, you must also b. Then
c."): that "Then" orders the instructions, and the rule's events are only its condition.

| card | index | clause | stated? | change |
| --- | --- | --- | --- | --- |
| `base-doorkey` (O6) | 0, 1 | P(has_key, door_open), P(door_open, at_goal) | yes ("use the key to open", "then") | required |
| `base-unlock-pickup` | 0, 1 | P(has_door_key, door_open), P(door_open, box) | no (list with no order word) | stays `forced` (closest call) |
| `base-blocked-unlock-pickup` (O7) | 0, 1, 2 | P(ball, door), P(key, door), P(door, box) | yes ("..., unlock the door, and then pick up") | required |
| `base-key-corridor` | 0, 1 | P(key, target door), P(target door, box) | no (list with no order word) | stays `forced` |
| `cx-sequence` (O2, O3) | 0-3 | the four-step chain | yes ("and then"; p1 "First ... Then"; p2 "finish by") | required |
| `cx-goal-one-rule` (O1, W4b, U5) | 0 | P(door_open, box) | yes ("and then"; p1 "after"; p2, p3 "then") | required |
| `cx-goal-many-rules` (W5a) | 3, 4 | P(has_door_key, door_open), P(door_open, box) | yes ("open the door with the key"; "Then ... and pick up the box") | required |
| `tpl-existence-1-goal` (G1, O4) | 0 | P(has_key, at_goal) | yes (every wording: "then", "first", "after") | required |
| `tpl-response-1-goal` (G10) | 1, 2 | P(has_door_key, door_open), P(door_open, box) | yes ("open the door with it", "then", "Finally") | required |
| `tpl-precedence-1-goal` (G7, O8) | 1, 2 | P(has_door_key, door_open), P(door_open, box) | yes ("open the door with the key"; p3 "First ... then") | required |
| `tpl-responded-existence-2-goal` (G12) | 2, 3 | P(has_door_key, box), P(blocker_moved, box) | no ("Then" after an "if" rule) | stays `forced` (judgment call) |
| local soft S1-S4 (evidence copy) | S1 1; S2 0, 2; S3 1; S4 0, 2 | the soft-last chains | yes ("then", "after that") | required |

Paraphrase that disagrees with its main task: `cx-sequence` p3 ("Find the key, take it, open the
locked door, walk into the room behind it, and pick up the ball") has no order word. It is scored
against the same card; I did not guess a different answer for it.

### `also_ok` answers removed (they drop a stated order)

- `cx-sequence`: one Existence per step.
- `cx-goal-one-rule`: Existence(door_open), Existence(box), soft Absence(key_lost).
- `cx-goal-many-rules`: all four remaining answers (none has P(has_door_key, door_open)).
- `tpl-existence-1-goal`: Existence(has_key), Existence(at_goal) (form A).
- `tpl-existence-two-1-goal`, `-2-goal`: Existence(box) alone.
- `tpl-response-1-goal`, `tpl-precedence-1-goal`: both answers each.
- `tpl-precedence-1-nogoal`: RespondedExistence(at_exit, switch_toggled).
- `tpl-precedence-4-goal` (O5): RespondedExistence + Existence(at_exit), and Existence(switch) +
  Existence(at_exit). These two and the one above match the Precedence only because the run ends at
  the exit, a level fact. Judgment call: the S2 note had accepted them on that ground.
- Local soft copy: S1 and S3 one answer each, S2 and S4 four each. Each keeps the one answer with the
  same chain and hard orders.

Kept: the Response chains of `base-doorkey`, `cx-goal-one-rule` and the pilot and smoke copies. They
state the order as "after a, b".

### Listed for the root, not changed

- **Answers that drop a stated non-order clause:** G12 `also_ok` 0 and 1 and
  `tpl-responded-existence-1-goal`, `-3-goal` `also_ok` 0 drop the stated RespondedExistence;
  `tpl-existence-2-goal`, `-3-goal` `also_ok` 0 drop the stated door or room step;
  `tpl-existence-two-3-goal` `also_ok` 0 drops the count and the door.
- **Expect without a stated clause:** `tpl-existence-two-1/2-goal` (no key-before-box order after
  "then"; a single Precedence would not carry the count either), `tpl-existence-two-3-goal` (no
  door), `base-key-corridor` ("find and acquire the key" has no clause).
- **`also_ok` answers that add an order the task does not state:** P(door_open, box) on
  `tpl-existence-2-goal`, the door-to-goal Precedence on `tpl-response-2/3-goal`,
  `tpl-responded-existence-1/3-goal` and `tpl-existence-two-3-goal`, P(has_door_key, box) on G12.
  The user rule says such an order is never added; the cards still accept it.
- **"Until" bans:** `tpl-precedence-2/3-goal` and `-2-nogoal` accept Absence or NotCoExistence for
  "do not drop the key until the door is open". Stronger than the task on runs it never needs (S2
  rule); kept.
- **`base-unlock-pickup` against its copies:** the base card keeps `forced`, the pilot and smoke
  copies require both orders. Same task text, two scorings.
- **Stale docstring:** `app/src/benchmark/rm_facts.py:127` (`clause_status`) still says "the compiler
  policy drops orders the world guarantees".
- **Stored FARM bundles:** not rescored. A bundle generated before the audit that stores only the goal
  Existence for a stated order now shows `clause_check: mismatch`.

### Scorer check and rescore

- `chain_score.forced_closure` now builds its optional transitive Precedences from every hard
  Precedence of `expect`, not only forced ones (key before goal when key before door before goal
  accepts the same runs). Without that change, an implied pair that was allowed before the audit
  would now score wrong. No run in this loop needed it.
- `CHAIN_EXTRAS` is unchanged (optional extras only; its `tpl-response-1-goal` entry still names the
  old KeyCorridor events and never matches).
- Rescore, old cards and tools against new (`rescore/old-cards.txt`, `rescore/new-cards.txt`,
  `rescore/verdicts-*.txt`):

| arm | right old -> new | first right old -> new | catch@1 | false alarms | runs that changed |
| --- | --- | --- | --- | --- | --- |
| B4 (medium, 46) | 46 -> 46 | 39 -> 38 | 7/7 -> 8/8 | 2/48 -> 1/47 | O2 first proposal Existence(box) alone: R -> W |
| m1 (medium, 20) | 19 -> 18 | 15 -> 15 | 4/5 | 1/20 -> 1/19 | S2 r2 final: R -> W (no P(door_open, at_goal)) |
| none (r1/A, 46) | 42 -> 40 | 40 -> 37 | 3/6 -> 4/9 | 4/46 -> 3/43 | S3, S4 final R -> W; O7 first R -> W |

### Critic set re-labelled (`llm-loop2-evidence/items.json`)

Old defect ids kept, the missing stated-order Precedence appended as a `missing` add defect:

- w03 (G10): + P(has_door_key, door_open).
- w08, s02 (W5a): + P(has_door_key, door_open) and P(door_open, box).
- s03 (O3): + P(key_found, has_matching_key).
- r05 (G10) and r10 (O3): right -> wrong, + the same Precedences as above.

Wrong items 28 -> 30, right 10 -> 8. The last glm-at-medium run under the new labels: 24/30 caught on
call 1 (r05 and r10 were its two false alarms; both asked for the stated order), 0/8 false alarms.
That is the bar.

## Phase 2: prompts at medium

Gaps found (B4, m1 and the rescore):

- **Chain left out, only the goal Existence** (O2, O5 first proposals): the critic caught both.
- **Order into a soft last step left out** (S2 m1 r2; S3, S4 at none): the critic accepted it.
- **Existence of the earlier step in place of its Precedence** (W5a m1 r2: hard Existence(door_open),
  no P(door_open, box)): the critic accepted it and called it "no redundant or added clauses".

Edits (diff below), each a change to an existing line:

- Generator, chain rule: a soft last step keeps `Precedence(b, c)`. Before, the line said only that
  `b` becomes lone.
- Generator, last check: also check that every consecutive pair of a stated order has its Precedence.
- Critic checklist 6: "prerequisites that the environment already guarantees" now ends "and the task
  does not state", the generator's wording, so it no longer reads as "drop forced orders".
- Critic checklist 8: a stated order needs its Precedence; a set that leaves it out, or puts an
  Existence of the earlier step in its place, drops the order: reject and name it.
- `declare-templates.md` unchanged.

Full diff: `llm-loop2-evidence/prompt.diff` (cards: `llm-loop2-evidence/cards.diff`).

```diff
# reward-ltlf-creator.system.md
-  step is only preferred ("then preferably `c`"), `Existence(c)` is soft and forces nothing:
-  the last hard step `b` is then lone and gets a hard `Existence(b)`.
+  step is only preferred ("then preferably `c`"), `Existence(c)` is soft and forces nothing,
+  but `Precedence(b, c)` stays: the last hard step `b` is then lone and gets a hard `Existence(b)`.
...
-  hard `Existence`.
+  hard `Existence` and every consecutive pair of a stated order has its `Precedence`.

# reward-machine-critic.system.md
-6. Compactness: Do not require explicit clauses for prerequisites that the
-   environment's event definitions already guarantee. Those same facts never justify a
+6. Compactness: Do not require explicit clauses for prerequisites that the
+   environment's event definitions already guarantee and the task does not state. Those
+   same facts never justify a clause the task did not state, ...
...
-   generator can act on it. An order the task states stays even when the environment
-   already guarantees it: "`door_open` cannot become true before `has_key`" does not make
+   generator can act on it. An order the task states needs its `Precedence` even when the
+   environment already guarantees it. A set that leaves it out, or puts an `Existence` of the
+   earlier step in its place, drops the order: reject and name the missing `Precedence`.
+   "`door_open` cannot become true before `has_key`" does not make
```

Cases tested at medium (round p1, 2 runs each, at most 2 cases per group): S2, S3 (soft last step),
W5a (Existence in place of Precedence), O2, O5 (lone goal), G2, G12 (guards: no unstated order).

| case | before (B4 + m1, new cards) | after (p1 x2 + full run) | note |
| --- | --- | --- | --- |
| S2 | 2/3 | 3/3 (first wrong 2/3) | both short first proposals caught; one false alarm on a right first proposal (p1 r1) |
| S3 | 1/1 | 3/3 | |
| W5a | 2/3 | 3/3 (first wrong 3/3) | p1: Existence(door_open) in place of P(door_open, box) twice, full run: a lone goal Existence; the critic rejected all three (in p1 naming the stated order) |
| O2 | 1/1 (first wrong 1/1) | 3/3 (first wrong 1/3) | |
| O5 | 3/3 (first wrong 2/3) | 3/3 (first wrong 2/3) | |
| G2, G12 | 6/6 | 6/6 | G2 adds no order; G12 adds P(has_door_key, box) in 2/3 (the card accepts it, see below) |

Full run at medium (46 cases) and the critic set:

| | right | accepted | wrong | first right | catch@1 | false alarms | critic calls/run |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B4 (old prompts, new cards) | 46 | 0 | 0 | 38/46 | 8/8 | 1/47 | 1.20 |
| medium, new prompts | 46 | 0 | 0 | 38/46 | 8/8 | 2/48 | 1.24 |

| critic set, glm medium | caught on call 1 | false alarms | accepted with a defect left |
| --- | --- | --- | --- |
| last loop, new labels | 24/30 | 0/8 | 6 |
| this loop | 28/30 | 0/8 | 4 |

New catches on call 1: w01, w02, w10, w22. Still missed on call 1: w04 (O8 wrong event in a
Precedence) and w05 (U4 wrong event). One run per item swings a few items (workflow note), so +4 is a
gain, not a precise number.

New false alarms in the pipeline: G12 (medium) and G9 (high). The critic now reads "If ..., you must
also take the key. Then pick up the box" as a stated order and asks for P(has_door_key, box). The
cards accept that answer too (`forced`), so the cost is one extra round, not a wrong machine. It does
add an order the audit reads as not stated; the "if" rule reading is my judgment call, so the user may
want the critic told that a "Then" after an "if" rule orders instructions only. G11's false alarm asks
for an Existence(door_open) on a rule card and is not about orders. B4's one false alarm was W5b.

## Phase 3: reasoning sweep

Same prompts and cards, generator and critic at the same level, 46 cases once each (`runs/f-<level>/A`,
table in `runs/sweep-table.md`). The medium row is the phase-2 full run.

| level | right | accepted | wrong | first right | catch@1 | false alarms | critic calls/run | short first | wall s per run, median (total) | gen output tokens med / max | gen reasoning med / max | critic output med / max | critic reasoning med / max | call errors (timeouts) | resends, refusals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low | 46 | 0 | 0 | 37/46 | 9/9 | 0/46 | 1.20 | 7 | 27 (1431) | 1081 / 9343 | 991 / 9061 | 183 / 846 | 108 / 691 | 0 | 0 |
| medium | 46 | 0 | 0 | 38/46 | 8/8 | 2/48 | 1.24 | 8 | 34 (1928) | 2154 / 8220 | 2015 / 8054 | 177 / 881 | 88 / 773 | 0 | 0 |
| high | 46 | 0 | 0 | 37/46 | 9/9 | 1/47 | 1.22 | 8 | 48 (2553) | 2404 / 7705 | 2266 / 7498 | 470 / 4318 | 333 / 4096 | 0 | 0 |
| max | 46 | 0 | 0 | 30/46 | 16/16 | 0/46 | 1.35 | 14 | 166 (8664) | 4960 / 31662 | 4800 / 31339 | 3650 / 4317 | 3539 / 4096 | 2 (2) | 0 |

- **Short first proposals are one clause.** 36 of the 37 short first proposals across the four
  levels hold a single clause (W4b at high had 2). The critic caught every one. At max they nearly
  double (14), which is most of max's drop in first right.
- **Max timeouts:** G12's first generator call timed out twice at the SDK's 600 s limit, and the third
  try returned after about 315 s; the run took 1515 s. `PROVIDER_RETRIES` is 10, so one case at max
  can in the worst case hold a slot for 100 minutes. No other level had a call error.
- **Per call:** generator median 17 / 23 / 33 / 72 s (low / medium / high / max), critic median
  3 / 3 / 7 / 43 s. The critic's reasoning tops out at 4096 tokens at high and max (median 3539 at
  max), which looks like a provider cap; I did not check it.
- **False alarms:** medium G11 and G12, high G9. G9 and G12 are the "if/whenever rule. Then goal"
  shape (above); the cards accept the added order. No false alarm sank a run.
- **Unstated order in final machines:** P(has_door_key, box) on G12 at low, medium and max (and p1 r2),
  P(door_open, at_goal) on G9 at low and high. Before this loop: B4 G12 had it, m1 and `none` did not.
  The G12 card accepts it through `forced`, G9 through its `also_ok`.

Critic set per level, glm-5.3-flash. Budget left room only for a fixed random subset of 21 items
(16 wrong, 5 right, seed 20261120, `llm-loop2-evidence/critic-subset.txt`); the medium row is the
phase-2 full run restricted to the same items.

| level | caught on call 1 | defects flagged on call 1 | flagged in the run | accepted with a defect left | false alarms | critic calls | judge calls | wall s median | critic output tokens (reasoning) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low | 15/16 | 22/27 (81%) | 25/27 | 1 (w05; s02 hit the call limit) | 1/5 (r09) | 40 | 20 | 14 | 18,277 (12,795) |
| medium | 15/16 | 22/27 (81%) | 25/27 | 2 (w05, w12) | 0/5 | 40 | 19 | 13 | 18,599 (13,570) |
| high | 15/16 | 26/27 (96%) | 26/27 | 1 (w02) | 0/5 | 36 | 15 | 27 | 50,631 (44,591) |
| max | 16/16 | 26/27 (96%) | 27/27 | 0 | 0/5 | 38 | 17 | 102 | 143,240 (136,457) |

One run per item and level, so one item either way is noise; the 81% to 96% step on defects flagged
(4 defects) is the one difference that repeats at two levels.

Not run: the `none` level (pipeline and critic set) and the full 38-item critic set at low, high and
max. Both were dropped for budget, `none` first as the packet orders.

## Wrong machines left

None. Phase 2 (p1 14 runs, full medium 46) and phase 3 (low, high, max, 46 each) end with 0 wrong and
0 accepted machines.

The rescore turned four stored machines wrong. They are older runs, kept here for the record. Copies of
the records and their RM text are in `llm-loop2-evidence/rescore/wrong/`.

- **m1 S2 r2** (medium, before this loop). NL: "Pick up the key, then open the door, and then,
  ideally, walk onto the goal." Set: Existence(at_goal)~s, Existence(door_open),
  P(has_key, door_open); missing P(door_open, at_goal). LTLf: `(Fdoor_open)`,
  `(((~door_open)Uhas_key)|(G(~door_open)))`, `(Fat_goal)` (soft). RM:
  `rescore/wrong/m1/S2-r2.rm`.
- **m1 W5a r2** (medium, wrong under the old cards too). NL: "Move the ball away from the door before
  you take the key. Try not to drop the key while the door is still closed. Whenever you are holding
  the key, try to have the door open at that moment or open it afterwards. Then open the door with
  the key and pick up the box in the other room." Set: Existence(door_open) in place of
  P(door_open, box). LTLf: `(((~has_door_key)Ublocker_moved)|(G(~has_door_key)))`,
  `(((~door_open)Uhas_door_key)|(G(~door_open)))`, `(Fdoor_open)`, `(Ftarget_picked_up)`,
  `(~(Fkey_lost))` (soft), `(G(has_door_key->(Fdoor_open)))` (soft). RM: `rescore/wrong/m1/W5a-r2.rm`.
- **none S3 r1** (model comparison, reasoning `none`). NL: "Open the door, then, if possible, pick up
  the box in the other room." Set: Existence(door_open), Existence(box)~s; missing
  P(door_open, box). LTLf: `(Fdoor_open)`, `(Ftarget_picked_up)` (soft). RM:
  `rescore/wrong/none/S3-r1.rm`.
- **none S4 r1**. NL: "Take the key, then open the door. After that, try to pick up the box in the
  other room." Set: Existence(door_open), Existence(box)~s, P(has_door_key, door_open); missing
  P(door_open, box). LTLf: `(Fdoor_open)`, `(((~door_open)Uhas_door_key)|(G(~door_open)))`,
  `(Ftarget_picked_up)` (soft). RM: `rescore/wrong/none/S4-r1.rm`.

## Default level

The final machine does not depend on the level: 46/46 at all four. The level buys critic recall and
costs time.

- **high (my pick if the default moves).** Same final result as medium, and 96% of defects flagged on
  the critic's first call against 81%. Cost: wall per run 48 s against 34 s (+40% median, +32% total:
  2553 s against 1928 s per 46 cases), critic tokens about 2.7x, generator tokens about 1.1x. No
  timeouts.
- **medium (current default).** Keeping it is defensible: the same pipeline result as high, a
  quarter less wall time; its two false alarms cost one extra round each (2/48).
- **max: no.** 4.5x the medium wall time (8664 s), first right drops to 30/46 (14 one-clause first
  proposals), two 600 s timeouts, generator calls up to 31,662 output tokens. Its one extra critic
  catch on the subset is within noise.
- **low.** As good as medium on this run (46/46, 37/46 first right) and fastest (1431 s), but it had
  the only critic-set false alarm and the only max-calls item. Not a candidate given the user's lean.

## Budget

299 runs and 774 calls (690 + 84 judge) of 320 / 900, under the 300 / 880 guard, which never fired.

| part | runs | calls (+ judge) |
| --- | --- | --- |
| p1 (shrinking round, 7 cases x 2) | 14 | 44 |
| full medium | 46 | 114 |
| critic set, medium, all 38 | 38 | 70 + 32 |
| full low, high, max | 138 | 348 |
| critic subset at low, high, max | 63 | 114 + 52 |

## Paper candidates

Named here; nothing copied to `docs/paper/`. Asking the root before any copy.

- **Stated-order audit, before and after.** Card table, rescore (B4 first right 39 to 38, m1 19 to
  18, `none` 42 to 40) and the medium full run 46/46 with the critic set 24 to 28 of 30 caught on
  call 1. Evidence: this report, `rescore/`, `runs/f-medium/A`, `runs/critic/glm-medium`.
- **Reasoning sweep table** (the 46-case table and the critic subset table above). It is the number
  for "how much thinking does the pair need": none of it changes the final machine, max costs 4.5x and
  times out. Evidence: `runs/f-*/A`, `runs/critic/glm-*`, `runs/sweep-table.md`, `tools/level_stats.py`.

## Files changed (worktree)

- `app/src/prompts/compiler-rm/reward-ltlf-creator.system.md`, `reward-machine-critic.system.md`
- `experiments/benchmark/{base,complex,templates}/tasks.json` and their `README.md`
- `pre-commit run --files` on all eight: passed. `unittest tests.test_prompts tests.test_critic_clues`:
  8 passed. All five card suites load (card checks pass).

Evidence-only tools (not repo): `tools/chain_score.py` (closure over every hard Precedence),
`tools/verdicts.py`, `tools/level_stats.py` (new), the re-labelled `items.json` (old one kept as
`items-old.json`), the local soft-card copy.

## Notes

- **Decision records: no change.** Main `9ead827` already records both user rules (stated orders kept,
  only a hard Existence is redundant). This loop applies them to cards and prompts.
- **Process slip:** one edit of `complex/tasks.json` (the `cx-goal-many-rules` block) used a Python
  heredoc, which the packet forbids for repo files. The result was checked (JSON loads, card checks
  pass, diff is only that block); later edits used the edit tool.
- **Gaps:** one run per case and level; the critic sweep used a 21-item subset; `none` not run;
  stored FARM bundles not rescored; the "if rule. Then" reading (G9, G12) is my call and the prompts
  do not settle it.
