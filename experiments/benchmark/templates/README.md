# Templates suite

One card per DECLARE template, task and goal mode, to check two things: the generated machine
carries the expected template, and the agent trained on it does the task.

The eight templates: Existence, ExistenceTwo, Absence, Response, Precedence, ChainResponse,
RespondedExistence and NotCoExistence. Each template has three tasks with a goal and three without
one: 8 × 3 × 2 = 48 cards. Card ids read `tpl-<template>-<k>-<goal|nogoal>`, with `k` from 1 to 3.

Only the cards with `k = 1` are trained (16 per arm). The other two per template and goal mode are
generated and checked but not trained. The 16 trained cards also carry three extra wordings of the
task, to see whether different phrasings give the same machine. The cards stay `draft` until the
author approves them.

Layouts: training resets draw new procedural layouts (`layout: procedural`). Evaluation keeps the fixed
seeds `eval_seed_base + i`, the same for every run and arm. `layout_seed: 1` stays on the card only for
the scripted plans, the trace records and the card checks; the trainer ignores it. The service-room
cards keep their fixed room and draw new event timings.

Key-drop rules: `key_lost` means dropping the key while the door is still closed. The k=1 Absence and
NotCoExistence key cards run on BlockedUnlockPickup, where a key-first run must drop the key to move the
ball; the k=3 cards moved to UnlockPickup and DoorKey (D10 card revision).

Card fix 2:

- The six Response cards word the obligation as the state their trigger is, and only as far as
  `Response(a, b)` checks it (a `b` at or after the last `a`): the door open when the key was last
  held or later, the door open on the final step once `key_found`, the key held at the last moment
  the ball was out of the way (`blocker_moved` is reversible) or later. None says "keep" or "leave".
- The six ChainResponse cards ask to carry the box to the exit (the goal cards require reaching
  it, the no-goal cards only when the exit is reached) and add `Response(at_exit, holding_box)`,
  so a direct exit fails; the solving policy waits in place with the box until its falls are done.
- The do-it-once negatives of the counting cards end at the first pickup; the trained counting card
  also has one.
- `key_found` needs a clear view of the key (KeyCorridor cards).
- `tpl-absence-3-nogoal`, `tpl-precedence-1-nogoal`, `tpl-precedence-3-nogoal` and
  `tpl-responded-existence-2-nogoal` have one reading in every wording.

## Contents

- `tasks.json`: the cards.
- `bundles/<arm>/<card-id>/`: the generated machine per arm (`farm` or `arm-fm`); a paraphrase is
  `<card-id>~p<k>`.
- `traces/<card-id>/`: trace records of the scripted plans.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.

Run folders, logs, checkpoints, Plotly HTML and GIFs stay under `outputs/`. See `../../README.md` for
what goes into Git.
