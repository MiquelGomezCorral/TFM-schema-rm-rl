# Shop two jobs, no RM: runs passing and tasks learned

Suite `shop-two-reward` (no RM, env reward only, ppo-shop, 5M steps, 3 runs per card). A run passes at a judged success of 0.8 or more; a task is learned when 2 of its 3 runs pass. Built by `count_no_rm.py` from the `judge.json` files; per-run rows in `counts-no-rm.csv`.

**Learned: 6 of 16 cards.**

## Cells: runs passing of 3, then learned

| Task | 3x3 | 5x5 | 7x7 | grow |
|---|---|---|---|---|
| T1 serve + falls | 3/3 learned | 2/3 learned | 2/3 learned | 2/3 learned |
| T2 serve + siren | 0/3 no | 0/3 no | 0/3 no | 0/3 no |
| T3 full serve + falls | 0/3 no | 0/3 no | 0/3 no | 1/3 no |
| T4 full serve + siren | 3/3 learned | 2/3 learned | 0/3 no | 0/3 no |

## Judged success per run (runs 1, 2, 3)

| Task | 3x3 | 5x5 | 7x7 | grow |
|---|---|---|---|---|
| T1 serve + falls | 1.00, 1.00, 1.00 | 1.00, 0.13, 1.00 | 1.00, 0.00, 1.00 | 1.00, 0.00, 1.00 |
| T2 serve + siren | 0.00, 0.32, 0.00 | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.00 |
| T3 full serve + falls | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.03 | 0.00, 0.00, 0.00 | 1.00, 0.00, 0.00 |
| T4 full serve + siren | 1.00, 1.00, 1.00 | 0.00, 0.89, 1.00 | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.00 |

## Mean served count per run (runs 1, 2, 3)

Orders served per judged episode, from `mean_served_count` in the judge file.

| Task | 3x3 | 5x5 | 7x7 | grow |
|---|---|---|---|---|
| T1 serve + falls | 21.16, 21.59, 21.59 | 19.99, 20.19, 20.35 | 19.27, 0.00, 19.27 | 18.71, 0.00, 19.27 |
| T2 serve + siren | 21.66, 21.66, 21.66 | 20.38, 20.32, 20.40 | 19.33, 0.00, 19.34 | 0.42, 0.06, 19.36 |
| T3 full serve + falls | 16.31, 2.18, 1.39 | 0.00, 0.47, 12.64 | 0.00, 0.00, 0.00 | 9.11, 0.00, 0.00 |
| T4 full serve + siren | 16.25, 16.19, 15.65 | 0.00, 8.66, 11.71 | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.00 |

## Notes

- All 48 runs judged, one judged folder per run.
