# Tasks

## Reported task

`MW-SHELF-1` — Pick up the puck and place it on the shelf.

## Atomic pipeline probes

- `MW-SHELF-A`: Eventually grasp the puck.
- `MW-SHELF-B`: Move the puck near the shelf target only after grasping it.
- `MW-SHELF-C`: Place the puck on the shelf only after moving it near the target.

Source: paper Appendix A.2.3, `docs/ARM-FM/ARM-FM.md`. The original generator prompt
is not published.
