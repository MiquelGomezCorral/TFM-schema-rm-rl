# Tasks

## Reported task

`MW-BIN-1` — Pick up the puck from one bin and place it in the other bin.

## Atomic pipeline probes

- `MW-BIN-A`: Eventually grasp the puck.
- `MW-BIN-B`: Move the puck near the target bin only after grasping it.
- `MW-BIN-C`: Place the puck in the target bin only after moving it near that bin.

Source: paper Appendix A.2.3, `docs/ARM-FM/ARM-FM.md`. The original generator prompt
is not published.
