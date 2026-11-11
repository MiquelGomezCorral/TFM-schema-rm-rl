# L1.1 close test: simulation = code

Result: PASS
Test id: L11. Packet: `plans/rule-only-rewards/packet-tester-close.md`. Plan: `plans/rule-only-rewards/plan.md`.

## Command

```
cd /home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl-rule-only
PY="$HOME/miniconda3/envs/RM_RL_env/bin/python -W ignore -B" PYTHONPATH=app
$PY $L/tests/s1_l1_1.py > $E/out.txt 2>$E/err.txt; echo exit=$?
```

`L` = `.git/agent-memory/artifacts/rule-only-rewards-live`, `E` = `$L/evidence/close/L11`.

## Environment

- Worktree `rule-only` on `feat/rule-only-rewards`, HEAD `a56bbed`.
- Conda env `RM_RL_env`, Python 3.13. No `.env` read, no LLM calls.

## Expected vs observed

| Check | Expected | Observed |
|---|---|---|
| Exit code | 0 | 0 (`exit.txt`) |
| Machines | 20 | 20 |
| Differ from today's text | 9 | 9 |
| Equal their P2 text | 20 | 20 |
| Witness `a & !b & !g` first-step reward | 0 | 0.0 |
| Witness passes | True | True |

Output: `$E/out.txt` (25 lines, last line `PASS: the real code, no patch, compiles all 20 machines to exactly their P2 text; 9 changed, 11 unchanged;`). `err.txt` is empty.

## Side effects and cleanup

- Only writes: `$E/out.txt`, `$E/err.txt`, `$E/exit.txt`, this report.
- No processes started, no product, test, sample or decision-record edits, no Git actions.
- Nothing to clean up.

## Gaps

- None for L1.1. Other close tests (L1.2-L1.4, L2.x) not run; not in this task.

Memory candidates: none
