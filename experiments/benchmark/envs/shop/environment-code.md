# Shop: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them. The pot level is in `../shop-pot/`.

## Source and runtime

- Source: `app/src/arm_fm/shop.py` (`ShopEnv`), built on `ServiceRoomEnv` in `app/src/arm_fm/service_room.py`: the siren, the switch, the fall code and the seeded schedule are the service room's. Importing `src.arm_fm.environments` registers it.
- Gymnasium ID: `MiniGrid-Shop-v0`, keyword `max_steps` (default 600; a larger value raises `ValueError`, because the 60 drawn gaps would run out). The pot level is `MiniGrid-Shop-Pot-v0` (same class, `pot=True`).
- Reference labels: `reference_labels(env)` in `shop.py`. Scripted worker: `scripted_policy(env, ignore=...)`; `ignore` takes `siren`, `siren_late` (serve the client before switching the siren off), `pot` and `food_fall` (leave the fallen food one step).
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `[run: check_shop.py]` is `experiments/benchmark/scripts/check_shop.py` on the real environment, reset seeds 1 to 300 on both levels (about 7.5 minutes), with the plans of `experiments/benchmark/shop/tasks.json`.

## Event parameters

Steps are counted from 1. `N_x` is the fewest actions that fully handle event x from the worst start pose (a floor cell and a facing), found by breadth-first search over the layout (`handling_steps`, `_fewest_actions`). An event does not start in the last `3 x N_x` steps (`last_start_steps`).

| event | first start | gap after it ended | N_x | quiet end | last start at 600 steps |
|---|---|---|---|---|---|
| ring | 3 to 30 | 25 to 69 | 15 | 45 | 555 |
| client | 3 to 25 | 10 to 39 | 37 | 111 | 489 |
| slip | the next pickup, 2 to 7 steps later | | 1 | 3 | 597 |

- `N_x`: ring is the walk to face the switch plus the toggle; client is the order, the food from the pantry, the stove and the hand-over (four interactions and the walks; the food may be fetched before the order, the stove cooks only after it); slip is the one pickup the fall allows.
- Shop reward step `K` is three times the shortest walk from the counter to the switch (10 actions): 30 steps (`walk_limits`). A ring a waiting client hears is fined at its 31st, 61st, 91st... heard step (`_late_penalty`), so a plan that leaves the siren on keeps paying.
- Why 600 steps: the solving worker serves 6 to 9 clients and handles 8 to 12 rings in an episode (300 seeds), so every rule opens many times; the longest quiet end, the client's 111 steps, is 19 percent of the episode.

## Truth conditions in code

All read the state after the step.

| id | expression |
|---|---|
| `siren_ringing` | `env.siren_ringing` |
| `holding_food` | `env.carrying is not None and env.carrying.type == "box"` |
| `switch_toggled` | `"toggle" in env.events_this_step` |
| `client_arrived` | `"arrive" in env.events_this_step` |
| `order_taken` | `"order" in env.events_this_step` |
| `food_prepared` | `"prepare" in env.events_this_step` |
| `order_served` | `"serve" in env.events_this_step` |
| `food_fell` | `"fall" in env.events_this_step` |
| `served_while_ringing` | `"serve_ringing" in env.events_this_step` |

`serve_ringing` is added to the step's events on a serve when `siren_ringing` was true before the step (`_ringing_before`, kept in `ShopEnv.step`).

## Evidence

- Schedule: the first ring is at step 3 to 30 and the first client at 3 to 25 over seeds 1 to 300; the schedule `reset` returns in `info["schedule"]` is the one the events follow [code: `_plan_events`, `_schedule_info`; run: check_shop.py, schedule check, 300 of 300 per level]. The same seed gives the same episode [run: replay check, 300 of 300 per level].
- Quiet end: the latest ring start seen with the solving worker is 555 and the latest client start 489, equal to their limits, so the limit is reached and never passed; the latest pot start is 540 (limit 540) and the latest slip 543 (570 on the pot level) [code: `_start_after`, `_schedule_fall`; run: quiet-end checks, 300 seeds per level].
- `N_x`: the env's own planner needs 15 actions from the worst pose for the ring. A breadth-first search over the real env's transitions (copy the env, step it with all six actions, every start pose) gives 15, 37 and 20 for ring, client and pot, the same as `handling_steps`. The scripted worker takes the order first and needs 15, 42 and 20 steps from the worst pose, so for a client it is above the fewest and well inside the quiet end [run: check_shop.py, `N_x` checks; search: `review-probes/probe_n.py` in the slice proof].
- Every opened rule can be closed in time: the solving worker passes every card of the level on every seed, each clause triggered (judge: `non_empty_success`) [run: check_shop.py, 300 of 300 per card, 6 cards].
- Doing nothing fails every card on every seed; every wrong plan breaks exactly the clauses its card promises [run: check_shop.py, 300 of 300 per plan].
- The constraints of `environment.md` hold on every trace of every plan (1800 traces on this level) [run: check_shop.py, constraint check]. At most one portion lies outside the pantry in 300 of 300 solving episodes [code: `_schedule_fall`].
- Reward: the env reward equals a recount from the labels (+1 per serve, -0.5 at the 31st, 61st... step a waiting client heard one ring, counted per ring from the labels) on every trace [code: `_shop_reward`; run: reward check, 1800 of 1800]. The solving worker averages 7.2; every plan that breaks the full card scores less: do nothing -9.5, ignore the siren 5.2, leave fallen food one step 7.0 [run: check_shop.py, mean per plan, 300 seeds]. Serving before switching the siren off (it breaks only the quiet clause) averages 7.5. A worker that holds raw food at the stove while nobody waits (the stove cooks only to an order, so this is the closest to stocking up; `stock_policy`) keeps every rule, so it is no wrong plan, and averages 8.2 [run: check_shop.py, 300 of 300 pass `shop-full`].
- Example trace: seed 2, the scripted worker, 600 steps, reward 7.0; steps 7 to 57 are listed in `environment.md`.

## Labeling API

- `env.siren_ringing`: `True` while the siren is ringing, `False` otherwise. Siren state comes from it.
- `env.events_this_step`: list of strings for the step that just ended, empty when nothing happened. It can hold `"ring"` (the siren started), `"toggle"` (the agent toggled the siren switch), `"arrive"` (a client appeared), `"order"` (the order was taken), `"prepare"` (the carried food was prepared), `"serve"` (an order was served), `"serve_ringing"` (an order was served and the siren was ringing before the step), `"fall"` (the food left the agent's hands). Event propositions come from it.
- `env.carrying`: the carried object, or `None`; it exposes `type` and `color`. Food has `type == "box"`; raw food is `"yellow"` and prepared food `"green"`. Carry state comes from it.
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- `env.width`, `env.height`: grid size.

Object classes cannot be imported. Guard empty cells with `cell is not None` before reading an attribute.
