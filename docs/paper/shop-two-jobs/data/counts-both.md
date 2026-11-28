# Shop two jobs: FARM against no RM

Same 16 cards, 3 runs each, ppo-shop, 5M steps. A run passes at a judged success of 0.8 or more; a task is learned when 2 of its 3 runs pass. FARM trains with the RM bundle named in the first column, no RM trains without one. Grow is judged at 7x7. Sources: `counts-farm.csv`, `counts-no-rm.csv`.

| Task | RM bundle (FARM) | Shop | FARM runs passing | FARM learned | No RM runs passing | No RM learned |
|---|---|---|---|---|---|---|
| T1 serve + falls | `shop-ladder-deliver` | 3x3 | 3/3 | learned | 3/3 | learned |
| T1 serve + falls | `shop-ladder-deliver` | 5x5 | 3/3 | learned | 2/3 | learned |
| T1 serve + falls | `shop-ladder-deliver` | 7x7 | 2/3 | learned | 2/3 | learned |
| T1 serve + falls | `shop-ladder-deliver` | grow | 3/3 | learned | 2/3 | learned |
| T2 serve + siren | `shop-ladder-deliver-siren` | 3x3 | 3/3 | learned | 0/3 | no |
| T2 serve + siren | `shop-ladder-deliver-siren` | 5x5 | 2/3 | learned | 0/3 | no |
| T2 serve + siren | `shop-ladder-deliver-siren` | 7x7 | 0/3 | no | 0/3 | no |
| T2 serve + siren | `shop-ladder-deliver-siren` | grow | 0/3 | no | 0/3 | no |
| T3 full serve + falls | `shop-serve` | 3x3 | 3/3 | learned | 0/3 | no |
| T3 full serve + falls | `shop-serve` | 5x5 | 0/3 | no | 0/3 | no |
| T3 full serve + falls | `shop-serve` | 7x7 | 0/3 | no | 0/3 | no |
| T3 full serve + falls | `shop-serve` | grow | 0/3 | no | 1/3 | no |
| T4 full serve + siren | `shop-full` | 3x3 | 2/3 | learned | 3/3 | learned |
| T4 full serve + siren | `shop-full` | 5x5 | 0/3 | no | 2/3 | learned |
| T4 full serve + siren | `shop-full` | 7x7 | 0/3 | no | 0/3 | no |
| T4 full serve + siren | `shop-full` | grow | 0/3 | no | 0/3 | no |

**Learned: FARM 8 of 16 cards, no RM 6 of 16 cards.**
