# Templates suite

One card per DECLARE template, task and goal mode, to check two things: the generated machine
carries the expected template, and the agent trained on it does the task.

The eight templates: Existence, ExistenceTwo, Absence, Response, Precedence, ChainResponse,
RespondedExistence and NotCoExistence. Each template has three tasks with a goal and three without
one: 8 × 3 × 2 = 48 cards, plus `tpl-precedence-4-goal`, the goal twin of `tpl-precedence-1-nogoal` (49 cards).
Card ids read `tpl-<template>-<k>-<goal|nogoal>`, with `k` from 1 to 3 (4 for that twin).

Only the cards with `k = 1` are trained, plus `tpl-precedence-4-goal` (13 per arm: `tpl-precedence-1-nogoal` and
`tpl-not-co-existence-1-nogoal` stopped training on 2026-11-18, since a wait plan passes them and the
goal cards of their templates test the rule; `tpl-chain-response-1-goal` and `-1-nogoal` stopped on
2026-11-19: a fall in the plain service room does not turn the agent, so the next-move rule is unfair
there, and the box-carry copies in `box-carry/` train instead). The other two per template and goal mode are
generated and checked but not trained. The 16 `k = 1` cards also carry three extra wordings of the
task, to see whether different phrasings give the same machine. The cards stay `draft` until the
author approves them.

Layouts: training resets draw new procedural layouts (`layout: procedural`). Evaluation keeps the fixed
seeds `eval_seed_base + i`, the same for every run and arm. `layout_seed: 1` stays on the card only for
the scripted plans, the trace records and the card checks; the trainer ignores it. The service-room
cards keep their fixed room and draw new event timings.

Key-drop rules: `key_lost` means dropping the key while the door is still closed. The k=1 Absence and
NotCoExistence key cards run on BlockedUnlockPickup, where a key-first run must drop the key to move the
ball; the k=3 cards moved to UnlockPickup and DoorKey (D10 card revision).

`also_ok` rule (S2, 2026-11-19; the complex, base and box-carry cards follow it too): an alternative
clause set may be stronger than the card only on behaviour the task never needs, and never weaker. It
must reject everything the card rejects. Example: doors can be shut again, so `Absence(key_lost)` and
`NotCoExistence(key_lost, door_open)` are `also_ok` on the Precedence key cards (they forbid only
dropping the key after the door was opened and shut again), but `Precedence(door_open, key_lost)` is not
`also_ok` on an Absence or NotCoExistence card (it accepts that run). Each alternative's flags
(hard or soft) match the wording.

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

Two forms of an ordered task (2026-11-19, prompt loop n6; the complex cards follow it too): "A, then B"
has form A (one `Existence` per event, no order) and form B (`Existence` of the last event plus a
`Precedence` chain). A card lists the other form in `also_ok` only where the level forces the order, so
the two accept the same runs: `door_open` before the box, key before door before goal or ball, and
`at_exit` ending the episode so a toggle always comes before it. Steps the level forces
(`door_open`, `blocker_moved`, `has_door_key`) may also carry their own `Existence`
(`cx-goal-one-rule`, `cx-goal-many-rules`). Not valid, so not listed:
- ServiceRoom carry cards (`tpl-chain-response-N-goal`, `cx-box`): both forms accept a box dropped
  before the exit, which "carry the box to the exit" forbids; only `Response(at_exit, holding_box)` says it.
- An order the level does not force (ball before key, `tpl-precedence-1-goal`, `cx-goal-many-rules`)
  keeps its `Precedence`; per-event `Existence` alone lets the key go first.
Cards with also_ok from this rule: `tpl-existence-1/2/3-goal`, `tpl-existence-two-1/2/3-goal`,
`tpl-response-1/2/3-goal`, `tpl-precedence-1-goal`, `tpl-precedence-4-goal`,
`tpl-responded-existence-1/2/3-goal`, `cx-sequence`, `cx-goal-one-rule`, `cx-goal-many-rules`.
The Absence, NotCoExistence and `tpl-precedence-2/3` goal cards have one step and no second form.

## Contents

- `tasks.json`: the cards.
- `bundles/<arm>/<card-id>/`: the generated machine per arm (`farm` or `arm-fm`); a paraphrase is
  `<card-id>~p<k>`.
- `traces/<card-id>/`: trace records of the scripted plans.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.

Run folders, logs, checkpoints, Plotly HTML and GIFs stay under `outputs/`. See `../../README.md` for
what goes into Git.
