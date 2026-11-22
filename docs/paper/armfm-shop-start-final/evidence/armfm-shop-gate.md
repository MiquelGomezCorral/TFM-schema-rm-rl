# ARM-FM shop on the freeze: gate (2026-11-22)

Packet: `armfm-shop-gate-packet.md`. Bundles: `C/experiments/benchmark/shop/bundles-freeze/arm-fm/`, from the root's
background generation (left alone). No training, no model call, no bundle or code changed.

## Result

22 of 24 bundles finished and were gated; none passes, so nothing trains yet. `shop-boil` (main) and `shop-boil~p2`
were still generating at 20:53 (processes alive since 19:40 and 19:43), after a 30-minute wait. They are not gated.

21 of the 22 bundles mark their start state `u0` as their only final state; the 22nd, `shop-boil~p3`, ends at its
first served order (below). The shared runtime ends the episode at a final state, so in those 21 every episode ends
before the agent acts (status `pipeline-failed`, plan check "solve-s1: ends the episode before the agent acts"). By the packet's rule these machines do not train and count as not learned. This is the
ARM-FM format limit: our ARM-FM prompts call final states "accepting" (`app/src/prompts/arm_fm/rm_generator.system.md:16`)
and the runtime ends the episode there (`docs/decisions/arm-fm/rm-execution.md:47`). The model marked the state that
owes nothing final, which is right for an accepting automaton and fatal for a terminal one. The siren and pot machines
(all 8) are otherwise right Response machines.

## Per card

| suite | card | bundle | verdict | reason |
|---|---|---|---|---|
| shop | shop-siren | `bundles-freeze/arm-fm/shop-siren` | not trained | start is final; otherwise a right Response (ring owes a toggle) |
| shop | shop-serve | `.../shop-serve` | not trained | start is final; also a fall not picked up next move only costs 0.1 per step (hard rule made soft) |
| shop | shop-full | `.../shop-full` | not trained | start is final; also a missed next-move pickup costs 0.1 once, no well |
| shop | shop-quiet-first | `.../shop-quiet-first` | not trained | start is final; also no clause for a client arriving, and serving while ringing costs 1 instead of failing |
| shop | shop-boil | `.../shop-boil` | missing | still generating at 20:53; not gated |
| shop | shop-pot | `.../shop-pot` | not trained | start is final; otherwise a right Response (boil owes a fix) |
| shop-reward | shop-siren | same bundle as shop | not trained | as shop |
| shop-reward | shop-serve | same bundle as shop | not trained | as shop |
| shop-reward | shop-full | same bundle as shop | not trained | as shop |
| shop-reward | shop-quiet-first | same bundle as shop | not trained | as shop |
| shop-reward | shop-boil | same bundle as shop | missing | as shop |

Count now: 9 of the 11 cards (shop 5, shop-reward 4) are not trained and count as not learned (format limit). `shop-boil` (shop and
shop-reward) waits for its bundle.

Paraphrases (do not train; generation record only): all 3 of siren, serve, full, quiet-first and pot, and
`shop-boil~p1`, start final. `shop-boil~p3` does not start final, but every state goes to its final `u10` on the
first served order, so wrong plans that never silence the siren, never turn the stove down or leave fallen food
reach the final at steps 50, 67 and 71 (early final; `pipeline-failed`, "wrong-1-s1: reaches the final at step 50").
`shop-boil~p2` is missing.

## Copies and jobs

No copy written. No machine passed, and no failed main machine lets the agent act (all five main ones start final),
so there is no counted copy and no side copy. An `only: []` file would train every train card
(`app/scripts/run_suite.py:219`), so I wrote none.

**jobs.json:** no lines to add. The held job `armfm-shop-60` (`run-logs/jobs.json:10-14`) points at
`arm-fm/shop-60-freeze.yaml`, which does not exist. Keep it held, or delete it if `shop-boil` fails.

When `shop-boil` lands, gate it the same way (no model call; `C` as cwd, `env -i` with `PYTHON_DOTENV_DISABLED=1`):

```
python -P FP/tools/precheck.py FP/armfm-shop-gate 809dfe3 shop:experiments/benchmark/shop/bundles-freeze/arm-fm/shop-boil
python -P FP/gate/arms-60/armfm_gate.py FP/armfm-shop-gate shop:experiments/benchmark/shop/bundles-freeze/arm-fm/shop-boil
python FP/armfm-shop-gate/make_c8_rows.py <bundles-freeze/arm-fm> FP/armfm-shop-gate FP/armfm-shop-gate/c8-rows-3.jsonl shop-boil
python FP/gate/arms-60/append_c8.py FP/armfm-shop-gate/c8-rows-3.jsonl
```

(PYTHONPATH `app` for armfm_gate, `app:FP/tools` for precheck. Both scripts rewrite their summary files with only
the items given.) `make_c8_rows.py` writes only the generic start-final row. Any other failure needs its own read,
added to `EXTRA` and `GATE_TEXT` first.

- **If it passes:** the copies would be FARM's levels 2-5 settings with `arms: [arm-fm]`,
  `bundles: experiments/benchmark/shop/bundles-freeze`, `only: [shop-boil]`, 3 seeds, 5M steps.
  `shop-60-freeze.yaml` takes `suite: shop` and `ppo-shop.yaml` (as `farm/shop-runs-levels2-5.yaml`).
  `shop-60-freeze-shop-reward.yaml` takes `suite: shop-reward`, `ppo.yaml` and `reward_source: both` (as
  `farm/shop-runs-levels2-5-shop-reward.yaml`). That is 3 + 3 runs, and two jobs: the held `armfm-shop-60` (suite
  `shop`) plus one more with suite `shop-reward`.
- **If it fails but lets the agent act:** a side copy `shop-60-freeze-side.yaml` (`suite: shop-side-freeze`) needs a
  bundle copy without its status file, embedded, in a side folder first (workflow.md "Side test of a
  `pipeline-failed` ARM-FM bundle"): run-suite refuses `pipeline-failed`, and its `embeddings.json` is `{}`.
- **If it starts final:** nothing trains. All 11 cards count as not learned.

## Gate records (all in `FP/armfm-shop-gate/`)

- C1 pre-check (`precheck.py`, freeze `809dfe3`): `shop/<bundle>.precheck.json`, `precheck-summary.json`. Stamp and
  level page clean on every bundle (commit at or after the freeze, not dirty, reasoning max,
  `deepseek-v4.1-flash`/`glm-5.3-flash`). The FARM-only pricing, scale and `compiler_text` records do not apply to
  ARM-FM (`ok*`, as for the pilot). The embeddings stage is missing because the plan check failed.
- C2 (`gate/arms-60/armfm_gate.py`; `gate_all.py` crashes on ARM-FM): `shop/<bundle>.armfm_gate.json`,
  `armfm-gate-summary.json` (both summaries cover all 22). Facts and labeling pass everywhere. On the 21 start-final
  bundles, pay order ("finished 0 > not started 0") and plan check (seeds 1-5 and 42) fail, both from the start-final
  state. `shop-boil~p3` passes pay order (129.65 > 0) and fails the plan check (wrong plans reach the final).
- C3: shop has no trace bank; C2's labeling check plus `check_shop.py --out FP/armfm-shop-gate/shop-live`: all
  checks passed (300 seeds per level; it checks the levels and cards, not the bundles).
- C5 too-simple not run: `check_too_simple.py` reads only `<suite>/bundles`, not `bundles-freeze`; the start-final
  state already decides.
- C8: 22 rows, one per bundle, appended to `gate/machine-review/results.jsonl` through `gate/arms-60/append_c8.py`
  (staged in `c8-rows-1.jsonl` (21) and `c8-rows-2.jsonl` (`shop-boil~p3`), built by `make_c8_rows.py`). Key `("shop", "bundles-freeze/<bundle>", "arm-fm")`:
  the old pre-freeze rows already hold `("shop", "<bundle>", "arm-fm")`, and `append_c8.py` would skip a second row
  with that key. Verdict anomaly, retire true, `retire_for: machine`, finding `start-is-final` (explanation names the
  format limit); `shop-boil~p3` has `early-final` instead. Main bundles carry their extra findings; paraphrase reads
  stopped at the blocker.
- `summary.py` prints one line per bundle (status, stamp, states, start and finals, gate checks).
- Generation commits differ (`029d82c` to `881b22d`): main moved while the background generation ran. In `app/`
  only a box-carry world (`507886e`) and the tagger default (`f634e0f`, critic information on) changed, so bundles from `2c267e1` on may carry state
  texts written with it. The machines are not affected. The pre-check found the stored level page equal to today's on
  all 22.
