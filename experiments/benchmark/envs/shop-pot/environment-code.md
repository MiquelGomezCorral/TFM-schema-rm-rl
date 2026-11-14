# Shop with a pot: code notes

Addition to `environment.md`; read both. The two levels share the checks and most of the evidence of `../shop/environment-code.md` (event parameters of the ring, the client and the slip, why 600 steps); this file lists the whole Labeling API and what the pot adds.

## Source and runtime

- Source: the same class as the shop, `ShopEnv(pot=True)` in `app/src/arm_fm/shop.py`. Gymnasium ID `MiniGrid-Shop-Pot-v0`, keyword `max_steps` (default 600).
- The schedule draws the pot's start for every seed whatever the level, so the ring, client and slip draws of a seed are the same in both levels [code: `_plan_events`]. The pot is armed only with `pot=True`.
- `[run: check_shop.py]` is `experiments/benchmark/scripts/check_shop.py`, reset seeds 1 to 300, `shop-pot` section.

## Event parameters

| event | first start | gap after it ended | N_x | quiet end | last start at 600 steps |
|---|---|---|---|---|---|
| pot | 30 to 90 | 40 to 99 | 20 | 60 | 540 |

- `N_pot`: with full hands from the worst start pose, walk to the stove, put the food down on a free cell in front, turn the stove down, pick the food up again (20 actions, breadth-first search over the layout with the put-down and the pick-up as moves).
- Shop reward threshold `K_p` is three times the shortest walk from the counter to the stove (8 actions): 24 steps (`walk_limits`). A boil is fined at its 25th, 49th, 73rd... step (`_late_penalty`), and a ring a waiting client hears at its 31st, 61st, 91st... heard step, so a plan that leaves the siren or the pot alone keeps paying.
- The put-down is the `drop` action, not a slip: `events_this_step` has no `"fall"` for it [code: `ShopEnv._fall` runs only for planned slips].

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
| `pot_boiling` | `env.pot_boiling` |
| `stove_fixed` | `"fix" in env.events_this_step` |

`serve_ringing` is added to the step's events on a serve when `siren_ringing` was true before the step (`_ringing_before`, kept in `ShopEnv.step`).

## Evidence

- Pot schedule: the first boil is at step 30 to 90 over seeds 1 to 300, the latest boil start is 540 (limit 540); 5 to 8 boils per episode with the solving worker [run: check_shop.py, schedule and quiet-end checks, 300 of 300].
- Every card of the level is passed by the solving worker on every seed, doing nothing fails every card on every seed, and each wrong plan breaks exactly its promised clauses [run: check_shop.py, 300 of 300 per plan, `shop-boil` and `shop-pot`].
- The stove goes down only with empty hands: `stove_fixed` and `holding_food` never hold together, and a fix needs a boil before it, on every trace (1500 traces) [run: check_shop.py, constraint check].
- Reward: the recount from the labels matches the env reward on all 1500 traces, including the boil fine [run: reward check]. The solving worker scores 5.8 on average; every plan that breaks the full card scores less: do nothing -20.5, ignore the siren 3.5, ignore the pot -3.8, leave fallen food one step 5.7 [run: check_shop.py, mean per plan, 300 seeds]. The stove cooks only to an order taken, so food cannot be prepared ahead; a worker that holds raw food at the stove while nobody waits (`stock_policy`) keeps every rule, is no wrong plan, and averages 6.3 [run: check_shop.py, 300 of 300 pass `shop-boil`].
- Example trace: seed 4, the scripted worker, 600 steps, reward 6.0; steps 98 to 158 are listed in `environment.md`.

## Labeling API

- `env.siren_ringing`: `True` while the siren is ringing, `False` otherwise. Siren state comes from it.
- `env.events_this_step`: list of strings for the step that just ended, empty when nothing happened. It can hold `"ring"` (the siren started), `"toggle"` (the agent toggled the siren switch), `"arrive"` (a client appeared), `"order"` (the order was taken), `"prepare"` (the carried food was prepared), `"serve"` (an order was served), `"serve_ringing"` (an order was served and the siren was ringing before the step), `"fall"` (the food left the agent's hands), `"boil"` (the pot started boiling), `"fix"` (the agent turned the stove down). Event propositions come from it.
- `env.pot_boiling`: `True` while the pot is boiling over, `False` otherwise. Pot state comes from it.
- `env.carrying`: the carried object, or `None`; it exposes `type` and `color`. Food has `type == "box"`; raw food is `"yellow"` and prepared food `"green"`. Carry state comes from it.
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- `env.width`, `env.height`: grid size.

Object classes cannot be imported. Guard empty cells with `cell is not None` before reading an attribute.
