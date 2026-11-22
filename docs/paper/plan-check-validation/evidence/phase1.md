# Plan check study, phase1

- Code: the plan check of e6c3acb (main before the D1/D3 merge 029d82c, which landed at 14:19 during this run), exported read-only to S/code-e6c3acb/app and run by tools/run_checks.py. Between the two commits only app/src/benchmark/plan_check.py and traces.py changed in app/. Cards: the tasks.json files as committed in 029d82c (templates gained the 2026-11-22 readings).
- Truth: truth.json, from the scorer, the labeling replay, the 2026-11-22 rulings, trained results, paper entries and construction; pay-order and hand-read are marked as supplementary sources.
- Order slip: a first pass of the check ran on 8 set/suite folders before truth.json was written (14:07-14:10). I read 5 of those outputs first: set 1 base, box-carry, complex and templates matched the stored records already known from the inventory, and set 2 complex showed two passes that truth.json labels wrong, against the check. truth.json was written from the sources above, not from those runs. All 19 folders were then rerun for this table.
- Mutants of non-set-1 machines: tpl-absence-soft-1-goal~m-soft-pays-more and base-unlock-pickup~m-fact-wrong-object start from right final FARM bundles that are not in set 1.

## Counts

| set | true pass | true fail | FALSE PASS | FALSE FAIL | not counted | total |
|---|---|---|---|---|---|---|
| 1-right-final | 13 | 0 | 0 | 3 | 0 | 16 |
| 2-wrong-past | 3 | 8 | 3 | 0 | 1 | 15 |
| 3-arm-fm | 6 | 8 | 1 | 1 | 0 | 16 |
| 4-mutant | 0 | 13 | 2 | 0 | 0 | 15 |
| all | 22 | 29 | 6 | 4 | 1 | 62 |

## False and uncounted verdicts

- **FALSE FAIL** 1-right-final farm/tpl-existence-soft-1-goal (check: wrong-0-s1: breaks only soft rules and pays nothing)
  - truth: right, scorer exact; labeling ok; ruling D1 (a soft rule may be priced by paying less than the solve). D1 case: the soft break pays less (7 vs 12) with no negative step
  - why: D1: the soft rule is priced by paying less than the solve (7 vs 12), with no negative step; the pre-fix check (e6c3acb plan_check.py:186-190) asks for a negative step.
- **FALSE FAIL** 1-right-final farm/tpl-existence-two-soft-1-nogoal (check: wrong-0-s1: breaks only soft rules and pays nothing)
  - truth: right, scorer exact; labeling ok; ruling D1. D1 case: keeping the rule pays +1 per zombie, breaking it pays nothing
  - why: D1: keeping the rule pays +1 per zombie and breaking it pays nothing, no negative step.
- **FALSE FAIL** 1-right-final farm/tpl-precedence-soft-2-goal (check: wrong-0-s1: breaks only soft rules and pays nothing)
  - truth: right, scorer exact; labeling ok; ruling D1. D1 case
  - why: D1: the soft rule is priced by paying less, no negative step.
- **FALSE PASS** 2-wrong-past farm/cx-rules-only~prefreeze (check: pass)
  - truth: wrong, scorer exact; labeling ok; pay-order (supplementary): soft break -24.9 < hard break -1. pricing: a soft break on every step costs more over the episode than breaking a hard rule once, so walking into the well pays more
  - why: The defect is the price of a soft break repeated on every step against one hard break. No card plan breaks a soft rule step after step, so the plans never see it; only check-pay-order's stream bound does.
- **FALSE PASS** 2-wrong-past farm/cx-goal-many-rules~prefreeze (check: pass)
  - truth: wrong, scorer mismatch; labeling ok; pay-order (supplementary): soft break -24.9 < hard break -3. pricing: a soft break stream costs more than a hard break; also Existence(blocker_moved), Existence(has_door_key) in place of two orders the world already forces
  - why: Same blind spot as cx-rules-only~prefreeze (soft-break stream against a hard break). The clause swap (Existence for world-forced orders) changes nothing a plan can show.
- **not counted** 2-wrong-past farm/tpl-responded-existence-1-goal~prefreeze (check: pass)
  - truth: unclear, scorer mismatch; labeling ok. missing Response(key_found, target_picked_up), but the hard goal ends the episode at the pickup, so every finished run keeps it anyway
  - why: Not counted: the missing Response(key_found, target_picked_up) is implied by the hard goal that ends the episode at the pickup. The check passes it.
- **FALSE PASS** 2-wrong-past farm/tpl-chain-response-3-nogoal~prefreeze (check: pass)
  - truth: wrong, scorer mismatch; labeling ok. adds a hard Existence(at_exit) the no-goal task lacks, and RespondedExistence(at_exit, holding_box) in place of Response
  - why: The extra hard Existence(at_exit) adds a goal to a no-goal task, but the card's solve walks to the exit carrying the box anyway and so ends in the final. No plan keeps every rule while staying away from the exit, so the added goal is never tested.
- **FALSE FAIL** 3-arm-fm arm-fm/tpl-existence-soft-1-goal (check: wrong-0-s1: breaks only soft rules and pays nothing)
  - truth: right, labeling ok; ruling D1; hand-read: the switch pays 0.1 more, the exit pays 1 either way. D1 case
  - why: D1: the switch pays 0.1 and the exit 1 either way, so skipping the switch pays less with no negative step.
- **FALSE PASS** 3-arm-fm arm-fm/shop-siren (check: pass)
  - truth: wrong, hand-read. the shift ends at the first siren switched off, and a siren not switched off at once is forgotten (back to u0)
  - why: A no-goal card whose machine ends the shift at the first siren switched off. The solve reaches that final, so it passes; the check never asks that a no-goal machine keep running, and wrong-0 (never switch off) stays out of the final as a hard break should. The forgotten siren (back to u0 after one step) pays nothing either way.
- **FALSE PASS** 4-mutant farm/tpl-precedence-1-goal~m-well-pays (check: pass)
  - truth: wrong, construction. reward on the wrong edge: taking the key before the ball pays +20 on the step into the well, more than the solve's 14
  - why: The hard break goes into the well as it should, but pays +20 on the way, more than the solve's 14. The pay comparison (_check_pay) runs only for machines with no final state, so a well edge that pays more than the solve is not seen.
- **FALSE PASS** 4-mutant farm/base-doorkey~m-fact-late (check: pass)
  - truth: wrong, construction; labeling failed. labeling fact fires late: door_open is true only once the agent stands past the door column
  - why: door_open fires two steps late but in the same order, and the plans' end states are unchanged. The plan check cannot see a fact's timing; the labeling replay fails this copy.

Right verdicts whose deciding reason is not the real defect:

- farm/tpl-existence-soft-1-goal~m-soft-pays-more: fails on 'pays nothing' (the D1 rule); the real defect is that the soft break pays more than the solve (13 vs 12). The D1 fix must still fail it on pay.
- farm/tpl-absence-soft-1-goal~m-soft-pays-more: fails on 'pays nothing'; the real defect is that the soft break pays more than the solve. The D1 fix must still fail it on pay.
- farm/tpl-existence-two-soft-1-nogoal~m-rule-costs: fails first on 'pays nothing', but also on pay (idle 0 is not less than the solve's -2: _check_pay, no final state), so the D1 fix keeps it failed.
- arm-fm/tpl-response-soft-1-goal: fails on 'pays nothing'; the real defect is that the soft rule is made hard (ignoring the siren never finishes). wrong-0 pays 0, less than the solve's 1.1, so a D1 fix that accepts 'pays less' may pass it: a false pass to watch in phase 2.

## Every machine

| set | machine | card | truth | check | deciding plan | outcome |
|---|---|---|---|---|---|---|
| 1-right-final | farm/base-doorkey | base-doorkey | right | pass | - | true pass |
| 1-right-final | farm/base-key-corridor | base-key-corridor | right | pass | - | true pass |
| 1-right-final | farm/base-blocked-unlock-pickup | base-blocked-unlock-pickup | right | pass | - | true pass |
| 1-right-final | farm/cx-box-carry | cx-box-carry | right | pass | - | true pass |
| 1-right-final | farm/tpl-chain-response-1-nogoal-carry | tpl-chain-response-1-nogoal-carry | right | pass | - | true pass |
| 1-right-final | farm/cx-sequence | cx-sequence | right | pass | - | true pass |
| 1-right-final | farm/cx-siren | cx-siren | right | pass | - | true pass |
| 1-right-final | farm/cx-goal-many-rules | cx-goal-many-rules | right | pass | - | true pass |
| 1-right-final | farm/tpl-absence-1-nogoal | tpl-absence-1-nogoal | right | pass | - | true pass |
| 1-right-final | farm/tpl-precedence-1-goal | tpl-precedence-1-goal | right | pass | - | true pass |
| 1-right-final | farm/tpl-precedence-soft-1-goal | tpl-precedence-soft-1-goal | right | pass | - | true pass |
| 1-right-final | farm/tpl-existence-soft-1-goal | tpl-existence-soft-1-goal | right | FAIL | wrong-0-s1 | FALSE FAIL |
| 1-right-final | farm/tpl-existence-two-soft-1-nogoal | tpl-existence-two-soft-1-nogoal | right | FAIL | wrong-0-s1 | FALSE FAIL |
| 1-right-final | farm/tpl-precedence-soft-2-goal | tpl-precedence-soft-2-goal | right | FAIL | wrong-0-s1 | FALSE FAIL |
| 1-right-final | farm/shop-serve | shop-serve | right | pass | - | true pass |
| 1-right-final | farm/shop-siren | shop-siren | right | pass | - | true pass |
| 2-wrong-past | farm/cx-box~prefreeze | cx-box | wrong | FAIL | wrong-0-s1 | true fail |
| 2-wrong-past | farm/cx-rules-only~prefreeze | cx-rules-only | wrong | pass | - | FALSE PASS |
| 2-wrong-past | farm/cx-goal-many-rules~prefreeze | cx-goal-many-rules | wrong | pass | - | FALSE PASS |
| 2-wrong-past | farm/tpl-not-co-existence-2-goal~prefreeze | tpl-not-co-existence-2-goal | wrong | FAIL | solve-s1 | true fail |
| 2-wrong-past | farm/tpl-precedence-1-nogoal~prefreeze | tpl-precedence-1-nogoal | right | pass | - | true pass |
| 2-wrong-past | farm/tpl-chain-response-2-goal~prefreeze | tpl-chain-response-2-goal | right | pass | - | true pass |
| 2-wrong-past | farm/tpl-responded-existence-1-goal~prefreeze | tpl-responded-existence-1-goal | unclear | pass | - | not counted |
| 2-wrong-past | farm/tpl-precedence-2-goal~prefreeze | tpl-precedence-2-goal | right | pass | - | true pass |
| 2-wrong-past | farm/tpl-chain-response-3-nogoal~prefreeze | tpl-chain-response-3-nogoal | wrong | pass | - | FALSE PASS |
| 2-wrong-past | farm/tpl-chain-response-3-nogoal-carry~prefreeze | tpl-chain-response-3-nogoal-carry | wrong | FAIL | solve-s1 | true fail |
| 2-wrong-past | farm/tpl-absence-1-nogoal~kcpagebug | tpl-absence-1-nogoal | wrong | FAIL | wrong-0-s1 | true fail |
| 2-wrong-past | farm/tpl-response-1-goal~kcpagebug | tpl-response-1-goal | wrong | FAIL | solve-s1 | true fail |
| 2-wrong-past | farm/cx-sequence~kcs6r3p2 | cx-sequence | wrong | FAIL | solve-s1 | true fail |
| 2-wrong-past | farm/shop-serve~promisebefore | shop-serve | wrong | FAIL | wrong-1-s1 | true fail |
| 2-wrong-past | farm/tpl-precedence-1-goal~lbO8r1 | tpl-precedence-1-goal | wrong | FAIL | wrong-0-s1 | true fail |
| 3-arm-fm | arm-fm/base-doorkey | base-doorkey | right | pass | - | true pass |
| 3-arm-fm | arm-fm/base-unlock-pickup | base-unlock-pickup | right | pass | - | true pass |
| 3-arm-fm | arm-fm/cx-box | cx-box | right | pass | - | true pass |
| 3-arm-fm | arm-fm/cx-siren | cx-siren | right | pass | - | true pass |
| 3-arm-fm | arm-fm/cx-box-carry | cx-box-carry | right | pass | - | true pass |
| 3-arm-fm | arm-fm/tpl-chain-response-1-goal-carry | tpl-chain-response-1-goal-carry | right | pass | - | true pass |
| 3-arm-fm | arm-fm/tpl-existence-soft-1-goal | tpl-existence-soft-1-goal | right | FAIL | wrong-0-s1 | FALSE FAIL |
| 3-arm-fm | arm-fm/tpl-response-soft-1-goal | tpl-response-soft-1-goal | wrong | FAIL | wrong-0-s1 | true fail |
| 3-arm-fm | arm-fm/tpl-precedence-1-goal | tpl-precedence-1-goal | wrong | FAIL | wrong-0-s1 | true fail |
| 3-arm-fm | arm-fm/tpl-absence-1-nogoal | tpl-absence-1-nogoal | wrong | FAIL | solve-s1 | true fail |
| 3-arm-fm | arm-fm/cx-rules-only | cx-rules-only | wrong | FAIL | wrong-0-s1 | true fail |
| 3-arm-fm | arm-fm/cx-goal-many-rules | cx-goal-many-rules | wrong | FAIL | wrong-0-s1 | true fail |
| 3-arm-fm | arm-fm/tpl-chain-response-2-nogoal-carry | tpl-chain-response-2-nogoal-carry | wrong | FAIL | wrong-4-s1 | true fail |
| 3-arm-fm | arm-fm/shop-serve | shop-serve | wrong | FAIL | solve-s1 | true fail |
| 3-arm-fm | arm-fm/shop-siren | shop-siren | wrong | pass | - | FALSE PASS |
| 3-arm-fm | arm-fm/tpl-response-1-goal~kcpagebug | tpl-response-1-goal | wrong | FAIL | solve-s1 | true fail |
| 4-mutant | farm/tpl-precedence-1-goal~m-dropped-order | tpl-precedence-1-goal | wrong | FAIL | wrong-0-s1 | true fail |
| 4-mutant | farm/tpl-precedence-1-goal~m-swapped-order | tpl-precedence-1-goal | wrong | FAIL | solve-s1 | true fail |
| 4-mutant | farm/tpl-precedence-1-goal~m-well-pays | tpl-precedence-1-goal | wrong | pass | - | FALSE PASS |
| 4-mutant | farm/tpl-absence-1-nogoal~m-dropped-rule | tpl-absence-1-nogoal | wrong | FAIL | wrong-0-s1 | true fail |
| 4-mutant | farm/tpl-absence-1-nogoal~m-no-well | tpl-absence-1-nogoal | wrong | FAIL | wrong-0-s1 | true fail |
| 4-mutant | farm/tpl-absence-soft-1-goal~m-soft-pays-more | tpl-absence-soft-1-goal | wrong | FAIL | wrong-0-s1 | true fail |
| 4-mutant | farm/tpl-existence-soft-1-goal~m-soft-pays-more | tpl-existence-soft-1-goal | wrong | FAIL | wrong-0-s1 | true fail |
| 4-mutant | farm/tpl-existence-two-soft-1-nogoal~m-rule-costs | tpl-existence-two-soft-1-nogoal | wrong | FAIL | wrong-0-s1 | true fail |
| 4-mutant | farm/cx-siren~m-dropped-response | cx-siren | wrong | FAIL | wrong-0-s1 | true fail |
| 4-mutant | farm/tpl-chain-response-1-nogoal-carry~m-well-pays | tpl-chain-response-1-nogoal-carry | wrong | FAIL | wrong-0-s1 | true fail |
| 4-mutant | farm/cx-sequence~m-fact-never | cx-sequence | wrong | FAIL | solve-s1 | true fail |
| 4-mutant | farm/base-unlock-pickup~m-fact-wrong-object | base-unlock-pickup | wrong | FAIL | solve-s1 | true fail |
| 4-mutant | farm/base-doorkey~m-fact-late | base-doorkey | wrong | pass | - | FALSE PASS |
| 4-mutant | farm/shop-serve~m-fact-never | shop-serve | wrong | FAIL | wrong-1-s1 | true fail |
| 4-mutant | farm/cx-goal-many-rules~m-fact-always | cx-goal-many-rules | wrong | FAIL | wrong-0-s1 | true fail |
