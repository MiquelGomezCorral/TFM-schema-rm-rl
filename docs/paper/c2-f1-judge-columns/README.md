# The judge columns of the suite table were empty, and now they fill

Date: 2026-11-12, from the C2 review fix (finding F1, fix commit `0f7e56b`, final fix head `7ae1157`).
Two real judge files from two finished DQN runs: a check that the aggregator reads the judge files
the writer emits, not a result about the two arms.

## What it shows

`test-rl --judge` writes `judge.json` for a run. `aggregate-suite` is meant to copy four numbers from
it into the results table: judged success, hard breaks, soft breaks and open items at the end. The
final strong review found that the aggregator read keys the writer never wrote (`judged_success`,
`hard_breaks`, ...), while the writer wrote `mean_judged_success`, `mean_hard_breaks`,
`mean_soft_breaks`, `mean_hard_open` and `mean_soft_open`. So all four columns came out `null` on
every run, however good the judge file was.

The check feeds `aggregate-suite` two judge files a real run produced and compares each column with
the file's own number (open at end = `mean_hard_open + mean_soft_open`):

| Arm | Column | In the judge file | Before the fix | After the fix |
| --- | --- | --- | --- | --- |
| no RM | judged success | 1.0 | null | 1.0 |
| no RM | hard breaks | 0.0 | null | 0.0 |
| no RM | soft breaks | 0.0 | null | 0.0 |
| no RM | open at end | 0.0 | null | 0.0 |
| FARM machine | judged success | 0.0 | null | 0.0 |
| FARM machine | hard breaks | 0.0 | null | 0.0 |
| FARM machine | soft breaks | 0.0 | null | 0.0 |
| FARM machine | open at end | 1.0 | null | 1.0 |

The check printed `"pass": false` before and `"pass": true` after, with both arms `ok`.

## The task, the clauses and the machine

Both judge files judge the same card, `base-doorkey`, on the benchmark's own judge.

- **Natural-language task:** "Use the key to open the door, then reach the goal."
- **LTL (the card's expected clauses, all hard):** `Precedence(has_key, door_open)` =
  `((~door_open) U has_key) | (G ~door_open)`; `Precedence(door_open, at_goal)`; `Existence(at_goal)` =
  `F at_goal`.
- **No-RM arm:** no Reward Machine; a DQN run on the environment reward alone. Its single judged
  episode (19 steps) holds all three clauses.
- **FARM arm:** the pilot bundle `doorkey-base`, FARM compiler with `deepseek-v4.1-flash`, from the
  same task text. [Graph](graphs/farm.html), [RM text](graphs/farm.rm.txt) (5 states, final `u4`,
  rejecting `u2`). That bundle predates stored clauses, so the clause list it compiled is not in its
  manifest; the card's clauses above are what the judge checked. The DQN run on this machine did not
  finish the task: 640 steps, the two Precedence clauses hold, `Existence(at_goal)` is open at the end
  (mean RM return -3.0).

## What this does not show

- Two runs of one learner, one seed, one episode each. The numbers prove that the columns are read
  correctly. They say nothing about whether the machine helps: the FARM run failed and the no-RM run
  succeeded, on one episode each.
- The fix does not change how the judge decides; it changes how the table reads the judge's file.
- "Open at end" is one number, hard plus soft open items, as the record names it.

## Files

- `evidence/judge-no-rm.json`, `evidence/judge-farm.json`: the two judge files, as the runs wrote them.
- `evidence/f1-before.json`, `evidence/f1-after.json`: the check's verdicts before and after.
- `check/f1_aggregation.py`, `check/_common.py`: the check.
- `graphs/`: the FARM machine of the judged run, as live HTML, SVG and RM text.

## Rerun

The check copies two finished runs (`outputs/runs/li-l54-dqn`, `outputs/runs/li2-l54-dqn`) and the
no-RM judge file (`outputs/wave-tests/final-review/aggregation/judge.json`) from the repository's git-ignored
`outputs/`, so it runs where those exist (the wave worktree); the two judge files are kept in
`evidence/`. It needs no model call. From the repository root, inside `RM_RL_env`, on the code before
the fix (`git checkout 0f7e56b^`) and after (`0f7e56b` or later):

```bash
PYTHONPATH=app python docs/paper/c2-f1-judge-columns/check/f1_aggregation.py before
PYTHONPATH=app python docs/paper/c2-f1-judge-columns/check/f1_aggregation.py after
```

The argument only names the output folder (`outputs/wave-tests/c2-review-fix/<phase>/f1.json`); the
verdict depends on the checked-out code. Do not rerun in a worktree with uncommitted changes you want
to keep.

## Code

`judge_columns` and `judge_means` in `app/scripts/aggregate_suite.py` and `app/scripts/test_rl.py`,
fixed in commit `0f7e56b` (`fix(run-suite): read the judge means in aggregate-suite and skip no-op
ablation variants`), part of the C2 review fix whose final head is `7ae1157`.
