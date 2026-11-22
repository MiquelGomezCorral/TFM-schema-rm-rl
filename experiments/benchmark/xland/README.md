# XLand suite

The ARM-FM paper's XLand-MiniGrid experiments (Figures 9 and 10) on our three arms. Each card is one
ruleset of `XLand-R4-13x13-v0` (13x13 grid, 4 rooms, 507 steps; `env_kwargs.ruleset`). The task texts are
reconstructed from the rulesets by `../scripts/render_xland.py`, since the paper does not print them.

| Card | Ruleset | Used in |
|---|---|---|
| `xland-x1-197` | medium-1m 197 | X1 alone, both mixes |
| `xland-x2-212`, `xland-x3-260` | medium-1m 212, 260 | 3-task and 5-task mix |
| `xland-x4-859`, `xland-x5-594` | medium-1m 859, 594 | 5-task mix |
| `xland-za`, `xland-zb` | Figure 10 (a), (b), rebuilt | ZA+ZB mix |
| `xland-zc` | Figure 10 (c), rebuilt | zero-shot test of the ZA+ZB policies; trained directly too |

Every card has `train: false`, so a runs file names its cards in `only` or `mixes`.

- `reference/<card>/`: a hand-written machine per card (`../scripts/build_xland_reference.py`, no model
  call). It has no state texts or embeddings, so it trains only with `rm_state_encoding: one_hot`.
- `traces/`: the trace bank of the cards' plans (`trace-bank`).
- `runs.yaml`: X1 alone, ZC directly and the three mixes, 3 arms x 3 seeds, 5M steps.
- `runs-mix5-noemb.yaml`, `runs-mix5-normreward.yaml`: the two 5-task-mix ablations (arm-fm arm only).

## ZC zero-shot

After `runs.yaml` has trained the ZA+ZB mix, test its policies on ZC without retraining. The judge card is
the `card.json` of the ZC run of `runs.yaml`:

```
ZC=outputs/runs/bench__xland__xland-zc__farm__ppo/card.json
python app/main.py test-rl --run bench__xland__xland-zab__farm__ppo --judge $ZC --bundle experiments/benchmark/xland/bundles/farm/xland-zc
python app/main.py test-rl --run bench__xland__xland-zab__arm-fm__ppo --judge $ZC --bundle experiments/benchmark/xland/bundles/arm-fm/xland-zc
python app/main.py test-rl --run bench__xland__xland-zab__no-rm__ppo --judge $ZC
```

The machine runs write `<run>/transfer/xland-zc/`; the no-RM run plays ZC's ruleset from the card and writes
`<run>/transfer/card-xland-zc/`.
