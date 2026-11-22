# Fall series: the half world (2026-11-22)

Packet: `fall-half-packet.md`. Worktree `/home/turbotowerlnx/Documents/Master/TFM/wt-fall-half`, branch
`feat/fall-turn-half`, the change in commit `507886e` (local, not merged; parent `029d82c`, main).
Evidence folder: `fall-half/` beside this file (script, raw output, checks).

## What is measured

A fall is **pickable** when, right after it, the box lies in the cell the agent faces, so the very next
move can pick it up. Per world and agent: the share of pickable falls, and the share of episodes (with at
least one fall) where every fall was pickable, the best score an agent can get on the box rule. Each
share carries its 95% Wilson score interval (z = 1.96). Falls in one episode (one or two) are counted as
independent trials, so the fall intervals are a little narrow; the episode intervals have no such issue.

- **Agents.** `solve` is the cards' solving plan (`policy service_room`): it waits in place for each fall,
  in the start corner on the carry cards. `walk` walks the shortest route to the exit (the module's own
  breadth-first planner) and picks the box up whenever it lies on the floor.
- **Seeds** (reset seeds; one seed fixes the whole event schedule): event seeds 1, 2, 3 (plan check and
  trace bank); the judge's 100 test seeds 2000000 to 2000099 (`test-rl` defaults: `--episodes 100`,
  `--seed-base 2000000`); reset seeds 0 to 999.
- **Worlds.** The carry card's world (`carry: true`, box only, `require: [holding_box]`, `max_steps: 200`)
  under `fall_turn` `face`, `none`, `side` and `half`; `right (rejected)`, the rule the packet named, played
  as `none` plus a turn to face a box that landed at the agent's right (it reproduces the numbers the
  temporary in-code version gave); the templates world of `tpl-chain-response-1-goal` (`carry: false`).

## Rates

Raw rows: `fall-half/table.md`. Every fall: `fall-half/falls.json` (step, agent cell, direction, type in
front). Cells read `pickable/total = share [95% CI]`.

| world | agent | seeds | pickable falls [95% CI] | episodes where every fall was pickable [95% CI] |
| --- | --- | --- | --- | --- |
| face | solve | event 1-3 | 4/4 = 100.0% [51.0%, 100.0%] | 3/3 = 100.0% [43.8%, 100.0%] |
| face | solve | judge 2000000-2000099 | 151/151 = 100.0% [97.5%, 100.0%] | 100/100 = 100.0% [96.3%, 100.0%] |
| face | solve | reset 0-999 | 1493/1493 = 100.0% [99.7%, 100.0%] | 1000/1000 = 100.0% [99.6%, 100.0%] |
| face | walk | event 1-3 | 4/4 = 100.0% [51.0%, 100.0%] | 3/3 = 100.0% [43.8%, 100.0%] |
| face | walk | judge 2000000-2000099 | 140/140 = 100.0% [97.3%, 100.0%] | 100/100 = 100.0% [96.3%, 100.0%] |
| face | walk | reset 0-999 | 1341/1341 = 100.0% [99.7%, 100.0%] | 1000/1000 = 100.0% [99.6%, 100.0%] |
| side | solve | event 1-3 | 4/4 = 100.0% [51.0%, 100.0%] | 3/3 = 100.0% [43.8%, 100.0%] |
| side | solve | judge 2000000-2000099 | 151/151 = 100.0% [97.5%, 100.0%] | 100/100 = 100.0% [96.3%, 100.0%] |
| side | solve | reset 0-999 | 1493/1493 = 100.0% [99.7%, 100.0%] | 1000/1000 = 100.0% [99.6%, 100.0%] |
| side | walk | event 1-3 | 2/4 = 50.0% [15.0%, 85.0%] | 2/3 = 66.7% [20.8%, 93.9%] |
| side | walk | judge 2000000-2000099 | 107/142 = 75.4% [67.7%, 81.7%] | 67/100 = 67.0% [57.3%, 75.4%] |
| side | walk | reset 0-999 | 1064/1375 = 77.4% [75.1%, 79.5%] | 715/1000 = 71.5% [68.6%, 74.2%] |
| none | solve | event 1-3 | 3/4 = 75.0% [30.1%, 95.4%] | 2/3 = 66.7% [20.8%, 93.9%] |
| none | solve | judge 2000000-2000099 | 105/151 = 69.5% [61.8%, 76.3%] | 67/100 = 67.0% [57.3%, 75.4%] |
| none | solve | reset 0-999 | 1062/1493 = 71.1% [68.8%, 73.4%] | 660/1000 = 66.0% [63.0%, 68.9%] |
| none | walk | event 1-3 | 1/4 = 25.0% [4.6%, 69.9%] | 1/3 = 33.3% [6.1%, 79.2%] |
| none | walk | judge 2000000-2000099 | 58/142 = 40.8% [33.1%, 49.1%] | 35/100 = 35.0% [26.4%, 44.7%] |
| none | walk | reset 0-999 | 565/1375 = 41.1% [38.5%, 43.7%] | 349/1000 = 34.9% [32.0%, 37.9%] |
| half | solve | event 1-3 | 1/4 = 25.0% [4.6%, 69.9%] | 1/3 = 33.3% [6.1%, 79.2%] |
| half | solve | judge 2000000-2000099 | 81/151 = 53.6% [45.7%, 61.4%] | 39/100 = 39.0% [30.0%, 48.8%] |
| half | solve | reset 0-999 | 771/1493 = 51.6% [49.1%, 54.2%] | 382/1000 = 38.2% [35.2%, 41.3%] |
| half | walk | event 1-3 | 1/4 = 25.0% [4.6%, 69.9%] | 1/3 = 33.3% [6.1%, 79.2%] |
| half | walk | judge 2000000-2000099 | 76/142 = 53.5% [45.3%, 61.5%] | 42/100 = 42.0% [32.8%, 51.8%] |
| half | walk | reset 0-999 | 724/1375 = 52.7% [50.0%, 55.3%] | 420/1000 = 42.0% [39.0%, 45.1%] |
| right (rejected) | solve | event 1-3 | 4/4 = 100.0% [51.0%, 100.0%] | 3/3 = 100.0% [43.8%, 100.0%] |
| right (rejected) | solve | judge 2000000-2000099 | 138/151 = 91.4% [85.8%, 94.9%] | 87/100 = 87.0% [79.0%, 92.2%] |
| right (rejected) | solve | reset 0-999 | 1402/1493 = 93.9% [92.6%, 95.0%] | 909/1000 = 90.9% [89.0%, 92.5%] |
| right (rejected) | walk | event 1-3 | 2/4 = 50.0% [15.0%, 85.0%] | 2/3 = 66.7% [20.8%, 93.9%] |
| right (rejected) | walk | judge 2000000-2000099 | 104/142 = 73.2% [65.4%, 79.8%] | 65/100 = 65.0% [55.3%, 73.6%] |
| right (rejected) | walk | reset 0-999 | 1037/1375 = 75.4% [73.1%, 77.6%] | 703/1000 = 70.3% [67.4%, 73.1%] |
| templates | solve | event 1-3 | 4/4 = 100.0% [51.0%, 100.0%] | 3/3 = 100.0% [43.8%, 100.0%] |
| templates | solve | judge 2000000-2000099 | 151/151 = 100.0% [97.5%, 100.0%] | 100/100 = 100.0% [96.3%, 100.0%] |
| templates | solve | reset 0-999 | 1493/1493 = 100.0% [99.7%, 100.0%] | 1000/1000 = 100.0% [99.6%, 100.0%] |
| templates | walk | event 1-3 | 3/3 = 100.0% [43.8%, 100.0%] | 3/3 = 100.0% [43.8%, 100.0%] |
| templates | walk | judge 2000000-2000099 | 94/123 = 76.4% [68.2%, 83.1%] | 73/100 = 73.0% [63.6%, 80.7%] |
| templates | walk | reset 0-999 | 881/1219 = 72.3% [69.7%, 74.7%] | 684/1000 = 68.4% [65.5%, 71.2%] |

Reading: the user's 100/75/25 for `face`/`side`/`none` holds only on open floor. A blocked landing side
takes the next free one clockwise, so in the start corner (facing right, walls behind and to the left)
three draws in four land in front: the waiting solving plan reads `none` 71% and `side` 100%, the walker
41% and 77%. On the event seeds the solving plan breaks the box rule on `none` seed 1 and `half` seeds 1
and 2, the world's doing.

## The new rule

The packet's rule (front stays, a box at the right turns the agent to face it, left and behind keep the
direction) is the `right (rejected)` row: 94% / 75%, far from 50%, for the wall reason above. Simplest
change that fixes it: `fall_turn: "half"` keeps the shared landing draw of `none` and `side` and uses the
fall's second draw (the one `side` uses for a box behind) as a fair coin: heads, the agent turns to face
the box; tails, it turns to have the box on its right, one turn short of the pickup. That gives about 50%
for both agents (51.6% [49.1, 54.2] and 52.7% [50.0, 55.3] over reset seeds 0 to 999).

Checks:

- Same draws as `none` and `side`: draws, first landing cell and step equal on reset seeds 0 to 999
  (1000/1000); the coin came up heads on 51.9% of first falls (`fall-half/same_landing.py`).
- Existing values unchanged: the 8800 episodes of `face`, `none`, `side` and templates (both agents, all
  seed sets) have the same digest on `029d82c` (`fall-half/before-029d82c/`) and on `507886e`; with the
  rejected row, which derives from `none`, 11000 shared episodes, 0 changed. The rebuilt trace bank left
  every stored trace byte-identical.

Code: `app/src/arm_fm/service_room.py` (docstring, `FALL_TURNS`, `_fall`).

## Rerun

Paths: `W` = `/home/turbotowerlnx/Documents/Master/TFM/wt-fall-half` (or the main checkout once merged; it
needs commit `507886e`), `FP` = `/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl/.git/agent-memory/plans/farm-final-20261119/freeze-prep`,
`PY` = `/home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin/python`. Each line is one command. The results
are deterministic: a rerun gives the same table and digests.

1. Rates, raw falls and digests:
   `env -C W PYTHONPATH=app PY FP/fall-half/fall_half_rates.py --out FP/fall-half`
2. The same on the code before the change, exported to a scratch folder `S`:
   `git -C W archive --output=S/app-029d82c.tar 029d82c app`, then `mkdir -p S/old`, then
   `tar -x -f S/app-029d82c.tar -C S/old`, then
   `env -C S/old PYTHONPATH=app PY FP/fall-half/fall_half_rates.py --out FP/fall-half/before-029d82c`
3. Episodes unchanged:
   `PY FP/fall-half/compare_digests.py FP/fall-half/before-029d82c/digests.json FP/fall-half/digests.json`
4. Shared draws: `env -C W PYTHONPATH=app PY FP/fall-half/same_landing.py`
5. Templates misses: `PY FP/fall-half/missed_falls.py FP/fall-half/falls.json templates walk`
6. Trace bank (needs `RM_RL_env/bin` and `~/.local/bin` on PATH):
   `env -C W PYTHONPATH=app PATH=/home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin:/home/turbotowerlnx/.local/bin:/usr/bin:/bin PY app/main.py trace-bank --tasks experiments/benchmark/box-carry/tasks.json --output experiments/benchmark/box-carry/traces`
7. Dry runs: `env -C W PYTHONPATH=app PATH=<as in 6> PY app/main.py run-suite --suite FP/<arm>/box-carry-half.yaml --dry-run`

## Card and runs

- Card `tpl-chain-response-1-goal-carry-half` in `experiments/benchmark/box-carry/tasks.json`: copy of
  `-noturn` (`bundle_of` `tpl-chain-response-1-goal-carry`, same task, clauses, plans, no paraphrases),
  only `fall_turn: half`. Trace bank rebuilt for box-carry: 10 cards, 168/171 plans ok; the 3 fails are
  the solving plan on `-noturn` seed 1 and `-half` seeds 1 and 2. Every wrong plan of the new card breaks
  what its `breaks` says.
- `runs-fall-turn.yaml` now lists the three world copies (9 FARM runs; dry run from the worktree: 9 start).
- Training copies (3 seeds, 1.5M steps, `only:` the new card), each dry-run from the worktree, output
  beside it:
  - `farm/box-carry-half.yaml`: 3 runs, 3 start. FARM has no `box-carry-60.yaml`; settings copied from
    `runs-fall-turn.yaml`, which the -60 copies name as their source.
  - `arm-fm/box-carry-half.yaml`: 3 runs, 3 start (trains on arm-fm/`tpl-chain-response-1-goal-carry`).
  - `no-rm/box-carry-half.yaml`: 3 runs, 3 start.
- The card exists only on `feat/fall-turn-half`: merge before launching from the main checkout.

Docs: `box-carry/README.md` (card, rule, rate table), `envs/service-room-carry/environment-code.md`,
`docs/decisions/benchmark/thesis-benchmark.md` (Box-carry cards and a 2026-11-22 entry).
`docs/decisions/index.md` lists no fall worlds: no change.

## The templates world

Yes, it differs. `tpl-chain-response-1-goal` runs `carry: false`:

- The box starts on the floor at (4, 2). A fall comes 2 to 6 steps after each pickup (the n-th pickup
  schedules the n-th planned fall), so an agent that never picks the box up never meets the rule; the
  carry worlds start with the box in hand and the first fall at a step from 2 to 8.
- The drop action works, so a fall can be dodged by putting the box down first; in the carry worlds it
  does nothing before the first fall.
- The box lands in the first free cell from the front clockwise, as with `face`, but the agent never
  turns (`face_fallen = carry`). So it is `face` without the turn: the next-move pickup works when the
  cell in front is free and fails when it is not. The solving plan waits where it picked the box up, so
  the front is the cell the box left (100%). The walker missed 338 of 1219 falls over reset seeds 0 to
  999: 251 at (4, 6) facing the bottom wall, 87 at (5, 6) facing the exit cell (rerun step 5).
