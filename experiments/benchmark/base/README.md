# Base suite

The base paper's own tasks, so our results can be read next to the paper's. Each task is run with the
three arms (no RM, ARM-FM, FARM). Four MiniGrid cards, one per environment:

| Card | Environment |
| --- | --- |
| `base-doorkey` | DoorKey 8x8 |
| `base-unlock-pickup` | UnlockPickup |
| `base-blocked-unlock-pickup` | BlockedUnlockPickup |
| `base-key-corridor` | KeyCorridor S4R3 |

All four are trained. The cards stay `draft` until the author approves them.

Forced orders (card fix 2): each card lists in `forced` the clauses of `expect` that the world
guarantees anyway (the key before the door, the door before the object, the ball before the door).
Scoring treats them as optional extras: the stored clauses may keep or drop them, and the goal
clause alone is a correct output. `base-blocked-unlock-pickup` now says the ball and the key may
come in either order.

Order audit (2026-11-20): an order the task states is required even when the world forces it, so
`forced` now keeps only orders the task does not state. `base-doorkey` ("use the key to open the
door, then reach the goal") and `base-blocked-unlock-pickup` ("..., unlock the door, and then pick
up the box") state every order and lost `forced`; the goal clause alone is no longer correct there.
`base-unlock-pickup` and `base-key-corridor` list their steps with no order word, so their orders
stay in `forced`. The audit kept the Response chain of `base-doorkey` in `also_ok`, reading it as
stating both orders.

Card fixes (2026-11-20): the Response chain of `base-doorkey` left `also_ok` later the same day
(and on its pilot and smoke copies): `Response` is not a step form, so it does not carry the stated
orders (user rule).
The pilot and smoke copies of `base-unlock-pickup` mark both orders `forced`, as here, so they score
like this card. `base-key-corridor` is unchanged: its task lists the steps with no order word, so it
states no order. "Find and acquire the key" is the key step, which `expect` names
(`has_matching_key`); `key_found` adds nothing, since the key is never held before it is seen, and
"explore the side rooms" and "return to the corridor" have no label. Training runs seeds 1 to 3.

Stated-order rule (2026-11-20, user): only order words ("then", "after", "before") give an order;
"and" and commas do not. `base-unlock-pickup` (and its pilot and smoke copies) and
`base-key-corridor` list facts, so `expect` is one `Existence` per fact, the ordered chain is the
`also_ok` answer, and no card here uses `forced` any more. The Response chain left
`base-unlock-pickup`'s `also_ok`, as it did `base-doorkey`'s. One compound states an order: "find and
acquire the key", since taking the key needs finding it first, so `base-key-corridor` requires
`Precedence(key_found, has_matching_key)` in both answers. Its S4R3 FARM bundle gives that answer and
counts: FARM learned 2 of 3 seeds (judged success 0.85, 0.82, 0.00), no-RM none.

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
