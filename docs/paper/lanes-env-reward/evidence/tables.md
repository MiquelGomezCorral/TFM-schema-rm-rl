# Zombie lanes with the environment's reward added (tables of `check/lanes_env_reward.py`)

Mean over the 3 runs of each method [95% t interval over the runs, low end clipped at 0]; 100 judged episodes per run on reset seeds 2000000..2000099; idle: the judge's idle plan on the same seeds, one fixed policy, so no interval. Every break: the judge's `mean_soft_break_count`. Rules broken at least once: `soft_only.mean_soft_breaks`. Learned: every break and open clauses no more than idle's, one below it, label changes above idle's (user ruling 2026-11-22).

## `tpl-absence-soft-1-nogoal`

| method | runs | kills | top-lane breaches | side-lane breaches | episodes with no top-lane breach (of 100) | every break | rules broken at least once (of 2) | runs learned |
|---|---|---|---|---|---|---|---|---|
| FARM + environment's reward | 3 | 9.63 [9.10, 10.15] | 8.66 [8.64, 8.67] | 8.92 [8.80, 9.03] | 0.0 [0.0, 0.0] | 17.57 [17.46, 17.69] | 2.00 [2.00, 2.00] | 3 of 3 |
| FARM alone | 3 | 7.95 [7.63, 8.26] | 8.61 [8.57, 8.65] | 10.13 [9.92, 10.34] | 0.0 [0.0, 0.0] | 18.74 [18.56, 18.92] | 2.00 [2.00, 2.00] | 3 of 3 |
| No RM | 3 | 17.63 [17.43, 17.82] | 0.53 [0.24, 0.81] | 9.99 [9.91, 10.07] | 63.0 [42.7, 83.3] | 10.52 [10.28, 10.76] | 1.37 [1.17, 1.57] | 3 of 3 |
| Idle (one fixed plan) | - | 0.00 | 8.66 | 17.52 | 0 | 26.18 | 2.00 | - |

| method | run | kills | top | side | no top breach | top count = idle's | every break (idle's 26.18) | rules broken at least once | learned (every-break rule) | folder |
|---|---|---|---|---|---|---|---|---|---|---|
| FARM + environment's reward | seed1 | 9.64 | 8.65 | 8.92 | 0 | 99 | 17.57 | 2.00 | yes | `seed1-20261122T192230-1229365` |
| FARM + environment's reward | seed2 | 9.83 | 8.66 | 8.87 | 0 | 100 | 17.53 | 2.00 | yes | `seed2-20261122T192230-1229366` |
| FARM + environment's reward | seed3 | 9.41 | 8.66 | 8.96 | 0 | 100 | 17.62 | 2.00 | yes | `seed3-20261122T192230-1229368` |
| FARM alone | seed1 | 7.81 | 8.59 | 10.21 | 0 | 95 | 18.80 | 2.00 | yes | `seed1-20261122T063648-681411` |
| FARM alone | seed2 | 8.06 | 8.62 | 10.04 | 0 | 96 | 18.66 | 2.00 | yes | `seed2-20261122T063652-681454` |
| FARM alone | seed3 | 7.97 | 8.62 | 10.14 | 0 | 97 | 18.76 | 2.00 | yes | `seed3-20261122T063737-681862` |
| No RM | seed1 | 17.65 | 0.42 | 10.03 | 70 | 0 | 10.45 | 1.30 | yes | `seed1-20261121T231535-453265` |
| No RM | seed2 | 17.69 | 0.51 | 9.97 | 65 | 0 | 10.48 | 1.35 | yes | `seed2-20261121T231559-453740` |
| No RM | seed3 | 17.54 | 0.65 | 9.98 | 54 | 0 | 10.63 | 1.46 | yes | `seed3-20261121T231704-454970` |

## `tpl-not-co-existence-soft-1-nogoal`

| method | runs | kills | top-lane breaches | side-lane breaches | episodes with no top-lane breach (of 100) | every break | rules broken at least once (of 1) | runs learned |
|---|---|---|---|---|---|---|---|---|
| FARM + environment's reward | 3 | 9.54 [8.97, 10.10] | 8.65 [8.62, 8.68] | 9.02 [8.80, 9.24] | 0.0 [0.0, 0.0] | 5.78 [5.67, 5.88] | 1.00 [1.00, 1.00] | 3 of 3 |
| FARM alone | 3 | 9.05 [7.22, 10.87] | 8.64 [8.56, 8.72] | 9.12 [6.86, 11.39] | 0.0 [0.0, 0.0] | 5.66 [4.56, 6.76] | 1.00 [1.00, 1.00] | 3 of 3 |
| No RM | 3 | 17.63 [17.43, 17.82] | 0.53 [0.24, 0.81] | 9.99 [9.91, 10.07] | 63.0 [42.7, 83.3] | 0.51 [0.21, 0.81] | 0.37 [0.17, 0.57] | 3 of 3 |
| Idle (one fixed plan) | - | 0.00 | 8.66 | 17.52 | 0 | 7.49 | 1.00 | - |

| method | run | kills | top | side | no top breach | top count = idle's | every break (idle's 7.49) | rules broken at least once | learned (every-break rule) | folder |
|---|---|---|---|---|---|---|---|---|---|---|
| FARM + environment's reward | seed1 | 9.79 | 8.64 | 8.98 | 0 | 99 | 5.73 | 1.00 | yes | `seed1-20261122T192230-1229370` |
| FARM + environment's reward | seed2 | 9.47 | 8.66 | 8.96 | 0 | 100 | 5.79 | 1.00 | yes | `seed2-20261122T195646-1303410` |
| FARM + environment's reward | seed3 | 9.35 | 8.64 | 9.12 | 0 | 98 | 5.81 | 1.00 | yes | `seed3-20261122T195646-1303411` |
| FARM alone | seed1 | 9.88 | 8.60 | 8.07 | 0 | 96 | 5.15 | 1.00 | yes | `seed1-20261122T124030-867604` |
| FARM alone | seed2 | 8.77 | 8.65 | 9.62 | 0 | 99 | 5.89 | 1.00 | yes | `seed2-20261122T124030-867605` |
| FARM alone | seed3 | 8.49 | 8.66 | 9.68 | 0 | 100 | 5.94 | 1.00 | yes | `seed3-20261122T124030-867607` |
| No RM | seed1 | 17.65 | 0.42 | 10.03 | 70 | 0 | 0.40 | 0.30 | yes | `seed1-20261121T231535-453265` |
| No RM | seed2 | 17.69 | 0.51 | 9.97 | 65 | 0 | 0.50 | 0.35 | yes | `seed2-20261121T231559-453740` |
| No RM | seed3 | 17.54 | 0.65 | 9.98 | 54 | 0 | 0.64 | 0.46 | yes | `seed3-20261121T231704-454970` |
