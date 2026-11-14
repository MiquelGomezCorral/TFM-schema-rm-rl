# Learner probe X2: DQN on 8 environments is faster; counterfactual experience hurts

Date: 2026-11-12. Real training runs (500k steps each) on the two pilot cards with the pilot's FARM Reward
Machines; no provider call, no model call. Numbers are copied from the X2 worker's report and evidence folder;
the runs were not repeated for this entry. The three code checks K1 to K3 are scripts whose saved outputs are
included (see Gaps).

## What it shows

Two changes to the DQN learner were tried against the pilot DQN (R46 fraction 0.77, 14.7 min per 500k steps;
pilot PPO 0.413):

1. **8 training environments in one learner** (`dqn_num_envs: 8`), with the update schedule counted in
   environment steps. Faster, and it learns as well.
2. **Counterfactual experience (CRM, Toro Icarte et al., JAIR 2022)**: besides the real transition, store one
   copy for every other non-final, non-rejecting machine state (3 extra rows per step on these machines). It
   did not help here; it hurt.

| DQN setting (R46 fraction solved, mean of seeds 1 and 2) | DoorKey | UnlockPickup | Minutes per 500k (DoorKey) |
| --- | --- | --- | --- |
| 1 environment (control, same load) | 0.81 | not run | 33.1 |
| 8 environments, update ratio 4 | 0.79 | 0.69 | 17.9 |
| **8 environments, `train_frequency: 8` (`dqn8-tf8`)** | 0.78 | 0.69 | 8.8 |
| 8 environments, `train_frequency: 16` | 0.70 | 0.55 | 7.0 |
| 8 environments, `dqn8-tf8` plus exploration 0.2 | 0.81 | 0.42 | 9.7 |
| 1 environment + CRM | 0.24 | 0.00 | 33.5 |
| 8 environments + CRM | 0.00 | 0.00 | 18.4 |
| 8 environments + CRM, 300k replay buffer | 0.27 | 0.00 | 16.0 |

- **Speed, same load.** 1 environment against 8 with the same update ratio: 33.1 against 17.9 minutes per
  500k steps (**1.85 times**). In a concurrent 100k-step check (all three started the same minute): 144.1 s for 1
  environment, 99.0 s for 8 (1.46x), 75.0 s for 8 with `train_frequency: 8` (**1.92x**). Wall time includes
  start-up, so the 100k check understates a 500k run.
- **Learning, same.** The two-card mean of `dqn8-tf8` is 0.735 (pilot DQN 0.77); seed 3 confirms it (DoorKey
  0.78, UnlockPickup 0.68). Differences under about 0.05 are noise at two seeds.
- **CRM, no.** Two-card mean 0.00 (8 envs), 0.12 (1 env), 0.135 (8 envs, 300k buffer). The report's likely cause
  (replay diluted by two counterfactual copies per step; these machines are linear, so the copies add little
  reward information) is a hypothesis, not tested. A fair test of CRM's gain would need a machine with
  branching or cycles; neither pilot card has one.
- **Procedural layouts are much harder** for the best setting (`dqn8-tf8`, seeds 1, 11, 21, held-out layouts
  for evaluation): mean evaluation success 0.22 on DoorKey and 0.07 on UnlockPickup; final 100-episode
  evaluation 0.45 and 0.44 averaged over seeds, from 0.25 to 0.75 on DoorKey and from 0.01 to 0.82 on
  UnlockPickup. Three seeds do not pin a mean; the spread is the finding.
- **Seeding finding.** The new 8-environment code seeds sub-environment i with `seed + i`, so neighbouring run
  seeds share layouts: run seeds 1 and 2 share 28 of 32 distinct training layouts; 1 and 11, 1 and 21, 11 and
  21 share none. The procedural runs therefore use seeds 1, 11, 21. A one-line fix (`seed * dqn_num_envs + i`)
  was proposed and **not applied**.
- **Memory.** 100k-buffer runs peak at 2.2 to 2.3 GB; CRM with a 300k buffer at 3.45 GB. A stored transition
  takes 6458 bytes.

## Task, formula and machine

The two cards are the pilot's, with the pilot's FARM Reward Machine (symbolic observation, fixed layout, layout
seed 1).

**`base-doorkey`** (MiniGrid DoorKey 8x8): "Use the key to open the door, then reach the goal."
`Precedence(has_key, door_open)`, `Precedence(door_open, at_goal)`, `Existence(at_goal)`, all hard.
Machine (5 states): [interactive graph](graphs/base-doorkey.html), [SVG](graphs/base-doorkey.svg),
[RM text](graphs/base-doorkey.rm.txt). The CRM check `K2` below uses this machine's states `u0`, `u1`, `u3`,
`u4`.

**`base-unlock-pickup`** (MiniGrid UnlockPickup): "Acquire the matching key, unlock the door, and pick up the
designated box in the other room." `Precedence(has_door_key, door_open)`,
`Precedence(door_open, target_picked_up)`, `Existence(target_picked_up)`, all hard.
Machine (5 states): [interactive graph](graphs/base-unlock-pickup.html),
[SVG](graphs/base-unlock-pickup.svg), [RM text](graphs/base-unlock-pickup.rm.txt).

<details>
<summary>RM text</summary>

[`graphs/base-doorkey.rm.txt`](graphs/base-doorkey.rm.txt) and
[`graphs/base-unlock-pickup.rm.txt`](graphs/base-unlock-pickup.rm.txt) hold the machines with rewards, both
drawn with `render-rm --html`.

</details>

## Evidence

- `evidence/results.md`, `evidence/runs.csv`, `evidence/variants.csv`: per setting, card and seed.
  `evidence/eval-points.csv`: every evaluation point.
- Code checks (saved output): `evidence/k1-defaults-output.txt` (defaults identical to `7ae1157`),
  `evidence/k2-crm-output.txt` (CRM adds exactly 3 transitions per step on a scripted DoorKey episode, 5 steps
  give 15 rows), `evidence/k3-envs-output.txt` (same episode counts, rows, 1249 gradient updates and 2 target
  syncs for 1, 8 and 8+CRM environments).
- `evidence/replay-adds.txt` (1.000 rows per step plain, 3.000 with CRM), `evidence/timing-check.txt`,
  `evidence/reset-check.txt` (32 distinct layouts procedural, 1 fixed; seed overlap),
  `evidence/buffer-bytes-doorkey.txt`.
- `evidence/code-changes.md`: what changed in the learner; `check/code-changes.patch` (590 lines) is the diff.
- `evidence/settings/`: a few run configurations (control, `dqn8-tf8`, CRM).
- Base commit `7ae1157`; the change is commit `236dda1`
  (`feat(learner): run DQN on several environments at once, with optional counterfactual Reward Machine
  updates`) on branch `MiquelGomezCorral/tp-x2-dqn-crm`.

## Files

- `check/`: `k1_compare.py`, `k2_crm_check.py`, `k3_check.py`, `reset_check.py`, `replay_adds.py`, `analyze.py`
  (builds `results.md`), `code-changes.patch`, `runs/<suite>/runs.yaml` and `runs/procedural/tasks.json` (the
  training suites).
- `evidence/`, `graphs/` as above.

## Rerun

The learner change is not in `main`; it is `check/code-changes.patch`, which applies to base commit `7ae1157`
(checked with `git apply --check` on a copy of `7ae1157`; it no longer applies to current `main`, where
`dqn.py` and `runtime.py` changed). The suite files are `check/runs/<suite>/runs.yaml` and
`check/runs/procedural/tasks.json`. From the repository root, inside `RM_RL_env`:

```bash
ROOT=$PWD; COPY=$(mktemp -d); git archive 7ae1157 app tests experiments pyproject.toml | tar -x -C "$COPY"
(cd "$COPY" && git apply "$ROOT"/docs/paper/x2-dqn-crm/check/code-changes.patch)
mkdir -p "$COPY"/experiments/benchmark/tuning/dqn && cp -r "$ROOT"/docs/paper/x2-dqn-crm/check/runs/. "$COPY"/experiments/benchmark/tuning/dqn/
(cd "$COPY" && PYTHONPATH=app python -W ignore "$ROOT"/docs/paper/x2-dqn-crm/check/k2_crm_check.py)   # CRM adds 3 rows per step
(cd "$COPY" && experiments/benchmark/scripts/train.sh tuning/dqn/<round1|round2|round3|round4|control|confirm|procedural|timing> --parallel 4)
```

`k2_crm_check.py` was rerun on `7ae1157` plus the patch for this entry and printed exactly the saved output
(`evidence/k2-crm-output.txt`, ending `K2 ok: 5 scripted steps, 15 buffer rows = 5 x 3`). `k1-defaults.yaml`
in `check/` is its configuration. The other checks were not rerun, and neither was `train.sh` on the copy.

The `train.sh` runs are training only (7 to 33 minutes each), no LLM call. The checks `K1` to `K3` need no
training. The commit `236dda1` on branch `MiquelGomezCorral/tp-x2-dqn-crm` holds the same files.

## Gaps

- The runs were not repeated for this entry.
- The 1-environment control was not run on UnlockPickup, so that comparison rests on the pilot's two-card mean
  (0.77), not on a per-card value.
- Rounds ran at different machine loads (about 20 GB of other projects in the background); only the control and
  the timing check are same-load. The `dqn8-tf8` wall time moved between 7.1 and 10.3 minutes across rounds.
- Two seeds per setting (three for the confirm and the procedural runs). The round 3 (300k buffer) and round 4
  (exploration 0.2) settings were chosen after reading rounds 1 and 2.
- `pytest` was not installed in `RM_RL_env` and `tests/test_rl_contract.py` was skipped locally, so the test
  suite was not run; `ruff` and the config-defaults hook passed.
- The code change (`check/code-changes.patch`) is not merged into `main`; it is also commit `236dda1` on branch
  `MiquelGomezCorral/tp-x2-dqn-crm`. The freeze is `a77709b`. A decision record is needed if 8 environments or CRM enter the final pipeline.
- The interactive curve pages (4 MB each) are not copied; `evidence/eval-points.csv` rebuilds them.
