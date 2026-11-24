# Shop world curriculum, 2026-11-23

Goal: one training run whose world changes under the same agent (no slips, then slips, then 25% back falls), so FARM
can learn to serve before the world gets harder. Nothing trained beyond a 150k-step CPU smoke run. Worktree
`tp-shop-curriculum`, branch `feat/shop-curriculum` from main (`ed42365f`),
all changes uncommitted.

## What changed

| File | Change |
|---|---|
| `app/src/arm_fm/curriculum.py` (new) | `WorldCurriculum` (stage, window, switch rule, `stages.csv`, print line) and `WorldStage` (wrapper of each training env: sets the stage's attributes at every reset, counts served / falls / caught from the shop's own events) |
| `app/src/config/config.py` | `env_stages` field and its check (PPO only, no `task_bundles`) |
| `app/src/arm_fm/ppo.py` | builds the curriculum, wraps the training envs only (evaluation keeps the card's world), calls `update` after each vector step, `world_stage` and `world_final_stage` in `summary.json` |
| `app/src/arm_fm/dqn.py` | `env_stages` in `config.yaml`, only when set |
| `app/scripts/run_suite.py` | `run_config` copies the card's `env_stages` into the run config |
| `app/src/arm_fm/shop.py`, `app/src/arm_fm/service_room.py` | `back_fall_chance` option; one hook in the base class (`_fall_draw`) that the shop overrides |
| `experiments/benchmark/shop/tasks.json` | four cards appended (additions only, 466 lines) |
| `experiments/benchmark/shop/runs-curriculum.yaml` (new) | the cluster runs file |
| `experiments/benchmark/shop/README.md` | option 10 (`back_fall_chance`) and a "Curriculum" section |
| `tests/test_world_curriculum.py` (new) | one deterministic test of the switch rule |

Not touched: the shop env pages, bundles, prompts, counted cards, judge, pricing code, `RUN_SETTINGS`, `episodes.csv`
(no stage column: it would change the header of every run; `stages.csv` has the global step of each switch).

## How a stage list is written

`env_stages` in the card's `env` (and in a run config), in order; after the last stage the run plays the card's own
`env_kwargs`:

```json
"env_stages": [
  {"env_kwargs": {"slip_chance": 0.0}, "until": {"served": 10}},
  {"env_kwargs": {"back_fall_chance": 0.0}, "until": {"served": 10, "caught": 0.9}}
]
```

- `env_kwargs`: shop attributes set on every training env at each reset, over the card's own; a key a stage does not set
  goes back to the card's value (stage 2 of the back card has slips at the default chance and no back falls because
  stage 1 only sets `slip_chance` back to the card's value).
- `until.served` (required): least mean served orders per episode. `until.caught` (optional, 0 to 1): least share of
  food falls whose next move picked the food up (`holding_food` right after `food_fell`). `until.episodes` (default
  100): the window.
- The window is the last `episodes` finished training episodes that began in the stage, across all 16 envs. An episode
  plays, and is tagged with, the world it began in: an env resets inside the vector step before the collector updates
  the curriculum, so the 16 episodes that begin on the switch step still play the old stage and the new stage's window
  starts one batch later (about 9,600 steps at 16 envs x 600 steps). A stage whose `caught` goal sees no fall has no
  share and does not switch.
- Stages only move forward. Validation (`config.py`): list of mappings with exactly `env_kwargs` and `until`; unknown
  `until` keys, a missing `served`, a negative or non-finite value, `caught` outside 0 to 1 or `episodes` below 1 are
  refused; `env_stages` needs `algorithm: ppo` and no `task_bundles`. A stage key the env does not have refuses at
  env build (`ValueError`).
- Evaluation during training, the final evaluation, the judge and the gates play the card's own world.

## Where the switch is logged

Run folder `stages.csv`: `global_step, stage, episodes, mean_served, caught_share` (the stage entered and the numbers
that decided it), one row per switch, and a console line `step N: world stage a -> b (...)`. `summary.json` has
`world_stage` (last stage reached; equals `world_final_stage` when the final world was reached) and
`world_final_stage`. `config.yaml` has `env_stages`. A run without stages has none of these.

## The back-fall rule (`back_fall_chance`, default 0)

Per pickup, drawn with the seed, after every other draw of the reset (so event times never move, and 0 is
byte-identical): with chance p the slip is a back fall. The food lands behind the agent and the fall turns the agent a
quarter to the right or left (drawn), so the food is now beside it and one more turn comes before any pickup: the next
move cannot catch it. If the cell behind is blocked, the food takes the next free cell clockwise (left, front, right)
and the agent faces it: a plain slip, which the next move can catch. This is the service room's `fall_turn: side`
rule with behind tried first. Probe (`back_fall_probe.py`, chance 0.25): 305 falls, 243 caught on the next move, 62 not
(20%); `food_fell` and `holding_food` labels fire right.

## Default-unchanged check

`default_hash.py` hashes the episodes (schedules, events, rewards, observations, poses) of 17 configurations: the
default shop, `small`, `easy_start_prob`, `slip_chance` 0.2 and 0, `siren` false, pot, `area` 7 and 3, ladder rung 1,
`client_patience`, and the service room with `box` and the four `fall_turn` modes. Before (unmodified worktree) and
after (all code in place) the 17 hashes are identical (`default-hash-before.txt`, same lines printed after).
`ruff check` and `ruff format --check` pass on the 8 changed Python files, `lint-imports` 2 kept 0 broken,
`git diff --check` clean. Unit tests (`python -m unittest discover -s tests`, from the worktree): 207 run, 2 skipped, 2
failures, both in `test_engines.py` and both an assertion that the repository folder is named `TFM-schema-rm-rl`
(they see `tp-shop-curriculum`); they do not touch the changed code.

## Cards

All four: a copy of the base card with `bundle_of` the base card (its FARM machine, no generation), same task, clauses
and plans, no paraphrases, `train` false, `env_stages` added, `notes` with the user's words.

| Card | Stages | Final world |
|---|---|---|
| `shop-ladder-deliver-curriculum` | no slips | rung 1, slips at 0.5 |
| `shop-ladder-deliver-curriculum-back` | no slips; slips, no back falls | rung 1 + `back_fall_chance` 0.25 |
| `shop-ladder-order-deliver-curriculum` | no slips | rung 3, slips at 0.5 |
| `shop-ladder-order-deliver-curriculum-back` | no slips; slips, no back falls | rung 3 + `back_fall_chance` 0.25 |

## Gates on each card's final world

Tools of `FP/shop-ladder.md`; card-named symlinks to the base machines in `bundles/` so `gate_all.py` matches the card.

| Gate | deliver-curriculum | deliver-curriculum-back | order-deliver-curriculum | order-deliver-curriculum-back |
|---|---|---|---|---|
| `gate_all.py` (pay order, review, plan trace, labeling, plan check, early final, repeat break, wrong plans) | passed 8 of 8 | failed `plan_check` only (7 of 8) | passed 8 of 8 | failed `plan_check` only (7 of 8) |
| trace bank (solve, wrong, idle plans; event seeds 1 to 3) | 9 of 9 ok | 8 of 9: `solve-s2` judged `holds, broken@16` | 12 of 12 ok | 11 of 12: `solve-s2` judged `holds, holds, broken@25` |
| `ladder_check.py` solving worker, 100 seeds: served mean (min), judged | 12.11 (10), 1.00 | 11.92 (10), 0.19 | 11.69 (10), 1.00 | 11.52 (10), 0.21 |
| stock worker: served, judged, ends holding | 15.11, 1.00, 100% | 15.04, 0.04, 100% | 14.61, 1.00, 100% | 14.55, 0.04, 100% |
| `pricing_check.py`, 40 seeds: solve served, plain, discounted | 12.1, 0.0, -0.375 | 5.5, -9.3, -5.069 | 11.7, 0.0, -0.449 | 5.4, -9.0, -4.862 |
| serve one then stop: served, plain, discounted | 1.0, -1.0, -0.841 | 0.78, -3.475, -3.092 | 1.0, -2.0, -1.609 | 0.78, -4.25, -3.594 |
| idle: plain, discounted | -1.0, -0.936 | -1.0, -0.936 | -2.0, -1.872 | -2.0, -1.872 |
| pay per extra served order: plain, discounted | 0.09, 0.042 | -1.233, -0.418 | 0.187, 0.109 | -1.033, -0.276 |

`check_shop.py` (`check-shop-default/`, reset seeds 1 to 100, Shop and Shop-Pot, every card of the file): all checks
passed, 166 ok lines, none failed, including all four new cards (solving plan judged success 100 of 100, wrong plans
break exactly their clauses, doing nothing fails). It plays every card of a level in the world of the level's first card
(`Plays(cards[0].env)`), the default shop, not in the card's own `env_kwargs`, so it says nothing about the back-fall
world; the own-world checks are the trace bank, `plan_check` and `ladder_check` above.

Reading it:

- The two non-back cards behave like their base cards in every gate (same numbers as the stored ladder: 12.11 and
  11.69 served, judged 1.00, same machine pay; the pay per extra order is positive but tiny, so the pricing finding of
  `FP/shop-ladder.md` (net 0 per served order) applies to these runs unchanged).
- On the back cards the plan check fails by design: on event seed 2 the solving plan's first slip is a back fall, the
  worker cannot catch it on the next move and the machine takes the well (step 16 and step 25); the wrong plans then
  "pay not less than" a solving plan that already fell in. Everything else passes (pay order, review, plan trace,
  labeling vs reference, early final, repeat break, wrong plans: each wrong plan breaks exactly the clauses it
  promises).
- **Pricing warning for the back cards.** In their final world the machine pays the scripted solving worker less than
  idling: -9.3 against -1.0 (rung 1) and -9.0 against -2.0 (rung 3). Serving more costs, per extra order, 1.23 and 1.03
  plain. The cause is the well: the scripted worker misses 22% of its falls (below), a run serves about 12 orders with
  about 12 falls, so most runs end in the well at -10 before the end. With this machine the last stage pays idling
  more than serving even for a perfect worker; whether training into it keeps a learned server is the open question
  of the live test. Nothing in pricing, judge or machine code was changed.
- `pricing_check.py` discounts at 0.995 (`ppo-shop.yaml`'s gamma); `ppo-onehot.yaml` has 0.99. Plain sums do not
  depend on it.

### Scripted worker through the real stages (`scripted_stages.py`, real thresholds, `scripted/`)

The scripted solving worker plays each card's real `env_stages` through the real `WorldStage` and `WorldCurriculum`
(served 10, caught 0.9, 100 episodes), one finished episode per update:

| Card | stage 0 (no slips) | stage 1 (slips, no back falls) | final world (300 episodes) |
|---|---|---|---|
| deliver-curriculum | switch at step 60,000, served 12.34, 0 falls | final: served 12.22, 739 falls, caught 1.000 | - |
| deliver-curriculum-back | switch at step 60,000, served 12.34, 0 falls | switch at step 120,000, served 12.22, caught 1.0 | served 11.95, 2,352 falls, caught 0.776 |
| order-deliver-curriculum | switch at step 60,000, served 11.86, 0 falls | final: served 11.71, 708 falls, caught 1.000 | - |
| order-deliver-curriculum-back | switch at step 60,000, served 11.86, 0 falls | switch at step 120,000, served 11.71, caught 1.0 | served 11.46, 2,270 falls, caught 0.774 |

- The switches fire on the card's real goals (10 served, then 10 served and at least 90% caught) and not before: 100
  episodes of 600 steps each, one at a time.
- The wrapper's served count equals the env return of every episode (`env_return_differs_from_served`: 0 of 200 and
  0 of 500 episodes), as the packet asked.
- Stage 0 has 0 falls (slips off); stage 1 has falls and the worker catches all of them; the back-fall world is the only
  one where the worker misses (22.4% and 22.6% of falls, against the 25% drawn because a blocked cell behind makes a
  plain slip).

## Smoke run (CPU, 150k steps, seed 1, `OMP_NUM_THREADS=2`, free RAM 23 GB of 60 at the start)

Settings of `shop-ladder-deliver-curriculum-back` (`ppo-onehot.yaml`, FARM machine of rung 1, 16 envs), `cuda: false`,
goals lowered through a test-only config (`smoke-config-*.yaml`). The untrained agent serves nothing in 150k steps
(`mean_env_return` 0.000 in every evaluation; in run 1 all 240 episodes follow the machine path `u0 u2` and never
leave it), so a goal above 0 is never met and the runs only show the wiring:

| Run | Goals | Result |
|---|---|---|
| `smoke/unreached` (`smoke-config-unreached.yaml`) | served 1.0, then served 1.0 and caught 0.4, window 40 | no switch in 151,552 steps, no `stages.csv`, `world_stage` 0 of 2 in `summary.json`, `config.yaml` has `env_stages` |
| `smoke/floor` (`smoke-config-floor.yaml`) | served 0.0 and window 40 for both stages (no `caught`: an agent that never picks up food has no falls) | both switches fire |

`smoke/floor/stages.csv`:

```
global_step,stage,episodes,mean_served,caught_share
28800,1,40,0.0,
67200,2,40,0.0,
```

Console lines `step 28800: world stage 0 -> 1 (40 episodes, mean served 0.00, caught share None)` and `step 67200: world stage 1 ->
2 (...)`. Step 28,800 is the third batch of 16 episodes finishing (the first with 40 or more in the window); 67,200 is
the third batch of stage-1 episodes (they began at step 38,400, one batch after the switch, as described above). Final
`summary.json`: `world_stage` 2, `world_final_stage` 2, 151,552 steps, final evaluation (card's own world) 0.0 return.
The `caught` path is exercised by the scripted run above, not by this PPO run: no agent that serves was available in
150k steps.

## Runs file

`experiments/benchmark/shop/runs-curriculum.yaml`: suite `shop-curriculum`, FARM only, `ppo-onehot.yaml` (`ram_gb`
3), four cards, seeds `[1, 2, 3]`, 5M steps, 12 runs. Dry run from the worktree
(`env PYTHONPATH=app python app/main.py run-suite --suite experiments/benchmark/shop/runs-curriculum.yaml --dry-run`):
`12 runs: 12 start`, nothing written. The dry run does not build the configs, so each card's real run config (`run_config`)
was also passed through `Configuration` as the driver does before launching: no error for all four cards (1, 2, 1 and 2
stages). `test-rl` loads the smoke run folder with its `env_stages` (5 test episodes).

## Gaps and risks

- No PPO run has crossed a real threshold: the smoke agent never serves. The real goals are shown only with the
  scripted worker. Whether FARM reaches 10 served per episode in the no-slip stage within the 5M steps is the live test.
- Back cards: see the pricing warning above (idle beats a perfect server in the final world); the gate fails the plan
  check by design.
- `env_stages` is in the saved `config.yaml` but not in `RUN_SETTINGS`, so a no-RM shared run would not tell a
  curriculum run from a plain one. The runs file is FARM only; do not run these cards on a no-RM arm.
- `pyright` is not installed in `RM_RL_env`; not run.
- The first stage's world applies to the first reset of each training env (the collector resets the vector env once at
  start); `WorldStage` assumes a plain `SyncVectorEnv` of shop envs (it reads `base.carrying` and `events_this_step`).

## Decision records

`Decision records: update`. The benchmark record's protected invariant "the shop world is the same for every card of
its level" does not describe training worlds that change inside a run (side test, not counted, evaluation and the
judge in the card's own world), and the shop options list gains `back_fall_chance`. Proposed, not written: one dated line
under the shop invariant for `env_stages` and the new option. The main agent owns the record.

## Pending live validation

- Flow: `python app/main.py run-suite --suite experiments/benchmark/shop/runs-curriculum.yaml` (12 runs, FARM,
  `ppo-onehot.yaml`, 5M steps; about 3 h per run from the counted shop-serve runs).
- Expected: per card, `stages.csv` rows that show the switch at served 10 (and, on the back cards, a second one at
  served 10 with 90% caught); final-world evaluation that the judge passes in all 100 episodes for a learned run, judged
  by the card in the card's own world; the two back cards may stay low by the pricing warning.
- Can run: yes once the user approves it; GPU and CPU are shared with 18 other trainings.

## Files kept here (`FP/shop-curriculum/`)

`default_hash.py`, `default-hash-before.txt`, `back_fall_probe.py`, `scripted_stages.py`, `scripted/<card>/`
(`stages.csv`, `summary.json`), `smoke-config-unreached.yaml`, `smoke-config-floor.yaml`, `smoke/` (both run folders and
console logs), `gate/` (`gate_all.py` output), `trace-bank/`, `ladder-check.json` and `ladder-check.txt`,
`pricing-check.json` and `pricing-check.txt`, `bundles/` (card-named symlinks), `check-shop-default/`.
