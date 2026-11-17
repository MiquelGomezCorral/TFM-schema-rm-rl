# Staging of the shop-ground-up wave, slice 2: nine training-complete machines (seven, plus the fixed pair)

Plan: `../plan.md` (R3, R5, R16, steps 6-7, live tests S2-L1 and S2-L2). Everything here is built from the main checkout's code
(commit `c1c3efd`, read only); no worktree and no tracked file was touched. No model call; embeddings come from the local
embedding server (nomic-embed-text, port 8934).

`SL` = `/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl/.git/agent-memory/plans/testing-program-20261111/slices`.

## Bundles (`bundles/<name>/`, nine, each loads with `load_bundle` and passes `validate(require_complete=True)`)

| bundle | states | source | clauses or hand text |
|---|---|---|---|
| step2-chain | 8 | copy of `SL/shop-steps/bundles/farm/shop-order-deliver`, machine recompiled from new clauses with today's compiler | `Response(client_arrived, order_taken)`, `Response(order_taken, holding_food)`, `Response(holding_food, order_served)`, all hard |
| step2-generated | 8 | exact copy of `SL/shop-steps/bundles/farm/shop-order-deliver` (the model's own clauses) | `Response(client_arrived, order_taken)`, `Response(client_arrived, holding_food)`, `Response(client_arrived, order_served)`, all hard |
| step3-ground | 5 | hand text in `scripts/build_bundles.py` (`GROUND_TEXT`), shell from `SL/shop-serve-only/bundles/farm/shop-serve-only` | linear u0 -> u1 -> u2 -> u3 -> u4 -> u0, +1 per agent stage (+2 for the order taken with food already in hand), arrival 0, no negative reward, end judgment kept with failed rewards 0 |
| step3-h2 | 5 | `SL/shop-handmade/h2-units.txt` as written (the saved file lacks only the zero-pay `(u0, client_arrived, u1) -> 0` line the serializer drops); same shell | the hand machine with drop penalties (-1, -2), step-back edges and end charges (hard -1, soft -0.5) |
| step3-chain4 | 16 | copy of `SL/shop-serve-only/bundles/farm/shop-serve-only`, machine recompiled from new clauses | `Response(client_arrived, order_taken)`, `Response(order_taken, holding_food)`, `Response(holding_food, food_prepared)`, `Response(food_prepared, order_served)`, all hard (R16 step 3) |
| step3-chain4-noend | 16 | `step3-chain4` through `scripts/ablate_rm.py` (`ablate-rm --off end_judgment`), manifest records `ablation.off = end_judgment` | same four clauses; the machine text has no end-judgment lines (no accepting set, no failed rewards) |
| step3-chain4-fixed | 16 | copy of `SL/shop-serve-only/bundles/farm/shop-serve-only`, machine recompiled from new clauses (found by `scripts/fix_search.py`, see `chain4-fixed.md`) | `Response(client_arrived, order_taken)`, `Response(order_taken, holding_food)`, `Response(order_taken, food_prepared)`, `Response(food_prepared, order_served)`, all hard: R16's chain with the third clause triggered by the order |
| step3-chain4-fixed-noend | 16 | `step3-chain4-fixed` through `ablate-rm --off end_judgment`, manifest records `ablation.off = end_judgment` | same four clauses; no end-judgment lines. **The run config needs `time_limit_penalty: 0`**, otherwise the cut charges the flat -0.5 (see below) |
| step3-generated | 8 | exact copy of `SL/shop-serve-only/bundles/farm/shop-serve-only` (the model's own clauses) | `Response(client_arrived, order_taken)`, `Response(order_taken, food_prepared)`, `Response(food_prepared, order_served)`, all hard |

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
| step3-ground | PASS | ok | PASS |
| step3-h2 | PASS | ok | PASS |
| step3-chain4 | PASS on the two asked lines; a full service never returns to accepting (net -0.2, end charge -1) | ok | FAIL (solve ends accepting 0/100) |
| step3-chain4-noend | same as chain4, end charge is the flat -0.5 | ok | FAIL (same cause) |
| step3-chain4-fixed | PASS (stages > 0, drop, ends accepting, net 0) | ok | PASS (accepting 100/100, end charge 0) |
| step3-chain4-fixed-noend | PASS, same pays | ok | PASS (accepting 100/100; end charge -0.50 at the config default, 0 with `time_limit_penalty: 0`) |
| step3-generated | FAIL: pickup pays 0 | ok | PASS |

## Folders

- `bundles/` the seven bundles.
- `graphs/<name>.html` (plus `.svg`) interactive Reward Machine graph, `render-rm --html`, one per machine. `step3-chain4-noend.html` equals `step3-chain4.html`: the graph draws states and edges only, and the
  two machines differ in the end-judgment header lines (accepting set, failed rewards, pending promises), not in edges.
- `pay-check.md`, `checks.md` the two deliverables with every command; both end with an addendum for the fixed pair.
- `chain4-fixed.md` the search for the working step-3 chain: candidates, why the literal chain fails, the winner's rows.
- `plancheck/<name>.md` full plan-check tables per bundle.
- `labelcheck/` link folders and `labeling_check.json` records of `repair-labeling --check-only` (the links point at `bundles/`).
- `scripts/` `build_bundles.py` (builds seven bundles), `fix_search.py` (the candidate search), `compile_probe.py` (recompiles the chains; equals-stored check for the generated
  machines), `walk.py` (pay walk, extends `SL/shop-regen/walk.py`), `plan_check.py` (copy of the shop-steps one with the step-3
  skipping plans), `check_bundles.py` (loader table).
- `work/` compiled texts, embedding cache, the naive ground variant and its walk, intermediate tables.

## Rebuild and rerun

From the main checkout, `PY=/home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin/python`, `ST` = this folder,
`OMP_NUM_THREADS=2 PYTHONPATH=app`; the embedding server must answer on port 8934.

```bash
$PY -W ignore $ST/scripts/build_bundles.py step2-generated step3-generated step2-chain step3-chain4 step3-chain4-fixed step3-h2 step3-ground
$PY -W ignore app/main.py ablate-rm --bundle $ST/bundles/step3-chain4 --off end_judgment --output $ST/bundles/step3-chain4-noend
$PY -W ignore app/main.py ablate-rm --bundle $ST/bundles/step3-chain4-fixed --off end_judgment --output $ST/bundles/step3-chain4-fixed-noend
$PY -W ignore $ST/scripts/check_bundles.py
cd $ST/bundles && $PY $ST/scripts/walk.py step2-chain=step2-chain/reward_machine.txt ...   # pay check, see pay-check.md
```

(`ablate-rm` flag names as in `app/scripts/ablate_rm.py`; the bundle was made with that route and its manifest records it.)
The labeling and plan-check commands are in `checks.md`. The ablated bundle loads and validates like the others.

## Run config for the no-end bundles (`step3-chain4-noend`, `step3-chain4-fixed-noend`)

A machine with no end judgment gets the flat `time_limit_penalty` (default -0.5, `Configuration.time_limit_penalty`,
`app/src/config/config.py:304`; used at `app/src/arm_fm/runtime.py:224-226`) on the step the time limit cuts the episode.
For "nothing is charged at the end" the run config of every episode on these bundles must set:

```
time_limit_penalty: 0
```

(the config accepts 0 or any negative number, `config.py:483`). Without it the no-end arm differs from its twin by a -0.5 cut charge
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
