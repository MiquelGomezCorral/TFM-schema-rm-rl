# Idle-passable tasks: 18 of the 53 no-goal tasks (`idle-passable-tasks/`), 2026-11-25

## What it shows

The thesis says an idle agent passes 18 tasks of the benchmark, 17 of the templates group and one of the complex group,
and that this is why those tasks do not train. The task notes mark only 14. This entry measures it: an agent that only
waits is judged on every no-goal task, with the judge's own code, on the 100 test seeds a trained agent is judged on.
No training and no model call.

**The 18 holds.** An idle agent passes 18 no-goal tasks, 17 in `templates` and 1 in `complex` (`cx-rules-only`). Each
passes at exactly 1.00 (100 of 100 episodes); every other hard task scores exactly 0.00. No task lies between, so the
0.8 bar does not decide any of them. None of the 18 is among the 60 trained rows. The 14 of the notes are all inside
the 18; the notes miss 4: `tpl-response-2-nogoal` and `tpl-chain-response-1-nogoal`, `-2-nogoal`, `-3-nogoal`.

## Definitions

- **Tasks.** The 124 distinct IDs of the 126 cards in the group task files at commit `9841d4b3` (`base`, `pilot`,
  `complex`, `templates`, `box-carry`, `forcing`, `forced-start`, `shop`). `pilot` repeats `base-doorkey` and
  `base-unlock-pickup` on a fixed layout; both have a goal, so they are not judged.
- **No goal.** The card's `goal` is false: 53 tasks. The other 71 have a goal, which an idle agent never reaches, so
  they are counted as "has a goal" and not judged.
- **Idle agent.** The plan that only waits (`_IDLE_STEPS`, `app/src/benchmark/plan_check.py`), played in the card's env
  until the env ends the episode.
- **Judged.** `judge_trace` on the card's `expect` clauses over the reference labels, as `JudgeRecorder` in
  `app/scripts/test_rl.py` does for a trained agent. Seeds 2,000,000 to 2,000,099 (`eval_seed_base` + i, 100 episodes),
  the seeds of the judge's own idle block. Judged success is every hard clause holding.
- **Passes.** Idle judged success 0.8 or more, the bar a training run must clear.
- **Soft-only.** No hard clause. Every judged episode succeeds, so there is no pass or fail; the idle soft figures are
  reported instead (`IDLE_EVERY` of the results builder holds them).
- **Trained.** The task is one of the 60 rows of `records.learned_rows()` (the `shop-reward` rows count for `shop`).

## Counts

| group | no-goal | with a hard clause | soft-only | idle passes | at 1.00 |
|---|---|---|---|---|---|
| complex | 1 | 1 | 0 | 1 | 1 |
| templates | 32 | 25 | 7 | 17 | 17 |
| box-carry | 3 | 3 | 0 | 0 | 0 |
| forcing | 4 | 3 | 1 | 0 | 0 |
| forced-start | 2 | 2 | 0 | 0 | 0 |
| shop | 11 | 11 | 0 | 0 | 0 |
| total | 53 | 45 | 8 | 18 | 18 |

71 tasks have a goal: `base` 7, `complex` 5, `templates` 48, `box-carry` 11 (the 2 `pilot` cards repeat `base` ones).

Idle passes (all at 1.00): `cx-rules-only`; `tpl-absence-1/2/3-nogoal`; `tpl-response-1/2/3-nogoal`;
`tpl-precedence-1/2/3-nogoal`; `tpl-chain-response-1/2/3-nogoal`; `tpl-responded-existence-1/3-nogoal`;
`tpl-not-co-existence-1/2/3-nogoal`. Idle fails (0.00) the hard `Existence` and `ExistenceTwo` cards,
`tpl-responded-existence-2-nogoal` (the siren rings by itself, so the rule is triggered), and every hard card of
`box-carry`, `forcing`, `forced-start` and `shop`.

14 of the 18 are vacuous passes: their non-empty share (a hard clause with a trigger must have triggered) is 0.00 in
`evidence/idle.json`, because idle never starts the `Response`, `Precedence`, `ChainResponse`, `RespondedExistence` or
`NotCoExistence` condition. The 3 `Absence` cards and `cx-rules-only` have a rule with nothing to trigger, so their
non-empty share is 1.00.

**Trained tasks idle passes: none.** Of the 53 no-goal tasks 22 are trained; each is either soft-only or fails idle.

**Soft-only tasks (8, all trained).** Idle soft breaks per episode (every break, as the machine charges them) and soft
rules unmet per episode (broken or still open at the end):

| task | idle soft breaks | idle soft rules unmet |
|---|---|---|
| `tpl-existence-soft-1-nogoal` | 0.00 | 1.00 (open) |
| `tpl-existence-two-soft-1-nogoal` | 0.00 | 1.00 (open) |
| `tpl-responded-existence-soft-1-nogoal` | 0.00 | 1.00 (open) |
| `keygift-soft` | 0.00 | 1.00 (open) |
| `tpl-chain-response-soft-1-nogoal` | 1.00 | 1.00 (broken) |
| `tpl-not-co-existence-soft-1-nogoal` | 7.49 | 1.00 (broken) |
| `tpl-absence-soft-1-nogoal` | 26.18 | 2.00 (broken) |
| `tpl-precedence-soft-1-nogoal` | 26.18 | 2.00 (broken) |

These 8 rows equal `IDLE_EVERY` (the judge's stored idle block) on all four of its figures; the script asserts it.

## Evidence

- `evidence/idle.md`: one row per no-goal task: group, ID, hard or soft-only, trained, idle judged success, passes, and
  the soft figures of the soft-only tasks.
- `evidence/idle.json`: the same with the counts, the non-empty share, the idle soft means of every task and the lists
  below.
- Cards: all 124 frozen IDs are unchanged in the current task files (0 differ). The `shop` file has 36 more cards now
  (the grid, ladder and curriculum cards added after `9841d4b3`); they are not part of the 124 and were not measured.
- The idle plan of the plan check (`_IDLE_STEPS`) and the judge's `SOFT_ONLY_IDLE_PLAN` differ in length: 1,000 steps
  against the env's own end. They agree on all 8 soft-only tasks (episodes of 200 to 300 steps); on KeyCorridorS6R3
  (1,080 steps) the judge's plan stops 80 steps early, so the entry uses the full wait, which is what a judged agent
  plays. In all 53 x 100 idle episodes the env ended the episode (the script asserts it).
- Cross-check, one-off and not scripted here: reading `<group>/bundles/farm/<id>.plan_check.json` of the FARM bundles,
  the plan check's idle run (event or layout seeds 1 to 3) keeps every rule on the same 18 IDs.

**Gaps.** One fixed policy over 100 seeds, so there is no interval; the values are 0.00 and 1.00 anyway. The idle agent
plays without a Reward Machine, so the judge's "cannot start" rule, which needs a machine, does not apply.

## Files

`README.md`; `check/idle_tasks.py`; `evidence/idle.md`, `evidence/idle.json`; `evidence/tasks-9841d4b3/`, the 8 group
task files of the commit, verbatim from `git show 9841d4b3:experiments/benchmark/<group>/tasks.json`. No page.

## Rerun

No model call, no training, CPU only (a few minutes with 4 worker processes), from the repository root in
`RM_RL_env`. It needs `.git/agent-memory` (the results builder behind `records.learned_rows()` and `IDLE_EVERY`):

```bash
env CC_ROOT=$PWD OMP_NUM_THREADS=4 \
  PYTHONPATH=app:.git/agent-memory/artifacts/final-results:docs/paper/level-benchmark-freeze/check:docs/paper/results-figures \
  nice -n 19 python -P -W ignore docs/paper/idle-passable-tasks/check/idle_tasks.py
```

It prints one line per task and ends with `124 tasks (126 cards), 71 with a goal, 53 without: 45 with a hard clause,
8 soft-only`, `idle passes: 18 (at 1.00: 18)`, `trained tasks idle passes: none` and `OK: 8 soft-only idle rows
equal the judge's stored idle figures`.

## Code

Tasks at `9841d4b3` (`feat(shop): serving ladder cards, deliver to the full shop`). `_IDLE_STEPS` in
`app/src/benchmark/plan_check.py`; `judge_trace` in `app/src/benchmark/declare_judge.py`; `JudgeRecorder` and
`SOFT_ONLY_IDLE_PLAN` in `app/scripts/test_rl.py`; the 8 stored idle rows from
`freeze-prep/no-train/soft_every_break.json` (`soft_every_break.py`). Measured on main `2e62e243` (`app/` unchanged).
