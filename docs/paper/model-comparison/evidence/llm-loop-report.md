# LLM loop report (2026-11-20)

Packet: `llm-loop-packet.md`. Evidence: `llm-loop-evidence/` (tools, `runs/<round>/<arm>/`, `runs/critic/<label>/`).
Worktree E = `tp-model-compare`, merged with main `cdae068` (fast-forward). Nothing committed.

## Results first

- **Production pair at `medium`, with the G12 card fix and the critic rewording: 46/46 right** (B4). The same
  pair at `none` (last report's arm A, rescored with the fixed card) has 42/46 right, 1 accepted, 3 wrong.
  Calls per run are the same (2.39 vs 2.35); a run takes about 6 times longer (median 39 s vs 6 s).
- **Thinking fixes the generator readings the packet listed.** U5, S2 and O7 right in 3 of 3 runs at medium
  (wrong, wrong, accepted at none). W5a right in 2 of 3 at medium, 1 of 1 at high.
- **Thinking makes glm a much better critic.** Critic set: caught on call 1 14/28 at none, 22/28 at medium;
  defects left in accepted candidates 15 vs 8. It costs 3 rejected fixed candidates and 2/10 false alarms.
- **New at medium: short first proposals.** In 10 of 66 medium runs deepseek's first answer had fewer clauses
  than any card answer (often one clause), never at none (0/46). glm at medium rejected every one and the
  second answer was right. Cause unknown: the JSON is valid and the call reasoned 1.4-4.6 K tokens.
- **Arm E (luna generator, Haiku critic): 46/46 right**, every first proposal right, 3/49 false alarms.
- **The rule clash on G12 is gone for luna.** With the rewording luna answers "The conditional clause is
  redundant but is stated in the task, so it should stay"; arm B G12 went from 7.33 rounds and 20/22 false
  alarms per run to 1 round and 0/2.
- **Budget: OpenCode 116 runs, 301 calls (cap 130 / 300): one call over.** My guard tripped at 284, after every
  B4 run had started, and the runs in flight added 17. So the B4 rerun at `none` of the cases wrong at none was
  not run.
  Subscriptions at the end: Claude 7-day 30 %, Codex 5 h 10 %, weekly 6 %.

## Per-arm table

Every row is scored with E's cards, so G12 uses the fixed card (B1). Columns as in the last report, plus
seconds per call and output tokens (reasoning tokens in brackets; OpenCode usage is logged only since this
loop, so arms A-D at none show 0; Claude CLI reports thinking inside output tokens).

| arm | generator + critic | runs | right | accepted | wrong | first proposal right | critic catch on call 1 | false alarms | critic calls/run | calls gen+critic | wall s median (sum) | s/call gen, critic | output tokens (reasoning) | rounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | deepseek + glm, none | 46 | 42 (91%) | 1 | 3 | 40/46 | 3/6 | 4/46 | 1.17 | 54+54 | 6 (362) | 4, 2 | not logged | r1 |
| B | Haiku + luna | 48 | 47 (98%) | 0 | 1 | 48/48 | 0/0 | 24/71 | 1.48 | 71+71 | 59 (5882) | 48, 16 | 1,136,441 (70,102) | r1, r3 |
| C | Haiku + glm, none | 18 | 18 (100%) | 0 | 0 | 18/18 | 0/0 | 0/18 | 1.00 | 18+18 | 42 (960) | 40, 2 | 228,156 | r2 |
| D | deepseek + luna | 18 | 16 (89%) | 0 | 2 | 13/18 | 5/5 | 25/41 | 2.56 | 46+46 | 39 (1250) | 4, 18 | 52,163 (48,881) | r2 |
| **E** | **luna + Haiku** | 46 | 46 (100%) | 0 | 0 | 46/46 | 0/0 | 3/49 | 1.07 | 49+49 | 102 (5066) | 16, 78 | 1,012,942 (45,639) | e1 |
| A medium | deepseek + glm, medium, hard 5 + 5 random, x2 | 20 | 19 (95%) | 0 | 1 | 15/20 | 4/5 | 1/20 | 1.25 | 25+25 | 60 (1713) | 38, 4 | 125,533 (119,364) | m1 |
| A high | deepseek + glm, high, W5a | 1 | 1 | 0 | 0 | 1/1 | 0/0 | 0/1 | 1.00 | 1+1 | 282 | 267, 14 | 21,212 (20,663) | h1 |
| **B4** | deepseek + glm, medium, B1 + B2 | 46 | 46 (100%) | 0 | 0 | 39/46 | 7/7 | 2/48 | 1.20 | 55+55 | 39 (2271) | 32, 3 | 161,496 (149,193) | b4 |

With the old G12 card arm E has 45/46 (its G12 is `RespondedExistence` + key-before-box order + goal, now
`exact`). Arm E's false alarms: Haiku asked to drop the stated `RespondedExistence` on G12 (the clash below),
and twice asked for the card's main answer `Precedence(door_open, key_lost)` over the also-right
`Absence(key_lost)` (G6, W5b). All three ended right.

## Critic set (38 items, same items for every critic)

w03 and r05 now use UnlockPickup's events (mechanical fix, `items.json`). Old prompt for every row.

| critic | caught on call 1 | defects flagged on call 1 | flagged in the run | accepted with a defect left | rejected the fixed candidate | false alarms (right items) | critic calls | judge calls | wall s median | critic output tokens (reasoning) |
|---|---|---|---|---|---|---|---|---|---|---|
| glm, none | 14/28 | 20/41 (49%) | 21/41 | 15 | 0 | 0/10 | 55 | 17 | 3 | not logged |
| glm, medium | 22/28 | 30/41 (73%) | 33/41 | 8 | 3 | 2/10 | 63 | 25 | 9 | 23,547 (15,487) |
| luna | 27/28 | 39/41 (95%) | 40/41 | 1 | 5 | 2/10 | 66 | 28 | 35 | 86,357 (81,693) |
| **Haiku** | 28/28 | 41/41 (100%) | 41/41 | 0 | 4 | 2/10 | 66 | 28 | 141 | 1,475,414 (in output) |

Flagged per defect kind: glm none event 0/5, extra 1/7, missing 5/8, template 5/8; glm medium event 3/5,
extra 4/7, missing 6/8, template 7/8; luna and Haiku miss at most one per kind. glm at medium still accepts
w01, w02, w04, w05, w10, w12, w16, w22 with a defect left.

Every strong critic rejects the same fixed candidates and right items: s02, w08 (W5a), w03, r05 (UnlockPickup)
and r10. They ask for orders the task states and the level forces (key before door, door before box), which
the cards mark `forced`, so optional. See "Left for the freeze".

## Thinking level (A3)

`CONFIG.reasoning` reaches OpenCode as `reasoning_effort` (`get_engine` -> `OpenCodeEngine(..., CONFIG.reasoning)`
-> `_create_completion`, `app/src/engines/provider_engines.py`). The adapter now logs the level sent, refused
sends, usage and thinking size per call (`provider` in each call record). Probe at medium: deepseek 6,446
reasoning tokens, 85 s; glm 104 reasoning tokens, 3.5 s. No refused send at medium or high.

| | none | medium | high |
|---|---|---|---|
| hard cases W5a, U5, S2, O7, G12 | 1 right, 1 accepted, 3 wrong (1 run each) | 9/10 right (2 runs each); B4 5/5 | W5a 1/1 |
| 5 random cases right at none | 5/5 | 10/10 | - |
| all 46 cases | 42 right, 1 accepted, 3 wrong | 46/46 (B4) | - |
| calls per run (gen+critic) | 2.35 | 2.39 (B4) | 2 |
| generator call, median | 4 s | 32 s (B4), 38 s (m1) | 267 s (W5a) |
| critic call, median | 2 s | 3 s | 14 s |
| run wall, median (sum, 46 runs) | 6 s (362 s) | 39 s (2271 s) | - |
| generator output tokens, median (max) | not logged | 2,889 (22,376 on W5a) | 20,183 |
| critic output tokens, median | not logged (glm: 0 reasoning) | 238 (111 reasoning) | 1,029 |
| critic set, glm caught on call 1 | 14/28 | 22/28 | - |

Mistakes fixed by medium: U5 (template: `Precedence(door_open, key_lost)` for "try not to drop the key while the
door is still closed"), S2 (hard last step on the key, not the door), O7 (hard `Existence` of the ball and the
key after glm's false alarm), W5a in 2 of 3. The W5a slip left (m1 r2): hard `Existence(door_open)` in place of
`Precedence(door_open, target_picked_up)`. High was run once, only on W5a: right, at the same cost as medium
on that case (W5a at medium: 285-303 s, 22.7 K tokens), so one sample says nothing about high.

## Fixes (Phase B, uncommitted in E)

### B1. G12 card (`experiments/benchmark/templates/tasks.json`, `tpl-responded-existence-2-goal`)

```diff
         ["RespondedExistence", ["blocker_moved", "has_door_key"], "hard"],
-        ["Existence", ["target_picked_up"], "hard"]
+        ["Existence", ["target_picked_up"], "hard"],
+        ["Precedence", ["has_door_key", "target_picked_up"], "hard"],
+        ["Precedence", ["blocker_moved", "target_picked_up"], "hard"]
       ],
+      "forced": [2, 3],
       "also_ok": [
         [["Existence", ["target_picked_up"], "hard"]],
-        [["RespondedExistence", ...], ["Precedence", ["has_door_key", "target_picked_up"], "hard"], ["Existence", ...]]
+        [["Precedence", ["has_door_key", "target_picked_up"], "hard"], ["Existence", ["target_picked_up"], "hard"]]
```

Plus a sentence in the card notes and a paragraph in `experiments/benchmark/templates/README.md`.

- Proof, `runs/b1-equiv.txt` (`tools/equiv.py`, product of the compiled clause DFAs): key order + goal against
  the same plus the `RespondedExistence`: EQUAL (8 reachable product states agree). Controls: goal alone against
  `RespondedExistence` + goal, DIFFERENT on `[blocker_moved, target_picked_up]`; key order + goal against goal
  alone, DIFFERENT on `[target_picked_up]`.
- Both box orders are forced: the door opens only from the ball's cell and with the key, and the box room has
  no other entrance (`envs/minigrid-blocked-unlock-pickup/environment.md` constraints, scripted plans). So
  both go in `expect` as `forced`, following the README convention, and the old `also_ok` answer with the key
  order becomes `exact`; arm C's `Precedence(blocker_moved, target_picked_up)` is now `exact` too.
- Before/after on all old G12 runs (A, B x3, C x2, D x2, E): 2/9 right -> 6/9 right. Arm B 45 -> 47/48,
  arm C 17 -> 18/18, arm E 45 -> 46/46. The three still wrong are luna loops (B r3-r2, D x2) that end with no
  machine: the B2 clash.

### B2. Critic redundancy rule (`app/src/prompts/compiler-rm/reward-machine-critic.system.md`)

```diff
 - `Redundant`: a hard clause the other hard clauses already imply, so the machine is the
-  same without it. It is a defect on its own: reject and ask to drop it, usually the `Existence`
-  of an earlier step of a `Precedence` chain, and keep the chain and the `Existence` of the last
-  step.
+  same without it. A listed `Existence` is a defect on its own: reject and ask to drop it, usually
+  the `Existence` of an earlier step of a `Precedence` chain, and keep the chain and the `Existence`
+  of the last step. Any other listed clause that a task sentence states, such as an order or an
+  "if" rule, stays: never ask to drop it.
@@ checklist 6
-   ... One redundancy is worth a rejection: in a stated
+   ... One redundant `Existence` is worth a rejection: in a stated
```

Tests, before = earlier runs on the same cases or the critic's verdict on the same fixed candidate:

| test | before | after |
|---|---|---|
| luna, arm B pipeline: G12 x2, G4, G6, C2, W2b + random O5, U1, U6, W5b | 10/11 right, false alarms 24/34, 3.09 rounds/run, 3678 s | 10/10 right, false alarms 5/15, 1.50 rounds/run, 1412 s |
| luna, arm B, G12 only | 2/3 right (one ran out of 10 attempts), false alarms 20/22, 7.33 rounds/run | 2/2 right, 0/2, 1 round |
| luna, fixed candidates s02, s05, w08, w16 (1 call each) | 4/4 rejected | 3/4 rejected (w16 now accepted) |
| glm medium, same fixed candidates | s02 and w08 rejected, s05 accepted, w16 never reached | s02, w08 rejected; s05, w16 accepted |
| redundancy catches w17, w18 (only items whose clues list a redundant clause) | luna, glm medium: caught, 2/2 and 1/1 flagged | same, both critics |
| right items r08, r09 (random) | accepted | accepted (both critics) |
| glm medium, G12 in the pipeline | 2/2 right (m1) | right in B4, accepted on call 1 with `RespondedExistence` listed as redundant |

glm loses no catch. luna's other false alarms stay: G4 (3, asks for the key and door orders the level forces), G6 (1,
`Absence` vs `Precedence` for the key drop), C2 (1, an environment fact about a missing siren). On w17 the judge (deepseek, none) graded glm's feedback as
flagging nothing although it names both redundant `Existence` clauses; counted by hand.

### B3. Generator wording: not done

Medium fixed U5 (3/3), S2 (3/3) and O7 (3/3). W5a is right 2 of 3 at medium. Its slip breaks a rule the prompt
already states ("Never replace it with an `Existence` of the earlier step", `reward-ltlf-creator.system.md`), so
there was no wording to fix, and no OpenCode budget left to test one.

### B4. Final rerun

46/46 right at medium (table above). No wrong machine left. The `none` rerun of the cases wrong at none
(W5a, U5, S2, O7) was not run: budget.

The four cases wrong or accepted at none, as B4 built them (RM text files in `runs/b4/A/`):

1. **W5a** "Move the ball away from the door before you take the key. Try not to drop the key while the door is
   still closed. Whenever you are holding the key, try to have the door open at that moment or open it
   afterwards. Then open the door with the key and pick up the box in the other room."
   LTLf: `(((~has_door_key)Ublocker_moved)|(G(~has_door_key)))` ; `(((~door_open)Uhas_door_key)|(G(~door_open)))` ;
   `(((~target_picked_up)Udoor_open)|(G(~target_picked_up)))` ; `(Ftarget_picked_up)` ; `(~(Fkey_lost))` soft ;
   `(G(has_door_key->(Fdoor_open)))` soft. RM: `llm-loop-evidence/runs/b4/A/W5a-r1.rm`.
   At none (A W5a-r1): extra hard `Existence(door_open)`, `Existence(has_door_key)`; RM `model-compare-evidence/runs/r1/A/W5a-r1.rm`.
2. **U5** "Open the door, then take the box from the other room; try not to drop the key while the door is still
   closed." LTLf: `(Ftarget_picked_up)` ; `(((~target_picked_up)Udoor_open)|(G(~target_picked_up)))` ;
   `(~(Fkey_lost))` soft. RM: `llm-loop-evidence/runs/b4/A/U5-r1.rm`. At none: soft `Precedence(door_open, key_lost)`
   for the ban; RM `model-compare-evidence/runs/r1/A/U5-r1.rm`.
3. **S2** "Pick up the key, then open the door, and then, ideally, walk onto the goal." LTLf: `(Fdoor_open)` ;
   `(((~door_open)Uhas_key)|(G(~door_open)))` ; `(((~at_goal)Udoor_open)|(G(~at_goal)))` ; `(Fat_goal)` soft.
   RM: `llm-loop-evidence/runs/b4/A/S2-r1.rm`. At none: hard `Existence(has_key)` instead of `Existence(door_open)`;
   RM `model-compare-evidence/runs/r1/A/S2-r1.rm`.
4. **O7** "Pick up the blocking ball and the key, in either order, unlock the door, and then pick up the box in
   the other room." LTLf: `(Ftarget_picked_up)` ; `(((~door_open)Ublocker_moved)|(G(~door_open)))` ;
   `(((~door_open)Uhas_door_key)|(G(~door_open)))` ; `(((~target_picked_up)Udoor_open)|(G(~target_picked_up)))`.
   RM: `llm-loop-evidence/runs/b4/A/O7-r1.rm`. At none: accepted with redundant hard `Existence` of the ball and
   the key; RM `model-compare-evidence/runs/r1/A/O7-r1.rm`.

G12 in B4: "If you move the ball, you must also take the key. Then pick up the box in the other room."
LTLf `((Fblocker_moved)->(Fhas_door_key))` ; `(((~target_picked_up)Uhas_door_key)|(G(~target_picked_up)))` ;
`(Ftarget_picked_up)`. RM: `llm-loop-evidence/runs/b4/A/G12-r1.rm`.

## Recommendation

Set the production pair to `reasoning = medium` for both roles. Evidence: 46/46 against 42/46 (3 wrong, 1
accepted) on the same cases, the critic set's catch rate up from 14/28 to 22/28, the same number of calls per
run. Price: a run takes 39 s median instead of 6 s (2271 s against 362 s for the 46 cases), and about 1,500
output tokens per call on average. High is not worth testing further on this budget: on W5a it cost the same as
medium, and one run proves nothing. `CONFIG.reasoning` still defaults to `none`; I changed no default.

## Left for the freeze

1. **Choose the reasoning default** (above).
2. **Stated orders the level forces.** Every strong critic (luna, Haiku, glm at medium) asks for them (s02, w08,
   w03, r05 on the critic set; G4 in arm B), while the cards mark them `forced`, optional. Critic rule 8 says to
   keep them. The decision records say the critic rejects a clause that restates an environment-guaranteed
   order (`docs/decisions/arm-fm/task-and-rm-identity.md:109-111`, `docs/decisions/arm-fm/rm-execution.md:95-98`).
   These three disagree. Today it costs extra rounds, not wrong machines. One owner has to decide which reading
   wins; the cards and the critic set's fixed candidates then follow.
3. **Short first proposals at medium** (10/66 runs). They are safe only while the critic catches them; glm at
   medium did, 10 of 10. Watch them in the next full run; with no cause known I made no change.
4. **The `none` rerun of W5a, U5, S2, O7 with the rewording** was not run (budget). It would show whether B2
   alone moves anything at none; B2 touches only candidates whose clues list a redundant non-`Existence`
   clause, so I expect no change there.
5. glm at medium still accepts 8/28 critic-set items with a defect left (luna 1, Haiku 0). In the pipeline it
   caught 11 of 12 wrong first proposals at medium (m1 4/5, B4 7/7).

## Paper candidates

1. Thinking level for the production pair: none against medium on the 46 cases (42 -> 46 right) and on the
   critic set (14 -> 22 of 28 caught on call 1), with time and tokens. Inputs: `runs/b4`, `runs/m1`,
   `runs/critic/glm-medium`, last report's `r1/A` and `critic/glm`.
2. The redundancy-rule fix: luna's G12 loop (7.33 rounds, 20/22 false alarms per run) gone (1 round, 0/2), with
   the quoted critic answer. Inputs: `runs/b2`, `runs/b2g`, `runs/critic/*-b2`.
3. The G12 card gap closed by a DFA equality proof (`tools/equiv.py`, `runs/b1-equiv.txt`): 2/9 -> 6/9 of the
   old G12 runs scored right.
4. Arm E, luna generator with Haiku critic: 46/46, every first proposal right.
5. Failure mode: short first proposals under thinking (10/66 at medium, 0/46 at none), all caught.

## Decision records

Update proposed, not made (the root owns records). B2 fits `task-and-rm-identity.md:87-89` ("Critics do not
demand redundant existence clauses") and could add that a stated non-`Existence` clause is never a redundancy
defect. Separately, the records quoted in item 2 above already disagree with critic rule 8, which this loop did
not change. If the user picks `medium`, `task-and-rm-identity.md:112-115` (default `none`) needs the new default.

## Files changed in E (uncommitted)

- `app/src/prompts/compiler-rm/reward-machine-critic.system.md` (B2)
- `experiments/benchmark/templates/tasks.json` (B1, card `tpl-responded-existence-2-goal`)
- `experiments/benchmark/templates/README.md` (B1 note)
- `experiments/dev/model-compare/cli_engine.py` (untracked adapter: `_metered` logs OpenCode usage per call)

Checks: `pre-commit run --files` on the four files passed. Unit tests in E: 201 run, 2 fail, the two
`test_engines` folder-name tests that always fail in a worktree (`known-errors`/workflow note), 2 skipped.
