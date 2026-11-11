# Live test L1.2 + L1.3 (close wave), test id L12L13

Result: PASS (both checks, observed).

Environment: worktree `/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl-rule-only`, `PYTHONPATH=app`,
`PY="$HOME/miniconda3/envs/RM_RL_env/bin/python -W ignore -B"`. No LLM calls, no `.env` read.

Commands:
- `$PY $L/tests/rm_texts.py $E/dump.txt` -> exit 0
- `$PY $L/tests/rm_texts.py compare $L/tests/l0-baseline.txt $E/dump.txt` -> exit 0
- `$PY $L/tests/s1_l1_3.py $E/dump.txt` -> exit 0

L1.2 expected: exit 0, "42/42 machines with a final byte-identical", changed no-final list recorded.
L1.2 observed: exit 0, "42/42 machines with a final byte-identical; 23 of 23 machines with no final changed".
The 23 changed no-final machines are listed in `l1_2-compare.txt`. They are the 23 machines that now carry
`ACCEPTING_STATES:` and `PENDING_PROMISES:` (23 and 23 lines in `dump.txt`), the end-judgment lines of Slice 2.
Base had 0 of 23 changed, so the change is expected.

L1.3 expected: exit 0, "PASS: 71 machines, no positive reward cycle; the check detects the control loop".
L1.3 observed: exit 0, "PASS: 71 machines, no positive reward cycle; the check detects the control loop".
Witness `a & !b & !g` first-step reward 0.0. Negative control (+0.1 loop) detected as a positive cycle.

Evidence files:
- `$E/dump.txt`, `$E/l1_2-dump.out`, `$E/l1_2-compare.txt`, `$E/l1_3.txt`

Side effects: none outside `$E`. No processes started, nothing to clean up.
Gaps: none for L1.2 and L1.3.
Memory candidates: none
