# Base suite

The base paper's own tasks, so our results can be read next to the paper's. Each task is run with the
three arms (no RM, ARM-FM, FARM). Four MiniGrid cards, one per environment:

| Card | Environment |
| --- | --- |
| `base-doorkey` | DoorKey 8x8 |
| `base-unlock-pickup` | UnlockPickup |
| `base-blocked-unlock-pickup` | BlockedUnlockPickup |
| `base-key-corridor` | KeyCorridor S6R3 |

All four are trained. The cards stay `draft` until the author approves them.

Forced orders (card fix 2): each card lists in `forced` the clauses of `expect` that the world
guarantees anyway (the key before the door, the door before the object, the ball before the door).
Scoring treats them as optional extras: the stored clauses may keep or drop them, and the goal
clause alone is a correct output. `base-blocked-unlock-pickup` now says the ball and the key may
come in either order.

Layouts: training resets draw new procedural layouts (`layout: procedural`). Evaluation keeps the fixed
seeds `eval_seed_base + i`, the same for every run and arm. `layout_seed: 1` stays on the card only for
the scripted plans, the trace records and the card checks; the trainer ignores it.

## Contents

- `tasks.json`: the cards (task wording, expected clauses, solving and wrong plans).
- `bundles/<arm>/<card-id>/`: the generated machine per arm (`farm` or `arm-fm`).
- `traces/<card-id>/`: trace records of the scripted plans.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.

Run folders, logs, checkpoints, Plotly HTML and GIFs stay under `outputs/`. See `../../README.md` for
what goes into Git.
