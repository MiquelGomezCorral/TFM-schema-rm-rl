# L2.1 RM text format (close wave, test id L21)

Result: PASS. Expected "VERDICT: PASS (54/54 checks pass)", observed exactly that, exit 0.

Commands (from worktree root `TFM-schema-rm-rl-rule-only`, `PYTHONPATH=app`):
- `mkdir -p $E && $PY $L/tests/s2_l2_1.py $E > $E/out.txt; echo exit=$?`
  with `PY="$HOME/miniconda3/envs/RM_RL_env/bin/python -W ignore -B"` (`-B` so no bytecode is written).
- No LLM call, no `.env`, no embeddings server.

Environment: HEAD `a56bbed` on `feat/rule-only-rewards`, conda env `RM_RL_env`.
Sample: `$L/tests/s2_l2_1.py` with the Slice 2 oracle `tests/s2_common.py` and `sim/slice2-examples.txt`.

Checks: A-F all PASS. Check F (L1.2 rerun): 42/42 machines with a final byte-identical; 23 of 23 machines with no final changed.
The two lines matching "FAIL" in out.txt are check names (`HARD_FAILED_REWARD`), not failures.

Evidence:
- $E/out.txt (full check output)
- $E/bundle/ (saved bundle, incl. reward_machine.txt)
- $E/l1_2-dump.txt (L1.2 dump)

Side effects: writes only inside $E. Nothing else touched.
Cleanup: nothing started, nothing to stop.
Gaps: none for this test.

Memory candidates: none
