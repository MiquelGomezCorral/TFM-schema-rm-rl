# Why FARM never serves on shop ladder rung 1 (2026-11-23)

Card `shop-ladder-deliver`: "Whenever a client comes in, fetch food from the pantry and give it to them; if the
food falls, pick it up on your very next move." Clauses `Response(client_arrived, order_served)` and
`ChainResponse(food_fell, holding_food)`, both hard. Read-only diagnosis; no training, no model call.

## Verdict

The machine's logic and labeling are right. Its **pay** traps the learner. With this pay, sitting idle is the best
policy a learner can reach by small steps: every server that sometimes misses a slip scores far below idle. FARM
learns to leave the food alone in the first ~50k steps and never finds the serving policy.

- **Side:** the pipeline's reward layer. The well charge (-10, or -70 with promise cost) meets the env rule that
  the first pickup of every episode always slips, and a served order pays net 0. RL difficulty makes it worse. It
  is not the LLM (clauses exact), not labeling, and not the PPO settings.
- **Gate:** the C8 hold ("pricing-no-growth") was right, and training now confirms it. Rung 1 must not train on
  this pay.

The FARM optimum exists. It is the policy the no-RM learner found: that policy catches 4,938 of 4,938 slips on the
next move, and the FARM machine pays it 0 (discounted -0.12 to -0.18), against -1 (-0.94) for FARM's own idle policy.

## Ranked causes

| # | Cause | Evidence | Side | Cheapest test |
|---|---|---|---|---|
| 1 | **Fear valley.** A missed catch is the well (-10, -70 with promise cost) and ends the episode. The first pickup always slips, so every food-handling episode of a learner without the reflex hits it. | Machine return through the training env: idle -1 (disc -0.94), a server catching slips with chance 0.5 / 1/7 / 0 scores -12 (disc -8.5 / -10.4 / -10.8), a perfect server 0 (disc -0.38). Random play: 8 of 30 episodes reach the well, return -3.9. Training: food-fall episodes go from 0-31% of each run's first 16 episodes to 3.7-8.4% in the first 50k steps, then 0.2-1.3%. | Pipeline pay, with the env's forced first slip | FARM rung 1 with `slip_chance: 0` in `env_kwargs`, one seed, 1M steps, std settings (`ppo-onehot.yaml`): ~26-40 min, ~3 GB. It serves: cause 1 confirmed. It never serves by 1M: cause 2 is enough on its own. |
| 2 | **No pay growth.** Arrival charges -1 and the serve refunds it, with no waiting cost (plain). | The whole gain from idle to perfect is +1 plain (+0.57 disc) per episode, 0.04 disc per extra order (`FP/shop-ladder/pricing-check.json`). A serve moves the machine u2 to u0, which re-arms the next arrival's -1 10-40 steps later, so its advantage is about 1 - gamma^gap = 0.05-0.18 (gamma 0.995) or 0.10-0.33 (gamma 0.99). The no-RM learner gets about 1. | Pipeline pay | Only if test 1 never serves: the same run with `reward_source: both` (env +1 per serve on top), one seed, 1M steps. |
| 3 | **A legal serve is rare by chance.** It needs every slip caught. | Random play catches 3 of 11 slips (uniform pickup chance 1/7) and serves 0 of 30 episodes in both arms. No-RM's first serve came at 134k / 317k / 797k steps. A FARM-legal serve is at least 4-7x rarer, and avoidance (cause 1) cuts food handling another 5-20x. | RL difficulty | Covered by test 1. |
| - | Training setup: ruled out | The std run uses no-RM's exact PPO settings (gamma 0.99, clip 0.1; only the reward source and the one-hot RM input differ). It has 0 serves over 2.3M steps on 3 seeds; all three no-RM seeds had served by 797k. Its entropy stays at 1.65-1.84 after the first 50k steps (no collapse): it explores, but not with food. No-RM has no RM wrapper, so its `time_limit_penalty: -5` never applies. | - | - |
| - | Labeling or wrapper: ruled out | See "Labeling" below. | - | - |
| - | LLM machine: ruled out | Clauses exact (C2 scorer). The transitions follow the instruction. The no-RM policy keeps both clauses on all 300 greedy episodes. | - | - |

## 1. Exploration before any learning

Uniform random policy, reset seeds 1-30, through `make_run_environment` from each run's own `run-config.yaml`
(`ladder-noserve/probe.py`, output `ladder-noserve/probe.txt`). Means per episode:

| Env | Steps | Pickups | Slips | Caught next move | Served | Wells | Learner return (disc) |
|---|---|---|---|---|---|---|---|
| FARM plain | 497 | 0.70 | 0.37 | 0.10 | 0 (0/30 ep) | 0.27 | -3.90 (-2.37) |
| FARM promise cost | 497 | 0.70 | 0.37 | 0.10 | 0 | 0.27 | -68.19 (-25.64) |
| no RM | 600 | 1.97 | 0.73 | 0.17 | 0 (0/30 ep) | - | 0 (0) |

- A random agent does not serve in 30 episodes. That fits no-RM's first serve at 134k-797k steps (224-1,328
  episodes).
- For the FARM learner, 27% of random episodes end in the well, about 2.9 below idle each. No-RM sees no cost.
- The untrained PPO policy is almost uniform: entropy 1.90-1.94 at the first update (ln 7 = 1.95). So the random
  rows stand for it, and it was not played separately.
- Rows of the runs' first 16 episodes (one per env, before learning shows) agree: wells in 0-31% of episodes
  (mean 17%), no serve.

## 2. The reward each learner sees around a serve

The same probe gives the scripted solving worker, seed 1, step by step (`probe.txt`, the "event steps" blocks):

- **FARM plain:** arrive -1 (u0 to u2); slip -1 (u3); next-move pickup +1 (u2); serve +1 (u0) on the step where the
  env pays 1. Net 0 per order. 12.2 served per episode, return 0 (disc -0.38), no well on 30 seeds.
- **Promise cost:** the same, plus -0.1 per step owed; the slip is -1.1, the catch +0.9, the serve +0.9. Return
  -20.03 (disc -7.60). An episode that never touches food scores -59.95 (disc -18.94; smoke run, seeds 1-2).
- **No RM:** +1 at each serve, nothing else. A slip costs nothing, and the food can be picked up any time later.
- **Seed configs, FARM against no-RM:** they differ only in `reward_source` rm/env, `bundle`, `time_limit_penalty`
  0/-5 (unused without an RM), gamma 0.995/0.99 and clip 0.2/0.1 (the std run matches no-RM on both), and
  `rm_state_encoding` one_hot/embedding (unused without an RM). Promise cost against plain: only the bundle differs.
- **Bundle settings** (`manifest.json` `effective_settings`): `reward_progress`, `reward_well`, hard charge -10, no
  end judgment, no time-limit term (`time_limit_penalty: 0`). No shaping term is left out of the numbers above.

The scripted worker with a coin for the reflex shows the valley. The same 30 seeds, return and discounted return:

| Catches a slip on the next move | FARM plain | FARM promise cost | no RM (served) |
|---|---|---|---|
| always (solving worker) | 0 (-0.38) | -20.0 (-7.6) | 12.2 |
| chance 0.5 | -12 (-8.5) | -75.5 (-52.6) | 12.1 |
| chance 1/7 (random) | -12 (-10.4) | -73.2 (-63.3) | 12.0 |
| never | -12 (-10.8) | -72.9 (-65.3) | 12.0 |
| idle (`pricing-check.json`) | -1 (-0.94) | about -60 (-19) | 0 |

- With about 7.5 slips per episode, a server must catch nearly all of them (chance^7.5 of a clean episode) before
  serving beats idle.
- No-RM pays the same partial servers 12 orders whatever their reflex, so its learner never needs the reflex to
  improve. It learns the reflex anyway as the fastest way to serve.

## 3. The learning curve

From each run's `episodes.csv`, `train.csv` and greedy test traces (`ladder-noserve/curves.py`, output
`ladder-noserve/curves.txt`):

| Run (3 seeds each) | Episodes | Food-fall ep: first 16 / first 50k / after 500k | Catches (u3 to u2) | Wells | Served ep |
|---|---|---|---|---|---|
| ppo-shop, plain | 8,339-8,351 | 0-25% / 3.7-4.9% / 0.2-0.6% | 2-11 per run | 29-44 | 0 |
| ppo-shop, promise cost | 8,344-8,356 | 12.5-25% / 3.7-6.2% / 0.3-0.8% | 2-36 per run | 35-49 | 0 |
| std (ppo-onehot), at 2.3M | 3,870-3,892 | 12.5-31% / 4.9-8.4% / 0.2-0.6% | 1-3 per run | 18-23 | 0 |
| no RM | 8,320 | (no machine path) | - | - | 5,037-8,037 |

- Food-fall episodes run from the first 2k-11k steps to the end, as the packet says. Their share falls about
  tenfold in the first 500k steps: that is learned avoidance. In one promise-cost seed, 35 of the 39 food-fall
  episodes after 2M steps include a catch, and it still never serves.
- **Greedy test traces** (100 episodes per finished FARM seed): 0% of steps holding food. Not one episode picks food
  up, so none serves and none sees a slip. Each seed repeats one action that does nothing all episode: drop with
  empty hands, done, pickup facing nothing, or toggle. The machine sits in u2 from the first arrival (return -1).
- **No-RM greedy traces:** 73% of steps holding food, 17-18 served, all 4,938 slips caught on the next move.
- Entropy at 1M steps: ppo-shop FARM 1.54-1.63, std FARM 1.73-1.80, no-RM 0.83-1.70. FARM is not frozen: it moves at
  random but keeps away from food.

## 4. The labeling, on the training path

The scripted worker through `make_run_environment` (the training wrapper, not the gate tools), seed 1. On every
serve step `order_served` fires on the same step the env pays 1, and the machine goes u2 to u0 with +1. On every
slip `food_fell` sends it to u3 (-1). The next-move pickup sets `holding_food` and returns it to u2 (+1). Over 30
seeds: 12.2 served, 7.5 slips, all caught, no well, return 0 / -0.38 discounted. This matches the gate's pricing
table (12.2, 0.0, -0.38). The labeling is right.

## The no-RM policy scored by the FARM machines

The labels of the 300 no-RM greedy test episodes, replayed through both FARM machines and cut at the well
(`ladder-noserve/replay_norm.py`, output `ladder-noserve/replay-norm.txt`):

| Machine | Well | Served before the cut | Return (disc 0.995) |
|---|---|---|---|
| plain | 0% | 17.0-18.1 | 0.00 (-0.12 to -0.18) |
| promise cost | 0% | 17.0-18.1 | -6.1 to -8.7 (-2.5 to -3.7) |

FARM's own objective prefers this policy to the idle one it learned (-1 / -0.94; promise cost about -60 / -19).
The learner never reaches it.

## Next step (not started)

Run test 1: the rung-1 FARM run with `slip_chance: 0`, one seed, 1M steps, `ppo-onehot.yaml`, from a scratch runs
file. It takes about 26 min per 1M steps at today's load (the 5M FARM runs took 7,921 s). Run test 2 only if test 1
does not serve. Whatever they show, the fix is in the reward layer: a hard break that idling never pays must not
make every partial server worse than idle. This is the same fear pattern as `fear-diag-report.md`, where a hard
charge taught "never try".

## Files

All in `M/plans/farm-final-20261119/morning-20261123/ladder-noserve/`, run from C with
`OMP_NUM_THREADS=1 PYTHONPATH=app`:

- `probe.py` and `probe.txt`: random, scripted and partial-reflex play through the training env, three run configs.
- `curves.py` and `curves.txt`: episode, entropy and greedy-trace stats of the 12 rung-1 run folders.
- `replay_norm.py` and `replay-norm.txt`: the no-RM greedy traces scored by both FARM machines.

Probe size: about 165k env steps per full `probe.py` run (no network, one thread), about a minute of one core. I ran
it three times: a 2-seed smoke run and two 30-seed runs. That is more than the packet's "few thousand CPU steps",
but it was env stepping only, with no training and no policy inference.
