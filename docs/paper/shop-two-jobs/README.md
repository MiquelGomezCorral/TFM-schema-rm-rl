# Shop, two jobs at once: FARM against no RM

2026-11-27. Open `index.html` from disk (no server): the 16 cards by method, the totals with 95% intervals, and for each of the
four tasks its natural-language text, its LTL clauses and FARM's RM as the interactive `render-rm --html` graph with an "RM text"
fold-out. The page is 0.6 MB because the RM text of `shop-full` is inlined.

## What it shows

Four tasks, each a serving job plus one hard part, at four shop sizes (3x3, 5x5, 7x7 and a grown shop that goes through 3x3, 5x5
and 7x7): 16 cards, 3 runs each, PPO preset `ppo-shop`, 5M steps, for both methods. FARM trains on its RM's reward; no RM trains on
the environment's own reward. The judge plays the final stage (the grown shop at 7x7). A run passes at a judged success of 0.8 or
more; a card is learned when 2 of its 3 runs pass.

| Task | Serving job | Hard part | FARM's RM (bundle) | Cards learned of 4 sizes: FARM / no RM |
|---|---|---|---|---|
| T1 `shop-two-serve-falls-*` | deliver | food falls | `shop-ladder-deliver` | 4 / 4 |
| T2 `shop-two-serve-siren-*` | deliver | siren | `shop-ladder-deliver-siren` | 2 / 0 |
| T3 `shop-two-full-falls-*` | order, cook, deliver | food falls | `shop-serve` | 1 / 0 |
| T4 `shop-two-full-siren-*` | order, cook, deliver | siren | `shop-full` | 1 / 2 |

| Total | FARM | No RM |
|---|---|---|
| Cards learned | 8 of 16 (28.0-72.0%) | 6 of 16 (18.5-61.4%) |
| Runs passing | 21 of 48 (30.7-57.7%) | 15 of 48 (19.9-45.3%) |

Intervals are 95% Wilson (z = 1.959964). Paired on the 16 cards, 3 are learned by FARM only (T2 at 3x3 and 5x5, T3 at 3x3) and 1
by no RM only (T4 at 5x5): McNemar exact p = 0.625 (10/16; 0.63 rounded). The difference is small and the intervals overlap.

## Reading (what the traces show)

- **No RM delivers as much as FARM on T2, but 11 of its 12 runs never press the switch.** At 3x3 no RM serves 21.66 orders per
  episode in all 3 runs, FARM 19.78 to 21.31 (`data/judged.csv`). Of the 12 no-RM runs of T2, 11 never press the switch in any of
  their 100 judged episodes. The exception, 3x3 run 2, answers 8.91 of 9.59 rings per episode but leaves one unanswered at the end
  in 68% of its episodes (`data/rings.csv`).
- **The siren clause has no deadline.** In T2 it is `Response(siren_ringing, switch_toggled)`, hard (`data/tasks.json`). It fails
  only when a ring is still unanswered at the end of the episode.
- **The environment's reward barely fines it.** It fines a ring only when a waiting client hears it past a step limit
  (`app/src/arm_fm/shop.py:506-520`, -0.5 each time). Over the 8 no-RM runs of T2 that never press and still deliver, the fines
  average -0.075 to -1.48 per judged episode, against +19.33 to +21.66 for serving.
- **In cook + siren (T4), the no-RM runs that learn it turn off nearly every ring.** At 3x3 all three answer 11.81 to 11.86 rings
  per episode, every ring they get; at 5x5 the two that learn it answer 9.94 of 10.05 and 10.74 of 10.74. No RM learns T4 at 3x3 (3
  of 3 runs) and 5x5 (2 of 3); FARM learns it at 3x3 (2 of 3) and not at 5x5.

A ring starts when the siren turns on; it is answered when the switch is pressed while it rings. Counts are means over the 100
judged episodes of each run, read from the agent's `agent-traces/ep*.json` (`labels`: `siren_ringing`, `switch_toggled`,
`order_served`; `env_rewards`: the negative part is the fine, the positive part the pay).

## Files

- `index.html`: the page, built by `check/build.py`.
- `data/summary.csv`: one row per card and method: card id, method (`farm`, `no-rm`), runs passing (of 3), learned (1 or 0).
- `data/counts-farm.csv`, `data/counts-no-rm.csv`: one row per run (judged success and pass; the no-RM file adds the mean served
  count); with the `.md` tables `counts-farm.md`, `counts-no-rm.md`, `counts-both.md`.
- `data/judged.csv`: per run, from its `judge.json`: judged success, mean served count, the environment's reward split into pay and
  fines, and the pass rate of each clause of the task.
- `data/rings.csv`: per no-RM run of the two siren tasks, from the judged traces: rings, answered rings, presses, served orders, share
  of episodes ending with a ring unanswered, fines and pay, each per judged episode.
- `data/tasks.json`: for each task its natural-language text, bundle and clauses (template, arguments, priority, LTLf), read from
  `experiments/benchmark/shop/tasks.json` and checked against the FARM judge files.
- `graphs/<bundle>.rm`: FARM's RM text, byte for byte from `experiments/benchmark/shop/bundles/farm/<bundle>/reward_machine.txt`;
  `graphs/<bundle>.html` and `.svg`: its `render-rm` drawing, interactive and static.
- `check/`: the scripts below.

## Rerun

From the repository root, with `python` the `RM_RL_env` Conda env. No model call and no training.

```
python -I docs/paper/shop-two-jobs/check/count_farm.py     # data/counts-farm.csv, counts-farm.md
python -I docs/paper/shop-two-jobs/check/count_no_rm.py    # data/counts-no-rm.csv, counts-no-rm.md, counts-both.md
python -I docs/paper/shop-two-jobs/check/collect.py        # data/judged.csv, data/tasks.json
python -I docs/paper/shop-two-jobs/check/traces.py         # data/rings.csv
PYTHONPATH=app python -P -W ignore docs/paper/shop-two-jobs/check/render_graphs.py   # graphs/ (the shop-full drawing takes about 5 minutes)
python -I docs/paper/shop-two-jobs/check/build.py          # data/summary.csv and index.html
```

The first four read the run folders in `outputs/runs/` (git-ignored, on the computer that trained them); the last two need only
committed files and `data/`. `build.py` recomputes every total, interval and the paired test and stops if one differs from the
values above, or if a figure of the Reading differs from the data.

## Code and commit

The runs came from `python app/main.py run-suite --suite <file>` on `experiments/benchmark/shop/runs-two-farm.yaml` (suite
`shop-two`) and `experiments/benchmark/shop/runs-two-no-rm.yaml` (suite `shop-two-reward`), both added in commit `c7ccde20`
(2026-11-26 08:22). The code and the four FARM bundles are those of commit `48484e55` (2026-11-26 11:08, "data: shop FARM bundles
and promise-cost bundles"): the last commit that touched `app/` or `experiments/benchmark/shop/`, from
`git log -1 --format=%h -- app experiments/benchmark/shop` on 2026-11-27, when no tracked file under those folders had a change.
The first run started after it, on 2026-11-26.
