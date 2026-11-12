# Base suite

The base paper's own tasks, so our results can be read next to the paper's. Each task is run with the
three arms (no RM, ARM-FM, FARM). Four MiniGrid cards, one per environment:

| Card | Environment |
| --- | --- |
| `base-doorkey` | DoorKey 8x8, fixed layout |
| `base-unlock-pickup` | UnlockPickup |
| `base-blocked-unlock-pickup` | BlockedUnlockPickup |
| `base-key-corridor` | KeyCorridor S6R3 |

All four are trained. The cards stay `draft` until the author approves them.

## Contents

- `tasks.json`: the cards (task wording, expected clauses, solving and wrong plans).
- `bundles/<arm>/<card-id>/`: the generated machine per arm (`farm` or `arm-fm`).
- `traces/<card-id>/`: trace records of the scripted plans.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.

Run folders, logs, checkpoints, Plotly HTML and GIFs stay under `outputs/`. See `../../README.md` for
what goes into Git.
