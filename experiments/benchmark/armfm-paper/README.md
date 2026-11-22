# ARM-FM paper suite

The MiniGrid tasks of the ARM-FM paper that the benchmark lacked, so FARM, ARM-FM and no-RM can be
compared on the paper's own grid. Every card has `train: false`: none is in the counted 60.

| Card | World | Paper | Machine | Steps |
|---|---|---|---|---|
| `armfm-doorkey-5x5` | `MiniGrid-DoorKey-5x5-v0`, new map each episode | Fig 6, bottom row | own | 1.5M |
| `armfm-doorkey-5x5-fixed` | the same, one fixed map | Fig 6, top row | `armfm-doorkey-5x5`'s | 1.5M |
| `armfm-doorkey-8x8-fixed` | `MiniGrid-DoorKey-8x8-v0`, one fixed map | Fig 6, top row | `base/base-doorkey`'s | 1.5M |
| `armfm-doorkey-16x16` | `MiniGrid-DoorKey-16x16-v0`, new map each episode | Fig 6, bottom row | own | 5M |
| `armfm-doorkey-16x16-fixed` | the same, one fixed map | Fig 6, top row | `armfm-doorkey-16x16`'s | 5M |
| `armfm-unlock-to-unlock` | `BabyAI-UnlockToUnlock-v0`, new map each episode | Fig 7, Fig 19 | own | 5M |

DoorKey 8x8 with new maps is `base-doorkey` itself (Test 2). The steps are the user's (D3).

Task text: the DoorKey cards use `base-doorkey`'s text and the UnlockToUnlock card the dev
catalogue's restatement (`experiments/dev/arm-fm/babyai-unlock-to-unlock/tasks.json`, UTU-1). The
authors' mission text stays out of the cards: their repository has no licence.

Fixed map: `layout: fixed` with `layout_seed` 1. train-rl resets every training and evaluation
episode on that seed and test-rl judges on it. A fixed-map card trains on the bundles of the card
named in `bundle_of`, the same world on new maps, so generate-suite skips it. `bundle_of:
base/base-doorkey` reads another suite's bundles: run-suite takes `<suite>/<card-id>` as
`experiments/benchmark/<suite>/bundles/<arm>/<card-id>`.

UnlockToUnlock: the env pages are a copy of the dev catalogue's (`../envs/babyai-unlock-to-unlock/`),
and `app/src/benchmark/reference_labels.py` gained its reference labeler. Its layout is procedural,
like every benchmark card. The released ARM-FM labeling hard-codes the colours of layout seed 1, so
the paper may have trained on that one map (not verified). The plans name the colours of seed 1
(first door and key yellow, second red), so they run on that seed only.

## Contents

- `tasks.json`: the cards.
- `runs.yaml`: the 1.5M-step cards; `runs-5m.yaml`: the 5M-step cards. Both: 3 arms, seeds 1 to 3,
  PPO s07 (`../configs/ppo.yaml`), as the counted MiniGrid cards.
- `traces/`: the trace bank of the plans.
- `check/paper_cards_check.py`: the no-model checks (plan check on hand-written machines, labeling
  against the reference labeler on plan traces and 100 random walks, gates of the generated bundles).
- `bundles/<arm>/<card-id>/`: the generated machines (made by `generate-suite`).

Reproduce (`PYTHONPATH=app`, repository root):
`python app/main.py trace-bank --tasks experiments/benchmark/armfm-paper/tasks.json --output experiments/benchmark/armfm-paper/traces`,
`python experiments/benchmark/armfm-paper/check/paper_cards_check.py`, and
`python app/main.py run-suite --suite experiments/benchmark/armfm-paper/runs.yaml --dry-run`.
