# Shop suite

A MiniGrid level where things keep happening on their own and the agent has to react, with a ladder of six cards.

Why: a rule "whenever X happens, do Y" passes when X never happens. On the older MiniGrid cards X is something the agent does, so an agent that does nothing keeps the rule and is judged 1.00 on idle runs. In the shop X is the world's: a siren rings, a client walks in, the food in the agent's hands slips, the pot boils over. Doing nothing breaks every card (300 of 300 seeds, `check_shop.py`).

The world is the same for every card of a level: the siren, the clients and the food slips run in every episode and only the rules differ, so a policy trained on one card sees the world of every other card (the transfer experiment needs this). Facts: `../envs/shop/environment.md` and `../envs/shop-pot/environment.md`. Code: `app/src/arm_fm/shop.py` (`MiniGrid-Shop-v0`, `MiniGrid-Shop-Pot-v0`).

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

## Plans

The solving plan is the scripted worker (`scripted_policy`): it reacts to every event and keeps every rule. Wrong plans: do nothing; serve but ignore the siren; serve a waiting client first and switch the siren off later (`siren_late`, breaks only the quiet clause); leave the pot (`pot`); let fallen food lie one step (`food_fall`); take the first order and stop (`shop-serve`). Each plan promises the exact clauses it breaks, on event seeds 1 to 3, and the trace bank checks it.

## Run grid

Seed 1 only for now (target 1, 2, 3). Learner PPO, setting s07 (`../configs/ppo.yaml`). RM reward only is `reward_source: rm`; "with shop reward" is `reward_source: both` (RM reward plus the shop reward, `runtime.py`), set by the new suite key `reward_source` in a runs file (default `rm`). Such a run is in a second suite named `shop-reward`, so its run folders stay apart.

| File | Suite | Cards | Arms | Reward | Steps | Runs |
|---|---|---|---|---|---|---|
| `runs-level1.yaml` | `shop` | `shop-siren` | ARM-FM, FARM | RM | 1.5M | 2 |
| `runs-level1-shop-reward.yaml` | `shop-reward` | `shop-siren` | ARM-FM, FARM | RM + shop | 1.5M | 2 |
| `runs-levels2-5.yaml` | `shop` | `shop-serve`, `shop-full`, `shop-quiet-first`, `shop-boil` | ARM-FM, FARM | RM | 5M | 8 |
| `runs-levels2-5-shop-reward.yaml` | `shop-reward` | the same four | ARM-FM, FARM | RM + shop | 5M | 8 |
| `runs-pot.yaml` | `shop` | `shop-pot` | ARM-FM, FARM | RM | 5M | 2 |
| `runs-no-rm.yaml` | `shop` | all six | no-RM | shop reward | 5M | 6 listed, 2 trained |
| `runs-boil-15m.yaml` | `shop-probe` | `shop-boil` | ARM-FM | RM | 15M | 1 |

25 trainings. No-RM trains once per level (Shop for the first four cards, Shop-Pot for `shop-boil` and `shop-pot`; the dry run prints `start` twice and `share` four times) and is judged against every card of its level with `test-rl --judge <card.json>`. The 5M of `shop-pot` is a choice (the brief gives none for it). Reward note: the shop penalty repeats (-0.5 for every further K steps a waiting client hears the siren, K = 30; pot, K_p = 24), so the solving worker out-earns every plan that breaks `shop-full` or `shop-boil` (Shop: 7.2 against -9.5 for doing nothing, 5.2 for ignoring the siren, 7.0 for leaving fallen food; Pot: 5.8 against -20.5, 3.5, -3.8 for ignoring the pot, 5.7; 300 seeds, `check_shop.py`). `shop-quiet-first` has no such target: serving before switching the siren off breaks only its quiet clause and averages 7.5 on Shop. Preparing ahead is impossible (the stove cooks only to an order taken), and a worker that holds raw food at the stove while nobody waits keeps every rule: it is no wrong plan and averages 8.2 on Shop and 6.3 on Pot, above the solving worker, which is fine because the target only ranks plans that break a card.

## Contents

- `tasks.json`: the cards. `runs-*.yaml`: the run grid above. `bundles/<arm>/<card-id>/`: the generated machines (made by `generate-suite`, not in this slice except for the proof).

Reproduce: `python app/main.py trace-bank --tasks experiments/benchmark/shop/tasks.json --output <dir>`; `PYTHONPATH=app python experiments/benchmark/scripts/check_shop.py --out <dir>`; `python app/main.py run-suite --suite experiments/benchmark/shop/runs-no-rm.yaml --dry-run` (and the other runs files).
