# Shop two jobs, FARM: runs passing and tasks learned

Suite `shop-two` (FARM, ppo-shop, 5M steps, 3 runs per card). A run passes at a judged success of 0.8 or more; a task is learned when 2 of its 3 runs pass. Built by `count_farm.py` from the `judge.json` files; per-run rows in `counts-farm.csv`.

**Learned: 8 of 16 cards.**

## Cells: runs passing of 3, then learned

| Task | 3x3 | 5x5 | 7x7 | grow |
|---|---|---|---|---|
| T1 serve + falls | 3/3 learned | 3/3 learned | 2/3 learned | 3/3 learned |
| T2 serve + siren | 3/3 learned | 2/3 learned | 0/3 no | 0/3 no |
| T3 full serve + falls | 3/3 learned | 0/3 no | 0/3 no | 0/3 no |
| T4 full serve + siren | 2/3 learned | 0/3 no | 0/3 no | 0/3 no |

## Judged success per run (runs 1, 2, 3)

| Task | 3x3 | 5x5 | 7x7 | grow |
|---|---|---|---|---|
| T1 serve + falls | 1.00, 1.00, 1.00 | 1.00, 1.00, 1.00 | 1.00, 1.00, 0.00 | 1.00, 1.00, 1.00 |
| T2 serve + siren | 1.00, 1.00, 1.00 | 1.00, 1.00, 0.00 | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.00 |
| T3 full serve + falls | 1.00, 1.00, 1.00 | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.00 |
| T4 full serve + siren | 1.00, 0.00, 1.00 | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.00 | 0.00, 0.00, 0.00 |

## Notes

- All 48 runs judged, one judged folder per run.
