# Tasks

## Reported task

`CRAFT-1` — Mine a diamond by gathering wood, stone, iron, and diamond in that order.

This is the task sequence stated in Sections 3.2 and A.2.2. The original generator
prompt is not published.

## Atomic pipeline probes

- `CRAFT-A`: Eventually acquire wood.
- `CRAFT-B`: Acquire stone only after acquiring wood.
- `CRAFT-C`: Acquire iron only after acquiring stone.
- `CRAFT-D`: Acquire a diamond only after acquiring iron.

## Evidence

- Paper Sections 3.2, A.2.2, and A.9: `docs/ARM-FM/ARM-FM.md`.
