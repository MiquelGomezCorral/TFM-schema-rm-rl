# Learner probe X1: PPO needed stronger updates, not a lucky value

Date: 2026-11-12. Real training runs (500k steps each) on the two pilot cards with the pilot's FARM Reward
Machines; no provider call, no model call. The numbers are copied from the X1 worker's report and evidence
folder; the runs were not repeated for this entry (see Gaps).

## What it shows

The pilot picked DQN over PPO on the R46 rule (share of evaluation points, up to 500k steps, where the greedy
policy succeeds): **DQN 0.77, PPO 0.413**. The pilot PPO never solved UnlockPickup. X1 asked whether simple
tuning of PPO solves both cards and stays faster than DQN.

- **Base reproduces the failure.** The pilot setting on seeds 1, 2, 3: DoorKey solved (final success 1 on
  every seed), UnlockPickup never solved (final 0 on every seed). Evaluation rows on seeds 1 and 2 are
  bit-identical to the pilot PPO.
- **Setting `s07` solves both cards on 3 of 3 seeds.** Knobs: learning rate 1e-3, minibatches 16, epochs 10,
  16 environments, rollout 256 (base: 2.5e-4, 4, 4, 8, 128).
- **The working region is wide.** 18 settings were tried; 9 solve UnlockPickup on both seeds, 3 on one seed, 6
  on neither. 5 of the 6 one-knob changes from `s07` still solve both seeds; only going back to the base
  learning rate (`r03`) fails. Settings that change GAE (0.99), gamma (0.995) or entropy (0.03) alone do not
  solve it.
- **It costs a little R46 and is much faster.**

| UnlockPickup / DoorKey (fixed layout) | Pilot DQN | `s07` PPO |
| --- | --- | --- |
| Solves DoorKey, final evaluation | yes | 3 of 3 seeds |
| Solves UnlockPickup, final evaluation | yes | 3 of 3 seeds |
| R46 fraction, both cards | 0.77 | 0.711 (0.724 on seeds 1 and 2) |
| UnlockPickup / DoorKey fraction | 0.73 / 0.81 | 0.64 / 0.78 |
| First greedy solve | 90 to 160k steps | 74 to 221k steps |
| Wall time, same load (2 runs at once), UnlockPickup seed 1 | 9.9 min | 4.4 min (**2.2 times faster**) |

The two settings that match DQN's R46 (`s01` 0.781, `s10` 0.750) take 13 to 17 minutes, as long as DQN.

- **Procedural layouts are weaker.** With `layout: procedural` (a new layout at every reset, seeds 1, 21, 41),
  `s07` solves DoorKey on 3 of 3 seeds (final evaluation 0.96, 0.96, 0.98) and UnlockPickup on **2 of 3**
  (0.89, 0.00, 0.90; seed 21 stays at 0 for 500k steps). There is no procedural DQN run to compare with.
- **Layouts really differ.** In 32 training resets a procedural run sees 32 distinct layouts and shares none
  with the other seeds; the fixed-layout control sees 1. Run seeds 1, 2, 3 would share 28 to 30 of the 32
  (environment i resets on run seed + i), which is why the procedural runs use seeds 1, 21, 41.

## Task, formula and machine

The two cards are the pilot's. Both use symbolic observations, a fixed layout (layout seed 1) and the FARM Reward
Machine from the pilot bundles (not drawn again by this entry's scripts; the graphs are the pilot's).

**`base-doorkey`** (MiniGrid DoorKey 8x8): "Use the key to open the door, then reach the goal."
`Precedence(has_key, door_open)`, `Precedence(door_open, at_goal)`, `Existence(at_goal)`, all hard.
Machine (5 states): [interactive graph](graphs/base-doorkey.html), [SVG](graphs/base-doorkey.svg),
[RM text](graphs/base-doorkey.rm.txt).

**`base-unlock-pickup`** (MiniGrid UnlockPickup): "Acquire the matching key, unlock the door, and pick up the
designated box in the other room." `Precedence(has_door_key, door_open)`,
`Precedence(door_open, target_picked_up)`, `Existence(target_picked_up)`, all hard.
Machine (5 states): [interactive graph](graphs/base-unlock-pickup.html),
[SVG](graphs/base-unlock-pickup.svg), [RM text](graphs/base-unlock-pickup.rm.txt).

<details>
<summary>RM text (base-doorkey)</summary>

[`graphs/base-doorkey.rm.txt`](graphs/base-doorkey.rm.txt) holds the full machine with its rewards;
[`graphs/base-unlock-pickup.rm.txt`](graphs/base-unlock-pickup.rm.txt) the other. Both come from
`render-rm --html`.

</details>

## Evidence

- `evidence/summary.md`, `evidence/r46_runs.csv`: one row per setting, card and seed (fraction, first solve,
  final evaluation, wall minutes, peak memory). `evidence/eval_points.csv`: every evaluation point, the input of
  the curves.
- `evidence/pilot-reference/`: the pilot's 8 `eval.csv` files; the DQN 0.77 and PPO 0.413 were recomputed from
  them.
- `evidence/speed/summary.md`: the same-load check (both started at the same minute).
- `evidence/procedural/`: summary, per-run table and `reset-check.txt`.
- `evidence/settings/`: the exact knobs of `base` and `s07`.
- Base for all runs is commit `7ae1157`; the suite files and scripts were committed on branch
  `MiquelGomezCorral/tp-x1-ppo-tune` as `306d402`.

## Files

- `check/`: `summarize.py` (builds the tables), `reset_check.py` (distinct layouts per run), the suite files
  `runs-*.yaml` and `tasks-procedural.json`.
- `evidence/`, `graphs/` as above.

## Rerun

From the repository root, inside `RM_RL_env`, on the X1 branch (the suites are not on `main`):

```bash
git checkout MiquelGomezCorral/tp-x1-ppo-tune   # holds experiments/benchmark/tuning/ppo/ (commit 306d402)
experiments/benchmark/scripts/train.sh tuning/ppo/<base|round1|round2|confirm|procedural|speed> --parallel 6 --max-ram-gb 12
```

Runs are deterministic: a rerun of `s07` seed 1 and of the pilot DQN seed 1 reproduced the earlier evaluation
rows exactly. Training only, no LLM call. About 4 to 17 minutes per run.

## Gaps

- The runs were not repeated for this entry; the numbers come from the X1 report and its evidence.
- Only 3 seeds on the fixed layout (2 in round 1 and round 2 for the other settings); seeds vary a lot inside
  one setting (`s05`: 0.63 and 0), so two seeds cannot rank close neighbours.
- No procedural DQN run, so the R46 comparison (0.77) is only for the fixed layout. Seeds beyond 3, other cards
  and longer training for procedural seed 21 were not tried.
- The wall times of the first rounds come from a loaded machine; only the same-load check (4.4 against
  9.9 minutes) is a fair speed comparison.
- The interactive curve pages (4 MB each) are not copied; `evidence/eval_points.csv` rebuilds them.
- The tuning code is on branch `MiquelGomezCorral/tp-x1-ppo-tune`, not merged into `main` at the freeze
  `a77709b`.
- The "gradient steps × learning rate" rule of thumb in the X1 notes was found after the fact and is untested;
  it is not stated here.
