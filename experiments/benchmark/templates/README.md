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

## Contents

- `tasks.json`: the cards.
- `bundles/<arm>/<card-id>/`: the generated machine per arm (`farm` or `arm-fm`); a paraphrase is
  `<card-id>~p<k>`.
- `traces/<card-id>/`: trace records of the scripted plans.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.

Run folders, logs, checkpoints, Plotly HTML and GIFs stay under `outputs/`. See `../../README.md` for
what goes into Git.
