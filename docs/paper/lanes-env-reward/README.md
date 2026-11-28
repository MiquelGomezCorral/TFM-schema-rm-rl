# Zombie lanes with the environment's reward added (`lanes-env-reward/`), 2026-11-25

## What it shows

FARM's machine for the two soft-only lane tasks charges a breach on the step it happens, long after the move that
allowed it. A side test asked whether paying the environment's own reward on top (1 per zombie killed,
`reward_source: both`) closes the gap to the agent trained with no RM. Both tasks, 3 runs each, 100 judged episodes per
run. No training and no model call for this entry: it recounts runs that already exist and plays the idle plan.

**Result.** The agents kill a little more on the absence task (9.63 against 7.95 zombies per episode, intervals do not
overlap) and about as many on the not-both task (9.54 against 9.05). The top lane is still breached in every episode
(0 of 100 episodes without a breach, in every run), about 8.65 times per episode, and that is what the idle agent
lets through: **8.66**. Per episode, on the same reset seed, the count of top-lane breaches equals the idle agent's
in 98 to 100 of 100 episodes of every run with the environment's reward, so these agents stop none, or almost none, of
the zombies that come down the top lane.

**Learned.** On a soft-only task the thesis and the 60 rows compare every break (`mean_soft_break_count`) with the idle
plan's every-break figure (user ruling of 2026-11-22; the once-per-rule count saturates in Lanes). By that rule **every
FARM run counts as learned**, with the environment's reward (6 of 6) and without it (6 of 6), and so do the no-RM runs
(6 of 6, three shared agents). FARM breaks fewer than idle overall (17.57 against 26.18 on absence, 5.78 against 7.49 on
not-both), all of it through the side lanes; the top lane is breached as often as idle's. The once-per-rule count
(rules broken at least once per episode) shows no gap for FARM: it equals idle's in all 12 FARM runs (2.00 of 2 on
absence, 1.00 of 1 on not-both), while the no-RM agents break 1.37 and 0.37.

**Idle agent.** One fixed plan that only waits, played on the judge's 100 reset seeds: **0.00 kills, 8.66 top-lane
breaches, 17.52 side-lane breaches** per episode, and **0 of 100 episodes without a top-lane breach**. The top and side
figures add to 26.18, the judge's idle soft-break total on the absence task. Against the thesis table
`tab:res-lanes-counts` (Idle column: 0, 8.7, 17.5, "--"): kills, top and side match; the "--" can be filled with 0.
"FARM's agents let as many through it as the idle agent" holds: FARM's agents 8.59 to 8.66 per run, the idle agent
8.66, and 0 of 100 episodes without a breach for both. The thesis sentence "the top lane is still breached in every
episode, about 8.6 times per episode, as often as with FARM's RM alone" holds too (8.64 to 8.66 per run with the
environment's reward, 8.59 to 8.66 alone).

## The tasks

Both are `templates` cards with no goal, environment `MiniGrid-Lanes-v0` (zombies walk down three lanes of a field;
the top lane is the protected one; each zombie nobody stops gets through 27 steps after it enters; the environment
pays 1 per kill and nothing else; 300 steps).

| | absence task | not-both task |
|---|---|---|
| ID | `tpl-absence-soft-1-nogoal` | `tpl-not-co-existence-soft-1-nogoal` |
| NL task | "Try not to let zombies through any lane." | "Try not to let zombies through both the top lane and the side lanes." |
| Expected clauses (`tasks.json`) | soft `Absence(top_breach)`, soft `Absence(side_breach)` | soft `NotCoExistence(top_breach, side_breach)` (two soft Absences are also accepted) |
| LTLf | `(~(F top_breach))`, `(~(F side_breach))` | `((F top_breach) -> (~(F side_breach)))` |
| FARM's clauses (its bundle) | soft `Absence(top_breach)`, soft `Absence(side_breach)` | the same two soft Absences |

FARM's machine is the same text for both tasks (`evidence/rm/`, from the bundle each judge file names in `rm_bundle`,
`experiments/benchmark/templates/bundles/farm/<ID>`). One state, no final state; each step with a top breach pays -1,
with a side breach -1, with both -2, and nothing else is paid:

```
REWARD_MACHINE:
STATES: u0
INITIAL_STATE: u0
FINAL_STATES:
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !side_breach&top_breach) -> u0
(u0, side_breach&!top_breach) -> u0
(u0, side_breach&top_breach) -> u0
REWARD_FUNCTION:
(u0, !side_breach&top_breach, u0) -> -1
(u0, side_breach&!top_breach, u0) -> -1
(u0, side_breach&top_breach, u0) -> -2
```

The absence machine as a graph: `../lanes-spacing/graphs/tpl-absence-soft-1-nogoal-farm.svg` (same text, byte for byte).
On the not-both task the judge reads the card's NotCoExistence, not FARM's two Absences; that is why its "rules
broken" figure has 1 rule where the absence task has 2.

## Methods and runs

| method | run groups under `outputs/runs/` | `reward_source` |
|---|---|---|
| FARM + environment's reward | `bench__templates-lanes-both__<ID>__farm__ppo` | `both` |
| FARM alone | `bench__templates__<ID>__farm__ppo` | `rm` |
| No RM | `bench__templates__<ID>__no-rm__ppo` | `env` |

3 seeds per group (18 runs); the script checks `reward_source` in every `seed*/config.yaml` against this column. The
`both` runs ran on 2026-11-22 from `evidence/lanes-both.yaml` (same settings as the counted FARM runs: PPO, 1.5M steps,
embedding state encoding, except `reward_source`). The runs record no code commit; the bundles were generated on the
freeze `809dfe3`.

**The no-RM runs are shared.** No machine, so the same three agents serve every task: each no-RM folder holds
`shared-run.json` naming `bench__templates__tpl-existence-two-5-nogoal__no-rm__ppo` as the owner, and the judge files
differ per task only in the rules read. The two no-RM rows are therefore one result, not two: kills, top and side
figures are identical; only the soft figures change.

## Results

Per judged episode, mean over the 3 runs [95% t interval over the runs, 2 degrees of freedom, low end clipped at 0].
Every break: the judge's `mean_soft_break_count`, every broken step as the machine charges it; idle's figure is in the
Idle row. Rules broken at least once: the judge's `soft_only.mean_soft_breaks`, soft clauses broken per episode. Runs
learned: by the every-break rule (see "Reading the figures"). Idle: one fixed plan, so no interval.

**`tpl-absence-soft-1-nogoal`**

| method | runs | kills | top-lane breaches | side-lane breaches | episodes with no top-lane breach (of 100) | every break | rules broken at least once (of 2) | runs learned |
|---|---|---|---|---|---|---|---|---|
| FARM + environment's reward | 3 | 9.63 [9.10, 10.15] | 8.66 [8.64, 8.67] | 8.92 [8.80, 9.03] | 0.0 [0.0, 0.0] | 17.57 [17.46, 17.69] | 2.00 [2.00, 2.00] | 3 of 3 |
| FARM alone | 3 | 7.95 [7.63, 8.26] | 8.61 [8.57, 8.65] | 10.13 [9.92, 10.34] | 0.0 [0.0, 0.0] | 18.74 [18.56, 18.92] | 2.00 [2.00, 2.00] | 3 of 3 |
| No RM | 3 | 17.63 [17.43, 17.82] | 0.53 [0.24, 0.81] | 9.99 [9.91, 10.07] | 63.0 [42.7, 83.3] | 10.52 [10.28, 10.76] | 1.37 [1.17, 1.57] | 3 of 3 |
| Idle (one fixed plan) | - | 0.00 | 8.66 | 17.52 | 0 | 26.18 | 2.00 | - |

**`tpl-not-co-existence-soft-1-nogoal`**

| method | runs | kills | top-lane breaches | side-lane breaches | episodes with no top-lane breach (of 100) | every break | rules broken at least once (of 1) | runs learned |
|---|---|---|---|---|---|---|---|---|
| FARM + environment's reward | 3 | 9.54 [8.97, 10.10] | 8.65 [8.62, 8.68] | 9.02 [8.80, 9.24] | 0.0 [0.0, 0.0] | 5.78 [5.67, 5.88] | 1.00 [1.00, 1.00] | 3 of 3 |
| FARM alone | 3 | 9.05 [7.22, 10.87] | 8.64 [8.56, 8.72] | 9.12 [6.86, 11.39] | 0.0 [0.0, 0.0] | 5.66 [4.56, 6.76] | 1.00 [1.00, 1.00] | 3 of 3 |
| No RM | 3 | 17.63 [17.43, 17.82] | 0.53 [0.24, 0.81] | 9.99 [9.91, 10.07] | 63.0 [42.7, 83.3] | 0.51 [0.21, 0.81] | 0.37 [0.17, 0.57] | 3 of 3 |
| Idle (one fixed plan) | - | 0.00 | 8.66 | 17.52 | 0 | 7.49 | 1.00 | - |

Per run, with the environment's reward (the thesis ranges): absence kills 9.41 to 9.83, top 8.65 to 8.66, side 8.87 to
8.96; not-both kills 9.35 to 9.79, top 8.64 to 8.66, side 8.96 to 9.12. No-RM runs: kills 17.54 to 17.69, top 0.42 to
0.65, episodes with no top-lane breach 54 to 70. `evidence/tables.md` has every run with its folder, its top-lane
count against idle's, its every-break figure against idle's, and its learned mark.

## Reading the figures

- **Top lane.** The agents with the environment's reward breach it 8.64 to 8.66 times per episode, the idle agent 8.66.
  On the same reset seed the count equals idle's in 99, 100, 100 (absence) and 99, 100, 98 (not-both) of 100 episodes;
  FARM alone does so in 95 to 100. In the other episodes the agent's count is lower, never higher.
- **Side lanes.** Both FARM variants cut them from the idle agent's 17.52 to about 9 to 10, like the no-RM agent (9.99).
- **Every break.** Fewer than the idle agent's (17.57 against 26.18; 5.78 against 7.49), in step with the side-lane
  cut. Against FARM alone: lower on absence (17.57 against 18.74), the same on not-both (5.78 against 5.66).
- **Rule learned.** The rule of the thesis and the 60 rows, from the user ruling of 2026-11-22: a soft-only run is
  learned when its every-break figure (`mean_soft_break_count`) and its open clauses do not exceed the idle plan's, one
  of the two is below it, and its label changes exceed the idle plan's. It is `seed_learned` in
  `.git/agent-memory/artifacts/final-results/build_results.py` (idle's every-break figures `IDLE_EVERY`, the rule
  `every_break.rule`); the script copies the rule so the entry opens on its own. Idle: every break 26.18 and 7.49, open
  0.00, label changes 49.71. All 12 FARM runs, with and without the environment's reward, and all 6 no-RM runs are
  learned (open is 0.00 for every run, so every break below idle's decides it). The `learned` field of
  `evidence/runs.json` holds the mark. The judge file's own definition (`soft_only.definition`) compares the
  once-per-rule count instead and finds no FARM run learned; that is not the rule the thesis uses.

**Gaps.** Three runs per method, so the t interval has 2 degrees of freedom and is wide; the intervals are over runs,
not over episodes. One fixed idle policy, so no interval (the figures are the mean of 100 seeded episodes, and the
reset seed fixes the zombie schedule, so agent and idle see the same zombies). The runs do not tell whether the late
charge or the equal price of both lanes keeps the agent from the top lane; the entry only shows that adding the kill
reward does not move it. `soft_only.mean_soft_breaks` counts clauses broken, not steps; the every-break column counts
steps. The learned mark rests on the every-break cut and on label changes above idle's: FARM runs have 49.86 to 50.82
against idle's 49.71, the no-RM runs 53.45 to 53.65, so FARM passes that condition narrowly. A learned mark here does
not mean the top lane is defended.

## Evidence

- `evidence/runs.json`: every figure above, per run and per method, with the cards, the intervals and the idle row.
- `evidence/tables.md`: the two tables above and one row per run (every break against idle's, learned mark, folder).
- `evidence/judge/<ID>/<method>-seed<n>.json`: the 18 judge files, verbatim copies of `seed*/judge.json`.
- `evidence/episodes.json`: per judged episode, the reset seed and the number of steps on which `zombie_killed`,
  `top_breach` and `side_breach` held, counted from the saved traces (not copied); and the idle plan's per-episode
  counts with the judge's soft figures.
- `evidence/cards.json`, `evidence/rm/<ID>.rm`: the cards' NL task, expected clauses, LTLf and FARM's clauses, and
  the machine text. `evidence/lanes-both.yaml`: the job file of the runs with the environment's reward.

**Checks the script makes.** The 18 runs have the expected `reward_source`, 3 judged runs per group and reset seeds
2,000,000 to 2,000,099. The idle replay equals the idle figures stored in each of the 18 judge files (soft clauses
broken, soft clauses open, label changes) and the idle soft-break totals of `soft-breaks-vs-idle/` (26.18, 7.49). On
the absence task, every episode's judge `soft_break_count` equals the trace counts of top plus side breaches. All 18
runs are learned by the every-break rule (the script asserts it, as the thesis and the 60 rows count them).

## Files

`README.md`; `check/lanes_env_reward.py`; `evidence/` as above. No page.

## Rerun

No model call, no training, CPU only, from the repository root in `RM_RL_env`. It needs `outputs/runs/` and the app
code:

```bash
env PYTHONPATH=app nice -n 19 python -P -W ignore docs/paper/lanes-env-reward/check/lanes_env_reward.py
```

It prints the two tables and the idle column against the thesis table, and ends with `OK: 18 runs summarized`. With
`--evidence-only` it rebuilds `runs.json` and `tables.md` from the copied evidence alone (no run folders, no
rollouts).

## Code

The reward key is `reward_source` (`REWARD_SOURCES` at `app/src/config/config.py:55`, the `rm` default at
`app/src/config/config.py:376`): `rm` the machine alone, `env` the plain environment, `both` the sum. The idle plan is
`SOFT_ONLY_IDLE_PLAN` (`app/scripts/test_rl.py`, 1,000 waits; the env ends these episodes at 300 steps), played with
`run_plan` and judged with `judge_trace`, as `JudgeRecorder._soft_only_summary` does. Tasks in
`experiments/benchmark/templates/tasks.json`. Measured on main `2e62e243`.
