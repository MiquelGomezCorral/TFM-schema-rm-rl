| group | arm | bundles | RM accepted | RM tries (accepted) | RM tries (all) | RM tries from | labeling accepted at generation | labeling tries | labeling regenerated accepted | regeneration tries | labeling ok after repair | repair rounds | restored from log |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ablation | farm | 18 | 18/18 | 1 | 1 | run stats 18 | 18/18 | 2 | 0/0 | - | 0/0 | - | 12 |
| all main suites | arm-fm | 124 | 121/124 | 2.42 | 2.6 | run stats 124 | 98/121 | 1.55 | 0/0 | - | 124/124 | 2.69 | 0 |
| all main suites | farm | 124 | 124/124 | 1.23 | 1.23 | run stats 124 | 97/124 | 1.27 | 118/124 | 1.25 | 123/124 | 3.83 | 27 |
| base | arm-fm | 4 | 4/4 | 1.75 | 1.75 | run stats 4 | 4/4 | 1.25 | 0/0 | - | 4/4 | - | 0 |
| base | farm | 4 | 4/4 | 1 | 1 | run stats 4 | 3/4 | 1.33 | 4/4 | 1 | 4/4 | - | 1 |
| box-carry | arm-fm | 16 | 16/16 | 3.44 | 3.44 | run stats 16 | 16/16 | 1.06 | 0/0 | - | 16/16 | - | 0 |
| box-carry | farm | 16 | 16/16 | 1.25 | 1.25 | run stats 16 | 16/16 | 1 | 0/0 | - | 16/16 | - | 0 |
| complex | arm-fm | 24 | 24/24 | 2.42 | 2.42 | run stats 24 | 16/24 | 1.79 | 0/0 | - | 24/24 | 1.78 | 0 |
| complex | farm | 24 | 24/24 | 1.38 | 1.38 | run stats 24 | 19/24 | 1.68 | 23/24 | 1.29 | 24/24 | 3 | 5 |
| forced-start | arm-fm | 8 | 8/8 | 2.38 | 2.38 | run stats 8 | 6/8 | 1.88 | 0/0 | - | 8/8 | 2 | 0 |
| forced-start | farm | 8 | 8/8 | 1.25 | 1.25 | run stats 8 | 7/8 | 1.62 | 0/0 | - | 8/8 | 2 | 0 |
| pilot | farm | 2 | 2/2 | 1 | 1 | attempts.json 2 | 2/2 | 1 | 0/0 | - | 2/2 | - | 0 |
| templates | arm-fm | 96 | 93/96 | 2.45 | 2.69 | run stats 96 | 78/93 | 1.49 | 0/0 | - | 96/96 | 3.1 | 0 |
| templates | farm | 96 | 96/96 | 1.21 | 1.21 | run stats 96 | 75/96 | 1.16 | 91/96 | 1.25 | 95/96 | 4.25 | 21 |

- RM tries (all): mean over the bundles with at least one try; a bundle with 0 tries is left out.
- labeling tries: original generation only (the regeneration sidecar's previous attempts); restored bundles whose log has no per-try labeling lines are left out of the mean.
- labeling regenerated accepted: bundles accepted out of those a regeneration loop ran on; regeneration tries: mean tries of the latest loop.
- repair rounds: mean over the failed check records with at least one round; a failed record with 0 rounds is left out, though it stays in the ok-after-repair denominator.
