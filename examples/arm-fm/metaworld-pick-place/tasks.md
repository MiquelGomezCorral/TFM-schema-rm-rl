# Tasks

## Reported task

`MW-PICK-PLACE-1` — Pick up the puck and place it at the specified goal location.

## Atomic pipeline probes

- `MW-PICK-PLACE-A`: Eventually grasp the puck.
- `MW-PICK-PLACE-B`: Move the puck near the goal only after grasping it.
- `MW-PICK-PLACE-C`: Place the puck at the goal only after moving it near the goal.

Source: paper Appendix A.2.3, `docs/ARM-FM/ARM-FM.md`. The original generator prompt
is not published.
