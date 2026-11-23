# Shop suite

A MiniGrid level where things keep happening on their own and the agent has to react, with a ladder of six cards and a serving ladder of five more ("Ladder", below).

Why: a rule "whenever X happens, do Y" passes when X never happens. On the older MiniGrid cards X is something the agent does, so an agent that does nothing keeps the rule and is judged 1.00 on idle runs. In the shop X is the world's: a siren rings, a client walks in, the food in the agent's hands slips, the pot boils over. Doing nothing breaks every card (300 of 300 seeds, `check_shop.py`).

The world is the same for every card of a level: the siren, the clients and the food slips run in every episode and only the rules differ, so a policy trained on one card sees the world of every other card (the transfer experiment needs this). Facts: `../envs/shop/environment.md` and `../envs/shop-pot/environment.md`. Code: `app/src/arm_fm/shop.py` (`MiniGrid-Shop-v0`, `MiniGrid-Shop-Pot-v0`).

## Options: a smaller shop, an easier start, fewer food slips, no siren or clients, a client who leaves

Nine settings of the shop environment, all off by default (the default shop, its cards and every existing run are unchanged). Set them in a card's `env_kwargs`, next to `max_steps` and `agent_view_size`; they work on Shop and Shop-Pot.

- `small: true`: a 7 x 7 room with the counter, the pantry and the stove close together. The same objects, events and rules; the quiet end and the late-siren fine follow the shorter walks (`environment.md`, "Variants"). A scripted solver serves its first client about 35 steps after the client arrives, against about 49 in the default room. It is a constructor setting, not new gym ids, so one mechanism carries both options and no card or runs file needs a second id.
- `area: n` (8, 7, 5 or 3, default 8): the side of the square of floor the agent walks in, walls not counted. 8 is the shop as it is (a 10 x 10 map), 5 is `small: true`, 7 and 3 are new. The same objects, events and rules, the same step limit (600) and the same event schedule on a seed; the walks, and with them the quiet end and the late-siren fine, follow the room. A smaller room means more orders served per episode. See "World size" below.
- `easy_start_prob: p` (0 to 1): a share `p` of the episodes starts with the agent at the counter, facing the client spot, and the first client arrives on step 1 as the normal `client_arrived` event, so every machine and the labeling see it. The other events of the episode keep their seeded times. Not with `clients: false`: with no client to arrive there is no easy start.
- `slip_chance: p` (0 to 1, default 0.5): the chance that a pickup is followed by a slip. The first pickup of an episode always slips while `p > 0`; `slip_chance: 0` means no slip ever (`food_fell` never true). The other events keep their seeded times. Built to test whether the risk of holding food is what blocks serving; `environment.md` is not changed, so the generated machines are the same.
- `siren: false` / `clients: false`: the siren never rings / no client ever comes in. For a test that should run in a shop with only the parts its card uses (a serving card without the siren, a siren card without clients). With no clients, every ring is fined after the usual walk limit. The other events keep their seeded times.
- `client_patience: n` (a step count, default none): a client not served `n` steps after coming in leaves and the episode ends there as a loss (`terminated`, event `leave`), so a machine pays its end charge at that step instead of at step 600. The fewest actions from a client's arrival to the serve are 37 from the worst pose, 30 from the episode start and 28 from the counter, so 50 fits.
- `order_needed: false` / `cooking_needed: false` (default true): a client needs no order (it is marked ordered when it arrives and takes food as soon as it is held at the counter; the `order` event never fires) / any carried food, raw included, counts as served (the stove still cooks). For testing simpler serving steps: deliver only (both off), order then deliver (`cooking_needed: false`), then the full chain. The events keep their seeded times and `environment.md` is not changed, so the generated machines are the same.

## The cards

No goal, no episode end except the 600-step limit. All clauses are `hard`. LTLf is the judge's display form.

| Level | Card | World | Clauses |
|---|---|---|---|
| 1 | `shop-siren` | Shop | 0 `Response(siren_ringing, switch_toggled)` |
| 2 | `shop-serve` | Shop | 0 `Response(client_arrived, order_taken)`, 1 `Response(order_taken, food_prepared)`, 2 `Response(food_prepared, order_served)`, 3 `ChainResponse(food_fell, holding_food)` |
| 3 | `shop-full` | Shop | 0 the siren clause, then the four serving clauses as 1 to 4 |
| 4 | `shop-quiet-first` | Shop | `shop-full` plus 5 `Absence(served_while_ringing)` |
| 5 | `shop-boil` | Shop-Pot | `shop-full` plus 5 `Response(pot_boiling, stove_fixed)` |
| T | `shop-pot` | Shop-Pot | 0 `Response(pot_boiling, stove_fixed)` (the transfer experiment's second level) |

LTLf: `Response(a,b)` is `(G (a -> (F b)))`, `ChainResponse(a,b)` is `(G (a -> (X b)))`, `Absence(a)` is `(~(F a))`. The task wording and three paraphrases per card are in `tasks.json`.

- Wording: the brief's "pick it up right away" and "run the shop" are not used. The card contract bans "right away", so the food rule reads "pick it up on your very next move" (the box-carry wording). "Run the shop" alone would hide the rules from the generator, so each task spells its rules out.
- `shop-boil`: the clause is the pot rule alone. "Put down what you hold, turn the stove down, pick it up again" is how a carrying agent can satisfy it, because the stove works only with empty hands; it is not a separate clause.
- `shop-quiet-first`: "never serve while the siren rings" fits none of the 8 templates, so `served_while_ringing` (a serve on a siren that was already ringing) makes it `Absence`.
- FARM and the two big cards: FARM generates both machines, but its review step cannot read them. `shop-boil` (257 states) is 6.5M tokens and `shop-quiet-first` (65 states) is 0.97M, against the critic's 1M window. `shop-quiet-first` is borderline: it is refused at reasoning `none`, the run's setting, and fits at `low`. Both count as "too complex to review" (reason `critic-context-exceeded`), not as generation failures. The status files in `bundles/farm/` predate the reason and still read `provider-error`.

## Plans

The solving plan is the scripted worker (`scripted_policy`): it reacts to every event and keeps every rule. Wrong plans: do nothing; serve but ignore the siren; serve a waiting client first and switch the siren off later (`siren_late`, breaks only the quiet clause); leave the pot (`pot`); let fallen food lie one step (`food_fall`); take the first order and stop (`shop-serve`). Each plan promises the exact clauses it breaks, on event seeds 1 to 3, and the trace bank checks it.

## Run grid

Seeds 1 to 3 (since 2026-11-20; the Runs column counts one seed). Learner PPO, setting s07 (`../configs/ppo.yaml`). RM reward only is `reward_source: rm`; "with shop reward" is `reward_source: both` (RM reward plus the shop reward, `runtime.py`), set by the new suite key `reward_source` in a runs file (default `rm`). Such a run is in a second suite named `shop-reward`, so its run folders stay apart.

| File | Suite | Cards | Arms | Reward | Steps | Runs |
|---|---|---|---|---|---|---|
| `runs-level1.yaml` | `shop` | `shop-siren` | FARM | RM | 1.5M | 1 |
| `runs-level1-shop-reward.yaml` | `shop-reward` | `shop-siren` | FARM | RM + shop | 1.5M | 1 |
| `runs-levels2-5.yaml` | `shop` | `shop-serve`, `shop-full`, `shop-quiet-first`, `shop-boil` | FARM | RM | 5M | 4 |
| `runs-levels2-5-shop-reward.yaml` | `shop-reward` | the same four | FARM | RM + shop | 5M | 4 |
| `runs-pot.yaml` | `shop` | `shop-pot` | FARM | RM | 5M | 1 |
| `runs-no-rm.yaml` | `shop` | all six | no-RM | shop reward | 5M | 6 listed, 2 trained |

2026-11-15: the shop runs FARM and no-RM only (user decision, `docs/decisions/benchmark/thesis-benchmark.md`). The ARM-FM rows of this grid were dropped: none of them had been trained or reported (the ARM-FM shop runs so far are probes and a smoke run outside these files), and `runs-boil-15m.yaml`, an ARM-FM-only probe of `shop-boil`, was removed. ARM-FM machines for the shop cards stay in `bundles/arm-fm/` as generated.

2026-11-22: ARM-FM trains the shop again (user: every arm on the same 60 cards). Its stored shop bundles were built before the code freeze, and four of the six end the episode after one step, so the six cards are regenerated on the freeze (`bundles-freeze/arm-fm/`) and gated before any training; a machine that fails counts as not learned.

2026-11-15: the FARM bundles `shop-serve` and `shop-full` (and the archive `shop-serve~p3`) were rebuilt with the chain-weighted progress reward (each rule weighted by the chain it hands off to; `docs/COMPILER_REWARD_DESIGN.md`; `python app/main.py rebuild-rewards --bundle <dir>`): only the transition rewards changed, so the serve chain now pays arrive -0.3, order +0.1, cook +0.1, serve +0.1. Earlier shop results used the old rewards (code up to commit `ad470f6`).

13 trainings per seed (39 over seeds 1 to 3). No-RM trains once per level (Shop for the first four cards, Shop-Pot for `shop-boil` and `shop-pot`; the dry run prints `start` twice and `share` four times) and is judged against every card of its level with `test-rl --judge <card.json>`. The 5M of `shop-pot` is a choice (the brief gives none for it). Reward note: the shop penalty repeats (-0.5 for every further K steps a waiting client hears the siren, K = 30; pot, K_p = 24), so the solving worker out-earns every plan that breaks `shop-full` or `shop-boil` (Shop: 7.2 against -9.5 for doing nothing, 5.2 for ignoring the siren, 7.0 for leaving fallen food; Pot: 5.8 against -20.5, 3.5, -3.8 for ignoring the pot, 5.7; 300 seeds, `check_shop.py`). `shop-quiet-first` has no such target: serving before switching the siren off breaks only its quiet clause and averages 7.5 on Shop. Preparing ahead is impossible (the stove cooks only to an order taken), and a worker that holds raw food at the stove while nobody waits keeps every rule: it is no wrong plan and averages 8.2 on Shop and 6.3 on Pot, above the solving worker, which is fine because the target only ranks plans that break a card.

## Ladder: from "just deliver" to the full shop (2026-11-22)

The full shop is not learned: FARM's `shop-serve` and `shop-full` were judged 0.00 on all three seeds in the final run. The ladder (user, 2026-11-22) adds one step per rung, to show where learning breaks and why the whole task at once is too much. Food slips at the default chance and the next-move pickup rule stay on every rung; the siren is a second axis. The rungs use the options above, so `environment.md`, and with it the vocabulary the generator sees, is the same on every rung.

| Rung | Card | World options | Clauses |
|---|---|---|---|
| 1 deliver | `shop-ladder-deliver` | `order_needed`, `cooking_needed`, `siren` false | 0 `Response(client_arrived, order_served)`, 1 `ChainResponse(food_fell, holding_food)` |
| 2 deliver + siren | `shop-ladder-deliver-siren` | `order_needed`, `cooking_needed` false | 0 `Response(siren_ringing, switch_toggled)`, then rung 1's as 1 and 2 |
| 3 order + deliver | `shop-ladder-order-deliver` | `cooking_needed`, `siren` false | 0 `Response(client_arrived, order_taken)`, 1 `Response(order_taken, order_served)`, 2 the food clause |
| 4 order + deliver + siren | `shop-ladder-order-deliver-siren` | `cooking_needed` false | 0 the siren clause, then rung 3's as 1 to 3 |
| 5 serve, no siren | `shop-ladder-serve` | `siren` false | `shop-serve`'s four clauses, on `shop-serve`'s machine (`bundle_of`) |
| 6 serve, full shop | `shop-serve`, `shop-full` | none | levels 2 and 3 above (trained in the 60-card set, not rerun) |

- Fetching the food gets no clause on any rung: it only makes `holding_food` true, so the chain links the events (the generator prompt's whenever-chain rule, as on `shop-serve`). Without the stove, the order hands off straight to the serve.
- No ladder clause starts at `holding_food`. The 2026-11-16 ladder had `Response(holding_food, order_served)`: its agents served about 18 clients per episode but kept a spare portion, so every test episode ended with that rule open and was judged 0. Here a stock worker that holds a spare portion whenever it is idle (`check_shop.py`'s `stock_policy`) ends 100% of its episodes holding food and is judged 1.00 on every rung.
- The four new cards have three paraphrases each and get their own bundles; `shop-ladder-serve` has none and `generate-suite` skips it. `train` is false on all five: they are not in the counted 60-card set, and the ladder trains from its own runs file (suite `shop-ladder`).
- `check_shop.py` plays every card of a level in the first card's world, so it checks the ladder cards in the default shop, not in their own worlds. The check below plays them in their own worlds.

Check, 2026-11-22: the trace bank passes 60 of 60 plans (solve, wrong and idle, event seeds 1 to 3), each wrong plan breaking exactly the clauses it promises. On reset seeds 1 to 100 of each rung's own world, the scripted solving worker is judged 1.00 and serves, per episode:

| Rung | Solving worker served (min) | Stock worker served, judged |
|---|---|---|
| 1 deliver | 12.11 (10) | 15.11, 1.00 |
| 2 deliver + siren | 10.42 (9) | 13.41, 1.00 |
| 3 order + deliver | 11.69 (10) | 14.61, 1.00 |
| 4 order + deliver + siren | 9.01 (7) | 12.68, 1.00 |
| 5 serve, no siren | 9.33 (8) | 9.86, 1.00 |

Every rung's solving worker clears the shop's learned bar of 7.5 served per episode on average. `shop-serve`'s FARM machine passes the plan check in rung 5's world (solve, wrong and idle plans, event seeds 1 to 3; no plan fails to run).

## World size: the same ladder in a smaller shop (2026-11-23)

FARM does not learn the ladder in the 8 x 8 shop (rungs 1 and 2 serve 0 orders). User, 2026-11-23: "make the shop smaller? like 7x7 or 5x5? or even 3x3". The `area` option (see Options) shrinks the floor and nothing else: the objects, events, rules, step limit (600), event schedule and labels are the same, so a FARM machine made for the shop is the machine of every size.

Cards: `<ladder card>-<n>x<n>` for rungs 1 to 3 (`shop-ladder-deliver`, `-deliver-siren`, `-order-deliver`) and n in 7, 5, 3. Each is its base card with `env_kwargs.area` set and `bundle_of` pointing at the base card, so it trains on the base card's FARM machine with no new generation; same task text and clauses, no paraphrases, `train` false. Rungs 4 and 5 were not built at the smaller sizes (the same script adds them). Every rung fits at every size: the counter and the pantry take the outer floor columns, the stove is in the north wall and the switch in the south wall, so at 3 x 3 the agent walks a corridor of 3 cells between them.

| Floor | Map | Free cells | `N_x` ring / client | Ring fine after (`K`) | Quiet end, client / ring | Solving worker served, rungs 1 / 2 / 3 | Full shop, solving worker |
|---|---|---|---|---|---|---|---|
| 8 x 8 (default) | 10 x 10 | 58 | 15 / 37 | 30 | 489 / 555 | 12.11 / 10.42 / 11.69 | 7.19 |
| 7 x 7 | 9 x 9 | 43 | 14 / 34 | 27 | 498 / 558 | 12.99 / 11.59 / 12.52 | 7.85 |
| 5 x 5 (`small`) | 7 x 7 | 19 | 11 / 27 | 21 | 519 / 567 | 15.06 / 13.85 / 14.55 | 9.68 |
| 3 x 3 | 5 x 5 | 3 | 5 / 16 | 6 | 552 / 585 | 18.21 / 17.20 / 17.51 | 13.58 |

Check, 2026-11-23, no model call (reset seeds 1 to 100 of each card's own world): the layout has every station in place and reachable, the scripted worker's worst handling time from every start pose fits `N_x`, a ringing siren shows in the view from every pose, the recorded schedule, quiet end, replay, one-portion rule, label constraints and reward recount hold on every seed (`size_check.py`); the trace bank passes 99 of 99 plans (solve, wrong, idle; event seeds 1 to 3); the solving worker is judged 1.00 and the stock worker 1.00 on every card (`ladder_check.py`); the borrowed machines pass the gate in each size's world (pay order at step limit 600, plan trace, labeling, plan check, wrong plans: 9 of 9). The machine pays more for each extra served order at every size (0.03 to 0.10 per order, discounted at 0.995; `pricing_check.py`, seeds 1 to 40). On the 3 x 3 cards the wrong plan "leave fallen food one step" is written differently: the worker serves only 3 steps after a pickup and a slip comes 2 to 7 steps after it, so on some seeds the fall never comes before the next serve and the original plan breaks nothing; the card's plan holds the first portion until it slips.

Reading the table: a smaller room serves more orders per episode, so a learned policy gets more reward signal per episode and the quiet end moves later. In the 3 x 3 shop `K` is 6 (3 times the shortest walk to the switch): the env reward fines 0.5 for every further 6 steps a waiting client hears the siren, against 30 in the 8 x 8 shop. A scripted worker still switches it off within 5 steps from any pose, so the solving worker is never fined.

Runs files (suites `shop-size`, `shop-size-std`, `shop-size-reward`) are in the plan folder `freeze-prep/`, not here.

## Contents

- `tasks.json`: the cards. `runs-*.yaml`: the run grid above. `bundles/<arm>/<card-id>/`: the generated machines (made by `generate-suite`, not in this slice except for the proof).

Reproduce: `python app/main.py trace-bank --tasks experiments/benchmark/shop/tasks.json --output <dir>`; `PYTHONPATH=app python experiments/benchmark/scripts/check_shop.py --out <dir>`; `python app/main.py run-suite --suite experiments/benchmark/shop/runs-no-rm.yaml --dry-run` (and the other runs files).
