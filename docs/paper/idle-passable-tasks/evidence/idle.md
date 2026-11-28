# Idle-passable tasks

Tasks of the group task files at `9841d4b3`. Idle agent: a plan that only waits to the end of the episode (`_IDLE_STEPS`), judged with `judge_trace` on the card's clauses, test seeds 2000000..2000099 (100 episodes). Passes: idle judged success 0.8 or more. Soft-only: no hard clause, so every episode succeeds and the idle soft figures are shown instead.

53 of 124 tasks have no goal (71 have one and are not judged). Of the 53, 45 have a hard clause and 8 are soft-only. Idle passes 18 (18 at exactly 1.00); trained among them: none.

| group | no-goal tasks | with a hard clause | soft-only | idle passes | idle passes at 1.00 |
|---|---|---|---|---|---|
| complex | 1 | 1 | 0 | 1 | 1 |
| templates | 32 | 25 | 7 | 17 | 17 |
| box-carry | 3 | 3 | 0 | 0 | 0 |
| forcing | 4 | 3 | 1 | 0 | 0 |
| forced-start | 2 | 2 | 0 | 0 | 0 |
| shop | 11 | 11 | 0 | 0 | 0 |

| group | ID | rules | trained | idle judged success | passes | idle soft breaks per episode (every break) | idle soft rules unmet per episode |
|---|---|---|---|---|---|---|---|
| complex | `cx-rules-only` | hard+soft | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-existence-1-nogoal` | hard | yes | 0.00 (0/100) | no |  |  |
| templates | `tpl-existence-2-nogoal` | hard | no | 0.00 (0/100) | no |  |  |
| templates | `tpl-existence-3-nogoal` | hard | no | 0.00 (0/100) | no |  |  |
| templates | `tpl-existence-two-1-nogoal` | hard | no | 0.00 (0/100) | no |  |  |
| templates | `tpl-existence-two-2-nogoal` | hard | no | 0.00 (0/100) | no |  |  |
| templates | `tpl-existence-two-3-nogoal` | hard | no | 0.00 (0/100) | no |  |  |
| templates | `tpl-existence-two-5-nogoal` | hard | yes | 0.00 (0/100) | no |  |  |
| templates | `tpl-absence-1-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-absence-2-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-absence-3-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-response-1-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-response-2-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-response-3-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-precedence-1-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-precedence-2-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-precedence-3-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-chain-response-1-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-chain-response-2-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-chain-response-3-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-responded-existence-1-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-responded-existence-2-nogoal` | hard | yes | 0.00 (0/100) | no |  |  |
| templates | `tpl-responded-existence-3-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-not-co-existence-1-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-not-co-existence-2-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-not-co-existence-3-nogoal` | hard | no | 1.00 (100/100) | yes |  |  |
| templates | `tpl-existence-soft-1-nogoal` | soft-only | yes | 1.00 (100/100) | n/a (no hard clause) | 0.00 | 1.00 |
| templates | `tpl-existence-two-soft-1-nogoal` | soft-only | yes | 1.00 (100/100) | n/a (no hard clause) | 0.00 | 1.00 |
| templates | `tpl-absence-soft-1-nogoal` | soft-only | yes | 1.00 (100/100) | n/a (no hard clause) | 26.18 | 2.00 |
| templates | `tpl-precedence-soft-1-nogoal` | soft-only | yes | 1.00 (100/100) | n/a (no hard clause) | 26.18 | 2.00 |
| templates | `tpl-chain-response-soft-1-nogoal` | soft-only | yes | 1.00 (100/100) | n/a (no hard clause) | 1.00 | 1.00 |
| templates | `tpl-responded-existence-soft-1-nogoal` | soft-only | yes | 1.00 (100/100) | n/a (no hard clause) | 0.00 | 1.00 |
| templates | `tpl-not-co-existence-soft-1-nogoal` | soft-only | yes | 1.00 (100/100) | n/a (no hard clause) | 7.49 | 1.00 |
| box-carry | `tpl-chain-response-1-nogoal-carry` | hard | yes | 0.00 (0/100) | no |  |  |
| box-carry | `tpl-chain-response-2-nogoal-carry` | hard | no | 0.00 (0/100) | no |  |  |
| box-carry | `tpl-chain-response-3-nogoal-carry` | hard | no | 0.00 (0/100) | no |  |  |
| forcing | `lanes-guard` | hard | yes | 0.00 (0/100) | no |  |  |
| forcing | `lanes-rules` | hard+soft | yes | 0.00 (0/100) | no |  |  |
| forcing | `keygift-hard` | hard | yes | 0.00 (0/100) | no |  |  |
| forcing | `keygift-soft` | soft-only | yes | 1.00 (100/100) | n/a (no hard clause) | 0.00 | 1.00 |
| forced-start | `tpl-response-1-nogoal-forced` | hard | yes | 0.00 (0/100) | no |  |  |
| forced-start | `tpl-responded-existence-1-nogoal-forced` | hard | no | 0.00 (0/100) | no |  |  |
| shop | `shop-siren` | hard | yes | 0.00 (0/100) | no |  |  |
| shop | `shop-serve` | hard | yes | 0.00 (0/100) | no |  |  |
| shop | `shop-full` | hard | yes | 0.00 (0/100) | no |  |  |
| shop | `shop-quiet-first` | hard | yes | 0.00 (0/100) | no |  |  |
| shop | `shop-boil` | hard | yes | 0.00 (0/100) | no |  |  |
| shop | `shop-pot` | hard | yes | 0.00 (0/100) | no |  |  |
| shop | `shop-ladder-deliver` | hard | no | 0.00 (0/100) | no |  |  |
| shop | `shop-ladder-deliver-siren` | hard | no | 0.00 (0/100) | no |  |  |
| shop | `shop-ladder-order-deliver` | hard | no | 0.00 (0/100) | no |  |  |
| shop | `shop-ladder-order-deliver-siren` | hard | no | 0.00 (0/100) | no |  |  |
| shop | `shop-ladder-serve` | hard | no | 0.00 (0/100) | no |  |  |
