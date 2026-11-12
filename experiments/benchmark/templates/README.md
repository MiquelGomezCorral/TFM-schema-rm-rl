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

## Contents

- `tasks.json`: the cards.
- `bundles/<arm>/<card-id>/`: the generated machine per arm (`farm` or `arm-fm`); a paraphrase is
  `<card-id>~p<k>`.
- `traces/<card-id>/`: trace records of the scripted plans.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.

Run folders, logs, checkpoints, Plotly HTML and GIFs stay under `outputs/`. See `../../README.md` for
what goes into Git.
