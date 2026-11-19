# Shop ground-up machines: twenty-four training-complete bundles (seven, the fixed pair, the final prompt's step-2 machine, its hand copy, the step-2 ground machine, two scale-only copies, the final prompt's step-3 machine, two x10 copies of generated machines, the step-3 ladder copy, and six reward-shape copies of the two A3 machines)

Built from the code at commit `c1c3efd`, with no model call; embeddings come from the local embedding server
(nomic-embed-text). The pay checks, plan checks, graphs and build scripts named below stay with the private plan notes,
outside the repository; this folder holds the bundles and the run tooling (`runs/`).

`SL` = the earlier testing-program slices in the private plan notes (`plans/testing-program-20261111/slices`), not in
the repository; the `SL/...` sources below record where each bundle came from.

## Bundles (`bundles/<name>/`, twenty-four, each loads with `load_bundle` and passes `validate(require_complete=True)`)

| bundle | states | source | clauses or hand text |
|---|---|---|---|
| step2-chain | 8 | copy of `SL/shop-steps/bundles/farm/shop-order-deliver`, machine recompiled from new clauses with today's compiler | `Response(client_arrived, order_taken)`, `Response(order_taken, holding_food)`, `Response(holding_food, order_served)`, all hard |
| step2-generated | 8 | exact copy of `SL/shop-steps/bundles/farm/shop-order-deliver` (the model's own clauses) | `Response(client_arrived, order_taken)`, `Response(client_arrived, holding_food)`, `Response(client_arrived, order_served)`, all hard |
| step2-a3 | 8 | exact copy of generator try `armA3-step2-1`, written by the final generator prompt (A3) | `Response(client_arrived, order_taken)`, `Response(order_taken, holding_food)`, `Response(order_taken, order_served)`, all hard |
| step2-a3-ladder | 8 | `step2-a3` copied, then hand-edited (cause test for the chain failure, round 3) | the same machine with one change: `PENDING_PROMISES` gives `u4` (client arrived, order not taken) `hard 3` instead of `hard 1`, so the cut charge is -3.3 / -2.2 / -1.1 / 0 after the arrival / order / pickup / serve (step2-generated's ladder; step2-a3's is -1.3 / -2.2 / -1.1 / 0). Edges and pays are unchanged |
| step2-ground | 4 | hand text in the plan notes' `round3/scripts/ground2_build.py`, shell from `step2-generated` (labeling unchanged: it already defines `holding_food`) | `step3-ground` without the prepare stage: chain u0 -> u1 -> u2 -> u3, then u3 -> u0 when no client is present or u3 -> u1 when one is, +1 per agent stage (+2 for the order taken with food already in hand), arrival 0, no negative reward, no step-back edges, end judgment kept with failed rewards 0 |
| step2-a3-x10 | 8 | `step2-a3` copied, then every pay and both failed rewards multiplied by 10 (scale-versus-shape test, round 3; script `round3/scripts/sign_build.py` in the plan notes) | the same machine with only numbers changed: arrival -3, stages +1 to +5, failed rewards -10 (hard) and -5 (soft), so the cut charge is -13 / -22 / -11 / 0 after the arrival / order / pickup / serve. States, edges and `PENDING_PROMISES` are unchanged |
| step2-ground-x01 | 4 | `step2-ground` copied, then every pay multiplied by 0.1 (same script) | the same machine with only numbers changed: +0.1 per agent stage (+0.2 for the order taken with food already in hand), arrival 0, failed rewards stay 0. States, edges and `PENDING_PROMISES` are unchanged |
| step2-generated-x10 | 8 | `step2-generated` copied, then every pay and both failed rewards multiplied by 10 (scale test 2, round 3; script `round3/scripts/scale2_build.py` in the plan notes, with `sign_build.py`'s scaling) | the same machine with only numbers changed: arrival -3, other pays -2 to +3, failed rewards -10 (hard) and -5 (soft), so the cut charge is -33 / -22 / -11 / 0 after the arrival / order / pickup / serve. States, edges and `PENDING_PROMISES` are unchanged |
| step3-ground | 5 | hand text in `scripts/build_bundles.py` (`GROUND_TEXT`), shell from `SL/shop-serve-only/bundles/farm/shop-serve-only` | chain u0 -> u1 -> u2 -> u3 -> u4, then u4 -> u0 when no client is present or u4 -> u1 when one is, +1 per agent stage (+2 for the order taken with food already in hand), arrival 0, no negative reward, end judgment kept with failed rewards 0 |
| step3-h2 | 5 | `SL/shop-handmade/h2-units.txt` as written (the saved file lacks only the zero-pay `(u0, client_arrived, u1) -> 0` line the serializer drops); same shell | the hand machine with drop penalties (-1, -2), step-back edges and end charges (hard -1, soft -0.5) |
| step3-chain4 | 16 | copy of `SL/shop-serve-only/bundles/farm/shop-serve-only`, machine recompiled from new clauses | `Response(client_arrived, order_taken)`, `Response(order_taken, holding_food)`, `Response(holding_food, food_prepared)`, `Response(food_prepared, order_served)`, all hard (R16 step 3) |
| step3-chain4-noend | 16 | `step3-chain4` through `app/scripts/ablate_rm.py` (`ablate-rm --off end_judgment`), manifest records `ablation.off = end_judgment` | same four clauses; the machine text has no end-judgment lines (no accepting set, no failed rewards) |
| step3-chain4-fixed | 16 | copy of `SL/shop-serve-only/bundles/farm/shop-serve-only`, machine recompiled from new clauses (found by `scripts/fix_search.py`, see `chain4-fixed.md`) | `Response(client_arrived, order_taken)`, `Response(order_taken, holding_food)`, `Response(order_taken, food_prepared)`, `Response(food_prepared, order_served)`, all hard: R16's chain with the third clause triggered by the order |
| step3-chain4-fixed-noend | 16 | `step3-chain4-fixed` through `ablate-rm --off end_judgment`, manifest records `ablation.off = end_judgment` | same four clauses; no end-judgment lines. **The run config needs `time_limit_penalty: 0`**, otherwise the cut charges the flat -0.5 (see below) |
| step3-generated | 8 | exact copy of `SL/shop-serve-only/bundles/farm/shop-serve-only` (the model's own clauses) | `Response(client_arrived, order_taken)`, `Response(order_taken, food_prepared)`, `Response(food_prepared, order_served)`, all hard |
| step3-a3 | 16 | exact copy of generator try `armA3-step3-1`, written by the final generator prompt (A3); the step-3 twin of `step2-a3` (copied by `round3/scripts/scale2_build.py`) | `Response(client_arrived, order_taken)`, `Response(order_taken, holding_food)`, `Response(order_taken, food_prepared)`, `Response(food_prepared, order_served)`, all hard |
| step3-a3-x10 | 16 | `step3-a3` copied, then every pay and both failed rewards multiplied by 10 (same script) | the same machine with only numbers changed: arrival -4, pays -5 to +8, failed rewards -10 (hard) and -5 (soft), so the cut charge is -14 / -23 / -12 / -11 / 0 after the arrival / order / pickup / prepare / serve. States, edges and `PENDING_PROMISES` are unchanged |
| step3-a3-x10-ladder | 16 | `step3-a3-x10` copied, then hand-edited (ladder test 3, round 3; script `round3/scripts/ladder3_build.py` in the plan notes) | the same machine with one change: `PENDING_PROMISES` gives `u6` (client arrived, order not taken) `hard 2` instead of `hard 1`, so the cut total (pays so far plus the end charge) is -24 / -23 / -12 / -11 / 0 after the arrival / order / pickup / prepare / serve (step3-a3-x10's: -14 / -23 / -12 / -11 / 0, a dip at the order). Pays, edges, states and failed rewards are unchanged |
| step2-a3-done | 8 | `step2-a3` copied, then pay values only (shape test 4, round 4; script `round4/scripts/shape4_build.py` in the plan notes) | the compiled pays and charges kept, plus +0.3 (stages per service 3 x 0.1) on every serve edge (21), so a full service nets +0.3 instead of 0: arrival -0.3, order +0.1, pickup +0.1, serve +0.4. Failed rewards -1 / -0.5 and `PENDING_PROMISES` as in `step2-a3` |
| step2-a3-pot | 8 | `step2-a3` copied, then pay values, failed rewards and `PENDING_PROMISES` counts only (same script) | progress pay with take-back: arrival 0, order +0.1, pickup +0.1, serve +0.1 (net +0.3); an edge that goes back pays the difference; `HARD_FAILED_REWARD -0.1`, `SOFT_FAILED_REWARD 0`, `hard` = stages the open service has earned (`u1:1 u2:2 u3:2 u4:0 u5:1 u6:2 u7:2`), so every unfinished state cuts to 0 in total |
| step2-a3-pot0 | 8 | `step2-a3-pot` copied, then both failed rewards set to 0 (same script) | the same pays as `step2-a3-pot` and the same counts, with `HARD_FAILED_REWARD 0` and `SOFT_FAILED_REWARD 0`: no take-back at the cut (the cut total after each stage rises 0 / +0.1 / +0.2, then +0.3 at the serve) |
| step3-a3-done | 16 | `step3-a3` copied, then pay values only (same script) | the compiled pays and charges kept, plus +0.4 (stages per service 4 x 0.1) on every serve edge (87), so a full service nets +0.4 instead of 0. Failed rewards and `PENDING_PROMISES` as in `step3-a3` |
| step3-a3-pot | 16 | `step3-a3` copied, then pay values, failed rewards and `PENDING_PROMISES` counts only (same script) | progress pay with take-back as in `step2-a3-pot` over four stages: arrival 0, each stage +0.1, serve +0.1 (net +0.4); `HARD_FAILED_REWARD -0.1`, `SOFT_FAILED_REWARD 0`, `hard` = stages earned (`u1:1 u2:2 u3:3 u4:2 u5:3 u6:0 u7:3 u8:1 u9:2 u10:2 u11:3 u12:4 u13:5 u14:4 u15:5`; a state with two services open can hold more than 4) |
| step3-a3-pot0 | 16 | `step3-a3-pot` copied, then both failed rewards set to 0 (same script) | the same pays and counts as `step3-a3-pot` with `HARD_FAILED_REWARD 0` and `SOFT_FAILED_REWARD 0` |

Notes on how they differ from the packet's wording.

- **Ground is not "H2 minus penalties" alone.** Dropping only the negative pays leaves H2's two step-back edges, and each
  re-pick then pays +1 again (a drop + re-pick loop pays +1 raw, +2 prepared: farmable, `work/walk-naive.md`). The two
  step-back edges (u3 -> u2, u4 -> u2) are removed too. Judgment lines are kept with `HARD_FAILED_REWARD: 0` and
  `SOFT_FAILED_REWARD: 0`: the end charge is exactly 0, and the flat -0.5 `time_limit_penalty` (only used by a machine
  with no judgment at all) never applies. Text: `bundles/step3-ground/reward_machine.txt`.
- **Hand bundles carry no critic and no structural-check claim** in their manifest (`validation` is empty,
  `provenance.status = hand-written`); the hand text is stored in `generation.compiler_text`, a note in `generation.hand_machine`.
- **Labeling.** Step-2 and step-3 labelings come from the earlier generated bundles. The hand bundles and the chains for step 3 add
  `holding_food` (copied from step 2's labeling), because their machines read it; `step3-generated` has no `holding_food`.
- **State descriptions** are one plain sentence per state, in the generated bundles' style ("Still open: ..." lists the owed
  promises; the hand machines use one sentence per stage). Embeddings: `embed_descriptions_over_http`, cache in `work/embedding-cache.json`.

## Results (details in the two files)

| machine | pay check (`pay-check.md`) | labeling | plan check (100 seeds) |
|---|---|---|---|
| step2-chain | PASS | ok | PASS |
| step2-generated | PASS | ok | PASS |
| step2-a3 | PASS (generator evidence) | not rerun | PASS (generator evidence) |
| step2-a3-ladder | pay walk (round 1's scenarios): only the cut charge after the arrival changes (-1.3 to -3.3); best cycle pay 0 | not rerun (step2-a3's) | not run |
| step2-ground | PASS (round 1's scenarios: every stage > 0, a full service +3 in any order, nothing < 0, every cut charges 0; best cycle +3 per service, a drop + re-pick loop pays 0) | not rerun (step2-generated's) | PASS (100/100, no wrong plan ends accepting) |
| step2-a3-x10 | pay walk (round 1's scenarios): every pay and end charge is exactly 10 x step2-a3's; best serve-free cycle pay 0 | not rerun (step2-a3's) | not run |
| step2-ground-x01 | pay walk (same scenarios): every pay exactly 0.1 x step2-ground's, a full service +0.3, nothing < 0, every cut charges 0; no serve-free cycle | not rerun (step2-generated's) | not run (states and edges as in step2-ground, which passes) |
| step2-generated-x10 | pay walk (round 1's scenarios): every pay and end charge is exactly 10 x step2-generated's; best serve-free cycle pay 0 | not rerun (step2-generated's) | not run (states and edges as in step2-generated, which passes) |
| step3-ground | PASS | ok | PASS |
| step3-h2 | PASS | ok | PASS |
| step3-chain4 | PASS on the two asked lines; a full service never returns to accepting (net -0.2, end charge -1) | ok | FAIL (solve ends accepting 0/100) |
| step3-chain4-noend | same as chain4, end charge is the flat -0.5 | ok | FAIL (same cause) |
| step3-chain4-fixed | PASS (stages > 0, drop, ends accepting, net 0) | ok | PASS (accepting 100/100, end charge 0) |
| step3-chain4-fixed-noend | PASS, same pays | ok | PASS (accepting 100/100; end charge -0.50 at the config default, 0 with `time_limit_penalty: 0`) |
| step3-generated | FAIL: pickup pays 0 | ok | PASS |
| step3-a3 | pay walk (a full service in each of the three orders, two drop and re-pick services, a cut after each stage): the order-first service pays -0.4 +0.1 +0.1 +0.1 +0.1 (every agent stage > 0, net 0); with the pickup before the order the order pays +0.2 and the pickup 0; best serve-free cycle pay 0 | not rerun (the generator try's) | PASS (100/100, no wrong plan ends accepting, end charge 0) |
| step3-a3-x10 | pay walk (same scenarios): every pay and end charge is exactly 10 x step3-a3's; best serve-free cycle pay 0 | not rerun (step3-a3's) | not run (states and edges as in step3-a3, which passes) |
| step3-a3-x10-ladder | pay walk (same scenarios, `round3/scripts/ladder3_cut_walk.py`): every pay is identical to step3-a3-x10's; only the cut charge after the arrival changes (-10 to -20, total -14 to -24). The cut total rises strictly from the arrival on (-24 / -23 / -12 / -11 / 0) in the order-first, pre-pick and both drop and re-pick services; with the pickup after the arrival and before the order it is flat from the arrival to the pickup (-24, -24: `u6` has no `holding_food` edge, as in step3-a3-x10) and then rises; best serve-free cycle pay 0; the idle agent ends at -24, below every finished service (0) | not rerun (step3-a3's) | PASS (100/100, no wrong plan ends accepting, end charge 0; the do-nothing plan ends -20 at the cut) |
| step2-a3-done | pay walk (`round4/scripts/shape4_pay_walk.py`, every service order of round 1's scenarios): only the serve step differs from step2-a3 (+0.3); order-first service pays -0.3 +0.1 +0.1 +0.4, net +0.3; cut totals as step2-a3's until the serve (-1.3 / -2.2 / -1.1, then +0.3); idle / one service / two services: -1.3 / +0.3 / +0.6; best serve-free cycle pay 0, but a full service cycle pays +0.3, so the compiler's `_has_positive_cycle` would reject this shape | not rerun (step2-a3's) | PASS (100/100, no wrong plan ends accepting; do-nothing ends -1.00 at the cut) |
| step2-a3-pot | same walk: arrival 0, order +0.1, pickup +0.1, serve +0.1, net +0.3 in every order; cut total 0 after every stage before the serve, then +0.3; idle / one / two services: 0 / +0.3 / +0.6; best serve-free cycle pay 0; a full service cycle pays +0.3 (the compiler's positive-cycle check would reject it) | not rerun (step2-a3's) | PASS (100/100, no wrong plan ends accepting; end charge 0 / -0.10 / -0.20 for do-nothing / order only / order and food) |
| step2-a3-pot0 | same walk: the pays of step2-a3-pot; cut total after each stage 0 / +0.1 / +0.2, then +0.3; idle / one / two services: 0 / +0.3 / +0.6; best serve-free cycle pay 0; a full service cycle pays +0.3 | not rerun (step2-a3's) | PASS (100/100, no wrong plan ends accepting; end charge 0 in every plan) |
| step3-a3-done | same walk over `scale2_pay_walk`'s step-3 scenarios: only the serve step differs from step3-a3 (+0.4); order-first service pays -0.4 +0.1 +0.1 +0.1 +0.5, net +0.4; cut totals as step3-a3's until the serve (-1.4 / -2.3 / -1.2 / -1.1, then +0.4); idle / one / two services: -1.4 / +0.4 / +0.8; best serve-free cycle pay 0; a full service cycle pays +0.4 | not rerun (step3-a3's) | PASS (100/100, no wrong plan ends accepting; do-nothing ends -1.00 at the cut) |
| step3-a3-pot | same walk: arrival 0, each stage +0.1, serve +0.1, net +0.4 in every order; cut total 0 after every stage before the serve, then +0.4; idle / one / two services: 0 / +0.4 / +0.8; best serve-free cycle pay 0; a full service cycle pays +0.4 | not rerun (step3-a3's) | PASS (100/100, no wrong plan ends accepting; end charge 0 / -0.10 / -0.20 for do-nothing / order only / no prepare) |
| step3-a3-pot0 | same walk: the pays of step3-a3-pot; cut total after each stage 0 / +0.1 / +0.2 / +0.3, then +0.4; idle / one / two services: 0 / +0.4 / +0.8; best serve-free cycle pay 0; a full service cycle pays +0.4 | not rerun (step3-a3's) | PASS (100/100, no wrong plan ends accepting; end charge 0 in every plan) |

## Folders

- `bundles/` the twenty-four bundles.
- `runs/` the round configs and tooling (scheduler, watch table, judge); its `README.md` lists every run and command.

## Rebuild

The two `-noend` bundles come from their parents through `app/main.py ablate-rm --bundle <parent> --off end_judgment
--output <name>`, and their manifests record it. `step2-a3` and `step3-a3` are generator outputs (`armA3-step2-1`, `armA3-step3-1`) copied as is; `step2-a3-ladder` is a copy of `step2-a3` with
one edited line in `reward_machine.txt` (`u4: hard 3, soft 0`) and a hand-bundle manifest (script in the plan notes). The
other seven were built by a staging script kept with the plan notes; `step2-ground` by `round3/scripts/ground2_build.py` in the
plan notes (the same recipe as `step3-ground`, on `step2-generated`'s shell). `step2-generated-x10` and `step3-a3-x10` are byte copies of `step2-generated` and `step3-a3` with the numbers of `reward_machine.txt` scaled by 10 and a hand-bundle manifest (`round3/scripts/scale2_build.py` in the plan notes, which also copies `step3-a3`). `step2-a3-x10` and `step2-ground-x01` are byte copies of
`step2-a3` and `step2-ground` with the numbers of `reward_machine.txt` scaled and a hand-bundle manifest (`round3/scripts/sign_build.py`
in the plan notes). `step3-a3-x10-ladder` is a byte copy of `step3-a3-x10` with one edited line in `reward_machine.txt`
(`u6: hard 2, soft 0`) and a hand-bundle manifest (`round3/scripts/ladder3_build.py` in the plan notes). Each bundle's manifest and `reward_machine.txt` hold
everything training reads, and `load_bundle` plus `validate(require_complete=True)` accept all twenty-four.
The six `-done`, `-pot` and `-pot0` bundles are byte copies of `step2-a3` and `step3-a3` with only the pay values, both failed
rewards and the `PENDING_PROMISES` counts of `reward_machine.txt` rewritten and a hand-bundle manifest (`round4/scripts/shape4_build.py`
in the plan notes); a masked-number diff against the source shows only added reward rows, no transition, state or label changed.

## Run config for the no-end bundles (`step3-chain4-noend`, `step3-chain4-fixed-noend`)

A machine with no end judgment gets the flat `time_limit_penalty` (default -0.5, `Configuration.time_limit_penalty`,
`app/src/config/config.py:305`; used at `app/src/arm_fm/runtime.py:224-226`) on the step the time limit cuts the episode.
For "nothing is charged at the end" the run config of every episode on these bundles must set:

```
time_limit_penalty: 0
```

(the config accepts 0 or any negative number, `config.py:488-491`). Without it the no-end arm differs from its twin by a -0.5 cut charge
that no judgment caused.

## Findings that need a decision (not fixed by hand)

1. (Solved by `step3-chain4-fixed`, see `chain4-fixed.md`: the third clause is triggered by the order instead of by carrying. The literal
   chain stays as evidence.) `step3-chain4` and its `noend` twin never finish a correct service in the accepting state: `holding_food` is a condition,
   so `Response(holding_food, food_prepared)` re-opens on every carrying step after the prepare. Step 2's chain does not
   have it. A fix would need a different clause for step 3 (for example a trigger that is an event, or the prepare clause
   closed by something true when the food is served); that is a plan choice (R13/R16), not a staging edit.
2. Without an end judgment the trainer charges a flat `time_limit_penalty` (-0.5) at the cut
   (`app/src/arm_fm/runtime.py:224-226`). Compare `step3-chain4-noend` with `step3-chain4` only with `time_limit_penalty: 0` in the run config,
   or the comparison also changes the end charge from -1 to -0.5 for a reason that is not the judgment.
3. `step3-generated` pays 0 at the pantry pickup (its clauses skip `holding_food`), so it fails "every stage pays > 0" by design;
   it is the baseline machine.
