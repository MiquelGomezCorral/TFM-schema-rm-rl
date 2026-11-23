# ARM-FM baseline results (option B)

Written by `build.py` from the raw run folders under `outputs/runs/`; do not edit. Score: the judge's
`mean_judged_success` of each seed's run (share of judged episodes the judge counts as solved). Every cell
has exactly seeds 1, 2 and 3, except the DoorKey 16x16 fixed row of test 1 (counted over runs, see there).
The CI is over the 3 seeds: Student t with n - 1 = 2 degrees of freedom,
clipped to [0, 1]. Every card's task, LTL and both machines: [cards.md](cards.md). The 22 generated
machines (11 FARM, 11 ARM-FM) passed the B4 gate: [evidence/b4-gate.md](evidence/b4-gate.md).

## Test 1: ARM-FM paper tasks (MiniGrid, suite `armfm-paper`)

Each run judged by its own judge. A fixed-map card trains and is judged on its one map, so its judge
plays 1 episode and scores 0 or 1.

Cells: mean [95% CI over the 3 seeds, Student t, n - 1 = 2] (seeds 1, 2, 3).
DoorKey 16x16 fixed cells: share of training runs judged successful [95% Wilson interval] (runs judged successful of training runs).

| Card | Steps | Judged episodes | FARM | ARM-FM | no RM |
|---|---|---|---|---|---|
| [armfm-doorkey-5x5](cards.md#armfm-doorkey-5x5) | 1.5M | 100 | 1.00 [1.00, 1.00] (1.00, 1.00, 1.00) | 1.00 [1.00, 1.00] (1.00, 1.00, 1.00) | 1.00 [1.00, 1.00] (1.00, 1.00, 1.00) |
| [armfm-doorkey-5x5-fixed](cards.md#armfm-doorkey-5x5-fixed) | 1.5M | 1 | 1.00 [1.00, 1.00] (1.00, 1.00, 1.00) | 1.00 [1.00, 1.00] (1.00, 1.00, 1.00) | 1.00 [1.00, 1.00] (1.00, 1.00, 1.00) |
| [armfm-doorkey-8x8-fixed](cards.md#armfm-doorkey-8x8-fixed) | 1.5M | 1 | 1.00 [1.00, 1.00] (1.00, 1.00, 1.00) | 1.00 [1.00, 1.00] (1.00, 1.00, 1.00) | 1.00 [1.00, 1.00] (1.00, 1.00, 1.00) |
| [armfm-doorkey-16x16](cards.md#armfm-doorkey-16x16) | 5M | 100 | 0.95 [0.90, 1.00] (0.95, 0.93, 0.97) | 0.89 [0.73, 1.00] (0.86, 0.84, 0.96) | 0.00 [0.00, 0.00] (0.00, 0.00, 0.00) |
| [armfm-doorkey-16x16-fixed](cards.md#armfm-doorkey-16x16-fixed) | 5M | 1 | 0.75 [0.41, 0.93] (6 of 8 runs) | 0.75 [0.41, 0.93] (6 of 8 runs) | 0.00 [0.00, 0.56] (0 of 3 runs) |
| [armfm-unlock-to-unlock](cards.md#armfm-unlock-to-unlock) | 5M | 100 | 0.99 [0.97, 1.00] (0.99, 0.99, 0.98) | 0.95 [0.94, 0.97] (0.95, 0.95, 0.96) | 0.00 [0.00, 0.00] (0.00, 0.00, 0.00) |

**DoorKey 16x16 fixed, 8 training runs per method.** FARM and ARM-FM have 8 runs each: the first
3 from suite `armfm-paper`, the other 5 from suite `armfm-paper-rerun` (same card, machines,
`ppo.yaml` and 5M steps; runs file `experiments/benchmark/armfm-paper/runs-doorkey-fixed-seeds.yaml`).
No RM keeps its original 3 runs (0 of 3). The judge plays the one map once, so a run
counts as a success when that episode is judged solved (`mean_judged_success` = 1: goal reached, every
expected clause holds) and scores 0 otherwise. The row counts such runs, with a 95% Wilson interval.

With the first 3 runs FARM looked worse on this map (2 of 3 against 3 of 3);
with 8 runs both succeed 6 times (0.75 [0.41, 0.93] each), so the gap was run-to-run variance on a hard
fixed layout. The card's task, LTL and both machines: [cards.md](cards.md#armfm-doorkey-16x16-fixed).

One failed FARM `armfm-doorkey-16x16-fixed` run, recounted from its `episodes.csv`: all 1952 training episodes ran
to the step limit (2560) without reaching the goal, 1949 in machine state u1 (key held) and 3 in u0 (no key);
none opened the door. Other FARM runs of the card solve the same map on the same machine: an
exploration failure of this run, not a machine fault.

## Test 2: XLand single tasks (suite `xland`)

Cells: mean [95% CI over the 3 seeds, Student t, n - 1 = 2] (seeds 1, 2, 3).

| Card | Steps | Judged episodes | FARM | ARM-FM | no RM |
|---|---|---|---|---|---|
| [xland-x1-197](cards.md#xland-x1-197) | 5M | 100 | 0.85 [0.78, 0.93] (0.88, 0.86, 0.82) | 0.77 [0.63, 0.91] (0.71, 0.78, 0.82) | 0.75 [0.72, 0.79] (0.74, 0.77, 0.75) |
| [xland-zc](cards.md#xland-zc) | 5M | 100 | 0.82 [0.80, 0.84] (0.83, 0.81, 0.82) | 0.77 [0.73, 0.80] (0.75, 0.77, 0.78) | 0.69 [0.58, 0.80] (0.73, 0.70, 0.64) |

## Test 3: XLand mixes, judged per member card

One policy per mix and seed, judged on each member card; the machine arms with their own machine of that
card.

Cells: mean [95% CI over the 3 seeds, Student t, n - 1 = 2] (seeds 1, 2, 3).

| Mix | Card | Steps | Judged episodes | FARM | ARM-FM | no RM |
|---|---|---|---|---|---|---|
| xland-mix3 | [xland-x1-197](cards.md#xland-x1-197) | 5M | 100 | 0.81 [0.73, 0.89] (0.85, 0.79, 0.80) | 0.61 [0.46, 0.76] (0.60, 0.67, 0.55) | 0.15 [0.03, 0.28] (0.13, 0.21, 0.12) |
| xland-mix3 | [xland-x2-212](cards.md#xland-x2-212) | 5M | 100 | 0.80 [0.69, 0.92] (0.83, 0.75, 0.83) | 0.52 [0.23, 0.81] (0.50, 0.65, 0.42) | 0.14 [0.00, 0.35] (0.09, 0.24, 0.10) |
| xland-mix3 | [xland-x3-260](cards.md#xland-x3-260) | 5M | 100 | 0.80 [0.72, 0.87] (0.78, 0.83, 0.78) | 0.55 [0.40, 0.70] (0.56, 0.61, 0.49) | 0.22 [0.04, 0.41] (0.18, 0.31, 0.18) |
| xland-mix5 | [xland-x1-197](cards.md#xland-x1-197) | 5M | 100 | 0.80 [0.78, 0.82] (0.80, 0.79, 0.81) | 0.29 [0.04, 0.54] (0.35, 0.34, 0.17) | 0.02 [0.00, 0.03] (0.01, 0.02, 0.02) |
| xland-mix5 | [xland-x2-212](cards.md#xland-x2-212) | 5M | 100 | 0.61 [0.52, 0.70] (0.63, 0.57, 0.63) | 0.09 [0.06, 0.12] (0.10, 0.08, 0.08) | 0.01 [0.00, 0.03] (0.01, 0.02, 0.01) |
| xland-mix5 | [xland-x3-260](cards.md#xland-x3-260) | 5M | 100 | 0.67 [0.59, 0.76] (0.64, 0.71, 0.67) | 0.28 [0.15, 0.41] (0.30, 0.32, 0.22) | 0.08 [0.00, 0.18] (0.10, 0.04, 0.11) |
| xland-mix5 | [xland-x4-859](cards.md#xland-x4-859) | 5M | 100 | 0.76 [0.63, 0.88] (0.77, 0.80, 0.70) | 0.31 [0.16, 0.46] (0.34, 0.35, 0.24) | 0.06 [0.00, 0.19] (0.00, 0.09, 0.09) |
| xland-mix5 | [xland-x5-594](cards.md#xland-x5-594) | 5M | 100 | 0.66 [0.48, 0.84] (0.71, 0.70, 0.58) | 0.14 [0.05, 0.23] (0.13, 0.11, 0.18) | 0.04 [0.00, 0.15] (0.00, 0.03, 0.09) |

## Test 4: zero-shot on ZC

Trained on the mix ZA+ZB, judged on the unseen ZC (machine arms with their own ZC machine). The runs
trained on ZC itself are in test 2.

Cells: mean [95% CI over the 3 seeds, Student t, n - 1 = 2] (seeds 1, 2, 3).

| Trained on | Card | Steps | Judged episodes | FARM | ARM-FM | no RM |
|---|---|---|---|---|---|---|
| xland-za+xland-zb | [xland-zc](cards.md#xland-zc) | 5M | 100 | 0.69 [0.21, 1.00] (0.79, 0.47, 0.82) | 0.58 [0.38, 0.78] (0.61, 0.64, 0.49) | 0.02 [0.00, 0.05] (0.03, 0.01, 0.01) |

## Test 5: ARM-FM ablations on the 5-task mix

ARM-FM only, judged per member card with the ARM-FM machine. Default = the ARM-FM mix5 runs of test 3;
no embeddings = `rm_state_encoding: none` (the machine pays, the policy does not see its state); no RM
reward = `reward_source: env_rm_state` (the environment alone pays, the machine only feeds its state
and ends no episode).

Cells: mean [95% CI over the 3 seeds, Student t, n - 1 = 2] (seeds 1, 2, 3).

| Card | Steps | Judged episodes | default | no embeddings | no RM reward |
|---|---|---|---|---|---|
| [xland-x1-197](cards.md#xland-x1-197) | 5M | 100 | 0.29 [0.04, 0.54] (0.35, 0.34, 0.17) | 0.16 [0.03, 0.30] (0.10, 0.19, 0.20) | 0.08 [0.00, 0.24] (0.06, 0.15, 0.02) |
| [xland-x2-212](cards.md#xland-x2-212) | 5M | 100 | 0.09 [0.06, 0.12] (0.10, 0.08, 0.08) | 0.14 [0.00, 0.33] (0.07, 0.22, 0.13) | 0.02 [0.00, 0.05] (0.00, 0.03, 0.02) |
| [xland-x3-260](cards.md#xland-x3-260) | 5M | 100 | 0.28 [0.15, 0.41] (0.30, 0.32, 0.22) | 0.25 [0.03, 0.47] (0.20, 0.35, 0.20) | 0.16 [0.09, 0.23] (0.16, 0.13, 0.19) |
| [xland-x4-859](cards.md#xland-x4-859) | 5M | 100 | 0.31 [0.16, 0.46] (0.34, 0.35, 0.24) | 0.23 [0.15, 0.30] (0.22, 0.26, 0.20) | 0.14 [0.00, 0.35] (0.09, 0.24, 0.10) |
| [xland-x5-594](cards.md#xland-x5-594) | 5M | 100 | 0.14 [0.05, 0.23] (0.13, 0.11, 0.18) | 0.10 [0.00, 0.28] (0.02, 0.17, 0.10) | 0.06 [0.02, 0.09] (0.06, 0.04, 0.07) |
