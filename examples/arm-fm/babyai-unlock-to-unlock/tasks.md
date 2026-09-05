# Tasks

## Reconstruction target

`UTU-1` — Pick up the first key, open its matching door, pick up the second key, open
its matching door, and then pick up the target ball.

This is a concise restatement of the released mission and staged logic. Door colors
are randomized by the environment; “first” and “second” denote dependency order.

## Atomic pipeline probes

- `UTU-A`: Open the prerequisite door only after acquiring its key.
- `UTU-B`: Acquire the target-door key only after opening the prerequisite door.
- `UTU-C`: Open the target door only after acquiring its key.
- `UTU-D`: Pick up the target ball only after opening the target door.

## Evidence

- Released generator prompt:
  <https://github.com/roger-creus/llms-rm-rl/blob/main/prompts/make_rm/UnlockToUnlock/generator.txt>
- Paper Appendix A.2.1 and A.9: `docs/ARM-FM/ARM-FM.md`.
