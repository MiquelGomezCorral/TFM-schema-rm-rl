# Samples

One line per file. Testers never edit them.

- `l1_4-task.txt`: the L1.4 and L2.3 task text, "Whenever you drop the key, pick it up again".
- `doorkey-labeling.py`: the DoorKey labeling (`has_key`, `door_open`, `at_goal`, `key_lost`), a copy of `outputs/bundles/dk-precedence/labeling.py`; L2.2 runs it on scripted episodes.
- `reject-accepting-and-pending.rm`: L2.1, state `u1` is in `ACCEPTING_STATES` and in `PENDING_PROMISES`; the parser must reject it, naming the defect.
- `reject-neither-list.rm`: L2.1, a non-final non-rejecting state (`u2`) is in neither list; must be rejected.
- `reject-pending-unknown-state.rm`: L2.1, a `PENDING_PROMISES` row for `u7`, which the machine does not have; must be rejected.
- `reject-pending-before-reward-function.rm`: L2.1, `PENDING_PROMISES` placed before `REWARD_FUNCTION`; must be rejected.
- `reject-accepting-without-pending.rm`: L2.1, a one-state machine with `ACCEPTING_STATES: u0` and no `PENDING_PROMISES` section; the parser must reject it, naming `PENDING_PROMISES`.
- `accept-author-bundle.rm`: L2.1, the `paper-authors-DoorKey` text (no final, none of the new lines); must parse and round-trip with no new lines added.
- `accept-lists-without-values.rm`: L2.1, both lists but no `HARD_FAILED_REWARD` / `SOFT_FAILED_REWARD` lines; must parse (defaults -1 and -0.5) and round-trip.
- `accept-hard-failed-reward--2.rm`: L2.1 and L2.2 case 6, the compiled `hard Response(has_key, door_open)` text with `HARD_FAILED_REWARD: -2`; L2.2 checks it equals the oracle's text.
- `l2_3-smoke.yaml`: L2.3, the smoke training config (DoorKey 5x5, DQN, symbolic view, `success: rm`, 3000 steps); replace `BUNDLE_DIR` with the generated bundle folder.
