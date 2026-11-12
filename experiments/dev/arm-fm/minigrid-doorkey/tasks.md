# Tasks

## Reconstruction target

`DK-1` — Use the key to open the door, then reach the goal.

This is the mission in the released ARM-FM generator trace. The same logical task is
used for all reported DoorKey sizes.

## Atomic pipeline probes

- `DK-A`: Eventually acquire the key.
- `DK-B`: Open the door only after acquiring the key.
- `DK-C`: Reach the goal only after opening the door.

The probes test individual stages. They do not, by themselves, reproduce the single
multi-stage RM associated with `DK-1`.

## Evidence

- Released generator trace:
  <https://github.com/roger-creus/llms-rm-rl/blob/main/reward_machines/DoorKey/GENCRIT-TRACE-MiniGrid-DoorKey.txt>
- Paper Appendix A.2.1 and A.9: `docs/ARM-FM/ARM-FM.md`.
