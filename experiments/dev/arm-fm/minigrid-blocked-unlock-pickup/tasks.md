# Tasks

## Reconstruction target

`BUP-1` — Pick up the blocking ball, pick up the key, unlock the door, and then pick
up the box in the other room.

This restates the mission and staged logic in the released generator trace.

## Atomic pipeline probes

- `BUP-A`: Move the blocking ball before acquiring the door key.
- `BUP-B`: Unlock the door only after acquiring the door key.
- `BUP-C`: Pick up the target box only after opening the door.

These probes isolate the stages; they are not equivalent to the single RM for `BUP-1`.

## Evidence

- Released generator trace:
  <https://github.com/roger-creus/llms-rm-rl/blob/main/reward_machines/BlockedUnlockPickup/GENCRIT-TRACE.txt>
- Paper Appendix A.2.1 and A.9: `docs/ARM-FM/ARM-FM.md`.
