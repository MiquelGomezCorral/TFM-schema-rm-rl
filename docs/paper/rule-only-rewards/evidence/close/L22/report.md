# L2.2 runtime (close wave, test id L22)

Result: PASS. The script reports `VERDICT: PASS (24/24 checks pass)`, exit 0.

## Commands

```sh
cd /home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl-rule-only
PY="$HOME/miniconda3/envs/RM_RL_env/bin/python -W ignore -B"
export PYTHONPATH=app
L=/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl/.git/agent-memory/artifacts/rule-only-rewards-live
E=$L/evidence/close/L22
mkdir -p $E && $PY $L/tests/s2_l2_2.py > $E/out.txt; echo exit=$?
```

Environment: worktree at `feat/rule-only-rewards`, HEAD `a56bbed`. Conda env `RM_RL_env`. No LLM calls (the test is deterministic).
Sample: `tests/s2_l2_2.py` only; the case 8 bundle is read from the primary checkout (read only).

## Observed

- Exit 0, 24/24 checks PASS, no FAIL lines (the two "FAILED_REWARD" hits are case titles, not results).
- Plan cases, last-step reward / `rm_accept` / `is_success` (from `out.txt`):
  - 1 (hard key, idle): -1 / False / False
  - 4 (key, door, idle): +0.1 / True / True
  - 6 (HARD_FAILED_REWARD -2): -2 / False / False
  - 7 (goal task idle): -0.5 / False / False
  - 11 (hard well on last step): -1 / False / False
  - 12a (soft ChainResponse, broken): -0.4 / True / True
  - 15 (multi-task same-step reset): the script prints no last-step reward line for this case; only `rm_accept=True is_success=True` and "the autoreset drew 'next'". Gap: reward not recorded.

## Evidence

- `$E/out.txt` (full script output)

## Side effects and cleanup

- Writes only `$E` (evidence dir). Worktree `git status` is clean. No `outputs/runs/l2-3-smoke/` created. No processes started.
- No edits to product code, samples, tests, or decision records. No Git actions.

## Gaps

- Case 15 last-step reward not printed by the script (see above). Result for case 15 rests on its PASS verdict and `rm_accept`/`is_success` only.

Memory candidates: none
