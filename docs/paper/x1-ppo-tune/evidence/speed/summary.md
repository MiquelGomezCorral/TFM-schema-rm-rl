# Same-load speed check: pilot DQN against s07, UnlockPickup, seed 1

Both runs started together at 14:36:41 (suite `x1-speed`, `--parallel 2`) on the same machine, with X2 and C3 running. 500k steps.

| learner | wall min | peak GB | fraction solved | first greedy solve (k) | final eval | eval rows vs earlier run |
|---|---|---|---|---|---|---|
| pilot DQN (buffer 100000) | 9.9 | 2.2 | 0.76 | 110 | 1 | identical to the pilot's DQN seed 1 (columns 1 to 9) |
| s07 | 4.4 | 2.3 | 0.67 | 152 | 1 | identical to the round 1 s07 seed 1 run |

- s07 is 2.2 times faster than DQN at the same load. The pilot's 14.7 min for DQN was measured with 4 runs at once; with 2 at once it takes 9.9 min.
- s07 split (sum over iterations): collect 176 s (CPU env steps) + update 74 s (GPU). The round 1 run of the same setting took 300 s + 116 s under heavier load.
- Fraction is over eval rows with step ≤ 500k (49 for PPO, 50 for DQN).

Source: `outputs/runs/bench__x1-speed__base-unlock-pickup__farm__{dqn,s07}/seed1-*/` (`resources.json`, `eval.csv`, `train.csv`); suite file `inputs/runs-speed.yaml`.
