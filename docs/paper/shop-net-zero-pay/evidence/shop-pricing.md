# Shop pricing: does FARM's shop machine pay for serving more? (2026-11-22)

1. **No FARM shop machine pays more for serving more.** Each served order nets exactly 0.00 on
   shop-serve (all 724 orders on 100 seeds), and the same holds on all 10 shop machines. The return
   only counts what is still open at the end: solve 0, take one order and stop -2, idle -3, serve one
   order and stop -3.
2. **The pricing rule works as designed. It is not a bug and not the LLM's choice.** All 10 clause
   sets equal the card's answer. The 2026-11-16 ladder machine that learned also netted 0 per order.
   What it had, and today's machines lack, is the end charge for an order left open. Commit
   `deff802` (2026-11-18) switched that charge off by default.
3. **A right machine for these tasks should not pay per order.** LTLf and the no-positive-loop
   record both say so. It should price an order left open. Discounted, the solve is still the best
   plan on every machine, but only by 0.5 to 1.9 per episode (0.71 on shop-serve).
4. **Pricing does not explain the 0 served on the cooking cards.** No-RM, which earns +1 per serve,
   serves 0.00 there. So does FARM with the world reward added (`shop-reward`, `both`). With the
   promise cost on, shop-serve also served 0 on 3 of 3 seeds (paper entry, Part 4).
5. **Recommendation:** lift the "machine wrong" gate, keep the counted runs, and change no pricing
   before the final run. Report the cooking cards as an exploration limit of every arm. The user
   decides two things: the served bar on shop-siren and shop-pot, and how the held ladder trains.

## 1. What each machine pays (judge seeds 2000000-2000099)

These are the FARM bundles the runs trained on. Plain return / return discounted at 0.995 (the
`shop` runs' PPO gamma). Episodes are cut at the well. Time-limit penalty 0 and end judgment off,
as in the runs.

- **take order, stop:** the scripted worker until the first order is taken, then `done`.
- **serve one, stop:** the worker until the first serve, then `done`.
- **per order:** the machine pay from the step after one serve to the next serve, over every order
  the solve served.

| machine | idle | take order, stop | serve one, stop | solve | served by solve | pay per served order |
|---|---|---|---|---|---|---|
| shop-serve | -3.00 / -2.82 | -2.00 / -1.93 | -3.00 / -2.39 | **0.00 / -1.22** | 7.24 | 0.00 (min 0, max 0) |
| shop-full | -4.00 / -3.75 | -3.00 / -2.74 | -4.00 / -3.10 | **0.00 / -1.39** | 7.24 | 0.00 (-1 to +1: siren pay falling between serves) |
| shop-quiet-first | -4.00 / -3.75 | -3.00 / -2.74 | -4.00 / -3.10 | **0.00 / -1.39** | 7.24 | 0.00 (-1 to +1, as shop-full: its extra Absence is never broken by these plans) |
| shop-boil | -5.00 / -4.50 | -4.00 / -3.50 | -5.00 / -3.68 | **0.00 / -1.64** | 6.24 | -0.01 (-1 to +1, as shop-full) |
| shop-siren | -1.00 / -0.93 | -1.00 / -0.81 | -1.00 / -0.71 | **0.00 / -0.17** | 7.24 | n/a: no client rule |
| shop-pot | -1.00 / -0.75 | -1.00 / -0.75 | -1.00 / -0.63 | **0.00 / -0.13** | 6.24 | n/a: no client rule |
| ladder: deliver | -1.00 / -0.94 | same as solve (no order on this level) | -1.00 / -0.85 | **0.00 / -0.38** | 12.25 | 0.00 (min 0, max 0) |
| ladder: deliver + siren | -2.00 / -1.87 | same as solve (no order) | -2.00 / -1.63 | **0.00 / -0.64** | 10.42 | 0.00 (-1 to +1) |
| ladder: order + deliver | -2.00 / -1.88 | -1.00 / -0.96 | -2.00 / -1.62 | **0.00 / -0.46** | 11.75 | 0.00 (min 0, max 0) |
| ladder: order + deliver + siren | -3.00 / -2.81 | -2.00 / -1.81 | -3.00 / -2.36 | **0.00 / -0.87** | 9.01 | 0.00 (-1 to +1) |

The first six are the counted 60-card machines. The four ladder machines (`shop-ladder-*`, built
today at `881b22d`) are held out: `train: false`, and the ladder's own runs file trains them.
"ladder: order + deliver" has the clause set of the 2026-11-16 machine that learned, except that
it chains the client's rule through the order: arrival -2, order +1, serve +1. The `~p1-3`
paraphrase bundles are generation checks, and I did not replay them.

- **Which machines pay more for serving more: none.** Plain, any plan that ends with nothing open
  gets 0. Serving one order and stopping pays less than taking an order and stopping (-3 against -2):
  the serve brings the next client, and that client's -3 is never paid back. The agents' -2.00
  (judge, every FARM seed of serve, full, quiet-first and boil) is exactly this local optimum.
- **The solve is the best plan on every machine, plain and discounted.** The machine ranks the plans
  right. The margin is small and does not grow with the orders served.
- **Self-check:** the script asserts that the solve pays and serves the same as
  `no-train/plan_vs_agent.json` on every seed of the six counted cards. It passed.

**Agents (judge.json, greedy, per seed):** every FARM and no-RM run on every shop card serves 0.00
per episode. That includes `shop-reward` FARM (`reward_source: both`, the same bundles), which also
gets +1 per serve from the world. FARM holds the two instructions that never mention clients:
shop-siren judged 1.00 / 1.00 / 1.00 (shop) and 1.00 / 0.81 / 1.00 (shop-reward), shop-pot
1.00 / 1.00 / 0.00. Those cards count as not learned only because of the 7.5-served bar. The full
table is in `shop-pricing/table.md`.

## 2. Cause, with code lines

The pricing rule works as designed:

- **No final state, so no completion pay.** The +10 is paid only on an edge into a final
  (`app/src/compiler/reward_layer.py:643-646`). The shop machines have `FINAL_STATES:` empty.
- **Progress is a potential over the stages still owed.** Without a final it aims at the states
  where nothing is pending (`reward_layer.py:763`, `:772`). The chain weights
  (`reward_layer.py:399-420`) give `Response(client_arrived, order_taken)` weight 3, since it
  hands off to the order and cooking rules. So an arrival charges -3, and order, cooking and serve
  pay back +1 each. Any loop sums to 0. A machine with a positive loop is refused at build
  (`reward_layer.py:183`). Record: `docs/decisions/arm-fm/rm-execution.md:233-236` ("It stays a
  potential, so no loop gains").
- **Nothing charges an order still open at the end.** The end judgment is off by default
  (`app/src/config/config.py:269-271`, commit `deff802`), and benchmark runs set
  `time_limit_penalty: 0.0` (every shop `run-config.yaml`; `app/src/benchmark/traces.py:39-42`).
  So the runtime adds nothing at the time limit (`app/src/arm_fm/runtime.py:222-226`).
- **The world turns a serve into a new charge.** The next client comes a gap after the previous
  one is served (`app/src/arm_fm/shop.py:88-91`).
- **Discounting adds only a small push.** The pay is undiscounted and the learner is not, so each
  step with stages open costs about (1 - gamma) times the stages owed. That is why the solve still
  wins by 0.71 discounted on shop-serve. This known effect is documented, and the switch to
  discounted shaping was left "to decide after the shop runs"
  (`docs/COMPILER_REWARD_DESIGN.md:154-163`, `rm-execution.md:271-273`).

**Not a bug, not the LLM.** The clause sets of all 10 bundles equal the card's `expect` (checked
against `experiments/benchmark/shop/tasks.json`). The machine pays the plans as the rules above
predict, to the cent.

**The 2026-11-16 ladder machine that learned** (`TP/slices/shop-steps`, step 2 order+deliver, 16.6
to 18.1 served per episode):

- **It netted 0 per order too:** -0.3 on arrival, then +0.1 three times
  (`TP/slices/shop-steps/pay-shop-order-deliver.md:3-9`). Today's "ladder: order + deliver" machine
  pays the same net 0 (arrival -2, order +1, serve +1). Without an end charge, it scores "take an
  order and stop" at -1 against 0 for the solve (table above).
- **What differed was the end charge.** Its manifest records `reward_end_judgment: True`. A client
  left open to the limit cost an extra -3.0 (`TP/slices/shop-steps/report.md:56`).
- **The change that removed it is `deff802`** (2026-11-18, "whole-unit pay, owed end charge,
  soft-break cost without refund"). It turned the end judgment off by default
  (`config.py:269-271`) and made the pay 10 times bigger.
- **The paper entry measured it on the round 6 level** (order and deliver, no cooking;
  `docs/paper/shop-promise-cost/`, Part 1). With both switches off, 0 / 0 / 0 served. With the end
  judgment on, 18.15 / 12.42 / 12.42. With the promise cost on, 12.23 / 11.15 / 12.23. Its summary
  (`data.json:4`): the seeds that learned all had an open promise that cost something as the step
  limit ran out (12 of 12). With both switches off, 0 of 12 learned.
- **The 60 cards all need cooking.** That step was never learned, before the freeze or after. Before
  the freeze, step 3 served 0 with the end judgment on (`TP/slices/shop-steps/report.md:104-110`).
  After it, shop-serve served 0 with the promise cost on (paper entry, Part 4: random play never
  prepares food in 1,000 episodes). Today no-RM and FARM-both serve 0 as well.

## 3. Is it the instruction?

- **In LTLf, `G(client_arrived -> F order_taken)` counts no orders.** It holds on a finite trace
  when no arrival is left without its answer, so serving 1 or 17 clients is equally correct if none
  is left open. The task says "whenever a client comes in": answer every client, not serve many.
- **Throughput comes from the world, not the instruction.** A new client comes a gap after each
  serve, and no event starts in the quiet end (`shop.py:88-95`). Keeping the rule therefore means
  serving until the quiet end.
- **A right machine should not pay per order.** A net-positive serve would be a positive loop
  `u0 -> ... -> u0`, which the build refuses (`reward_layer.py:183`; `rm-execution.md:233-236`;
  `COMPILER_REWARD_DESIGN.md:148-153`). The user rule "the RM matches the instruction, never world
  forcing" says the same.
- **What it should do is price an order left open:** the end judgment or the promise cost, both
  existing switches.
- **The 7.5-served bar belongs to the benchmark, not to the instructions.** It also applies to
  shop-siren and shop-pot, which never mention clients. The user decides whether it should.

## 4. Options, replayed (no training)

**(a) `reward_source: both`.** The world pays +1 per serve and fines a ring a waiting client hears
(`shop.py:452-466`). Plain / discounted at 0.99:

| machine | take order, stop | serve one, stop | solve |
|---|---|---|---|
| shop-serve | -10.98 / -2.75 | -10.20 / -2.05 | **7.24 / -0.28** |
| shop-full | -11.98 / -3.43 | -11.20 / -2.58 | **7.24 / -0.47** |
| shop-boil | -24.00 / -5.03 | -22.23 / -3.65 | **5.82 / -0.94** |
| ladder: order + deliver | -1.00 / -0.93 | -1.00 / -0.64 | **11.75 / 1.54** |

- **It pays per order and the gap grows with the orders served.**
- **It is already tested.** The `shop-reward` suite is exactly FARM with `both` on the same bundles
  (`run-config.yaml`: `reward_source: both`, `bundle: experiments/benchmark/shop/bundles/farm/...`).
  All 15 runs serve 0.00.
- **It cannot move to the `shop` suite.** A protected invariant keeps `both` in `shop-reward` only
  (`docs/decisions/benchmark/thesis-benchmark.md:336`, `:350-352`). Cost: none to keep. It changes
  nothing.

**(b1) Promise cost on** (record `rm-execution.md`, the 2026-11-16 entry and the 2026-11-20 well
price; `reward_layer.py:622-640`):

- **Rebuilds need no model calls.** `rebuild-rewards --promise-cost` took seconds per bundle. The 10
  copies are in `shop-pricing/bundles/*-pc`.
- **Replay: the solve is the best plan everywhere, by 20 to 37 plain.** Each order costs the time it
  stays open, so serving faster pays more. Leaving a client waiting costs the whole episode.

| machine | idle | take order, stop | serve one, stop | solve | per served order |
|---|---|---|---|---|---|
| shop-serve | -61.63 / -20.52 | -60.63 / -19.63 | -59.30 / -18.49 | **-33.85 / -13.36** | -4.68 |
| shop-full | -63.01 / -21.81 | -61.88 / -20.68 | -61.44 / -20.04 | **-38.24 / -14.90** | -5.15 |
| shop-boil | -64.01 / -22.56 | -62.88 / -21.43 | -62.75 / -20.87 | **-43.06 / -16.40** | -6.68 |
| ladder: order + deliver | -60.63 / -19.58 | -59.63 / -18.66 | -58.30 / -17.49 | **-21.26 / -8.43** | -1.81 |

- **Cost: it is a change to the FARM method after the freeze.** As a default it reprices every FARM
  machine with a hard promise and invalidates the counted FARM runs on them, not only the shop. As a
  shop-only switch it is per-card tuning, which breaks one method for all cards. A shop-only change
  invalidates the 33 counted FARM shop runs (6 cards x 3 seeds in `shop`, 5 x 3 in `shop-reward`).
- **Evidence it would not lift the cooking cards:** shop-serve served 0 of 3 with it on (paper
  entry, Part 4).

**(b2) End judgment on** (`config.py:269-271` "flip this one line"; `rm-execution.md:339-343`):

- **No no-model rebuild tool exists.** `rebuild-rewards` has no flag for it, and `ablate-rm` only
  turns switches off. It needs a compile from the stored clauses plus copies of the labeling, texts
  and embeddings. The paper check's `compile_card.py` does the compile.
- **Not replayed here.** By the rule, each hard stage still open at the end costs -10
  (`reward_layer.py:977-989`, `_owed` and `_end_judgment`). The learner sees that charge discounted
  by 0.995^600 ≈ 0.05.
- **Cost:** it is the same kind of method change as (b1), with the same invalidation. It learned only
  on levels without cooking.

**(b3) Discounted shaping** (left open in `COMPILER_REWARD_DESIGN.md:154-157`). It makes every
plan's discounted return the same apart from the end term. That removes the one small push toward
serving. Rejected.

**Recommendation:**

- **Lift the gate.** The machines are right for their instructions, and the sign has a known cause.
- **Keep all counted runs, and change no pricing before the final run.**
- **In the report, call the cooking cards a limit of exploration.** No arm serves one order:
  FARM-rm, FARM-both and no-RM alike.
- **Two questions for the user:**
  - Does the 7.5-served bar apply to shop-siren and shop-pot? FARM holds both instructions.
  - How does the held ladder train? Its four machines have the same net-0 shape with no end charge.
    At the defaults, round 6 predicts 0 served on the order-and-deliver rungs. Trained on its
    promise-cost copies (already built, no model calls), it would be a labeled side test that does
    not count.

## Files and rerun

- `tools/shop_pricing.py`: `play <bundle>` writes `shop-pricing/<bundle>.json` (4 plans x 100
  seeds, stored and promise-cost machines). `table` writes `shop-pricing/table.md` (all bundles plus
  the agents' judge rows).
- `shop-pricing/bundles/<bundle>-pc`: the `rebuild-rewards --promise-cost` copies.
- Rerun (repository root; PATH with RM_RL_env/bin and ~/.local/bin for the rebuild):

```
env -C /home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl PYTHONPATH=app app/main.py rebuild-rewards --bundle experiments/benchmark/shop/bundles/farm/<bundle> --output .git/agent-memory/plans/farm-final-20261119/freeze-prep/shop-pricing/bundles/<bundle>-pc --promise-cost --gym-id <gym id> --env-kwargs '<card env_kwargs>'
env -C /home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl PYTHONPATH=app OMP_NUM_THREADS=2 /home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin/python -P -W ignore .git/agent-memory/plans/farm-final-20261119/freeze-prep/tools/shop_pricing.py play <bundle>
env -C /home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl PYTHONPATH=app /home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin/python -P -W ignore .git/agent-memory/plans/farm-final-20261119/freeze-prep/tools/shop_pricing.py table
```

- About 5 min per bundle, 7 at once on the loaded machine; shop-boil (65 states) about 15 min.
- **Gap, shop-boil:** HEAD holds a failed generation (`ebe6874`). The worktree bundle is
  uncommitted, with manifest status `reconstructed` and its manifest, labeling and texts rewritten
  at 20:08:52 today, 7 s before `no-train/plan_vs_agent.json` was written. Its `reward_machine.txt`
  (01:51) predates the runs (06:10) and its clauses equal the card's. The replay pays through the
  bundle's own `labeling.py`, the rewritten one, and no hash proves it is the one the runs used.
