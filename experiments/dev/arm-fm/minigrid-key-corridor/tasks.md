# Tasks

## Reconstruction target

`KC-1` — Explore the side rooms, find and acquire the key matching the locked target
room, return to the corridor, open the target door, and pick up the designated object.

This task is reconstructed from Appendix A.2.1 and the official environment. The
released RM trace incorrectly reuses the DoorKey mission, so it is not evidence of the
original KeyCorridor prompt.

## Atomic pipeline probes

- `KC-A`: Eventually find the matching key.
- `KC-B`: Open the target door only after acquiring the matching key.
- `KC-C`: Pick up the target object only after opening the target door.

## Evidence

- Paper Appendix A.2.1 and A.9: `docs/ARM-FM/ARM-FM.md`.
- Released artifacts:
  <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/KeyCorridorS6R3>.
