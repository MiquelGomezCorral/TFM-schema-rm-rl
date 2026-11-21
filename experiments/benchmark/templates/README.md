# Templates suite

One card per DECLARE template, task and goal mode, to check two things: the generated machine
carries the expected template, and the agent trained on it does the task.

The eight templates: Existence, ExistenceTwo, Absence, Response, Precedence, ChainResponse,
RespondedExistence and NotCoExistence. Each template has three tasks with a goal and three without
one: 8 × 3 × 2 = 48 cards, plus three ServiceRoom goal cards with `k = 4`: `tpl-precedence-4-goal`,
the goal twin of `tpl-precedence-1-nogoal`, and `tpl-existence-two-4-goal` and
`tpl-responded-existence-4-goal`, the hard copies of their `-soft-1-goal` cards; plus
`tpl-existence-two-5-nogoal` on Lanes, the hard copy of `tpl-existence-two-soft-1-nogoal` (52 hard
cards), plus 28 soft cards (80 cards in all, see "Soft cards" below). Card ids read
`tpl-<template>-<k>-<goal|nogoal>`, with `k` from 1 to 3 (4 for those three, 5 for the Lanes one).

The cards with `k = 1` are trained, plus the three `k = 4` cards, `tpl-existence-two-5-nogoal` and
`tpl-responded-existence-2-nogoal`, minus the cards that stopped training (11 per arm of the hard
cards). `tpl-precedence-1-nogoal` and
`tpl-not-co-existence-1-nogoal` stopped training on 2026-11-18, since a wait plan passes them and the
goal cards of their templates test the rule; `tpl-chain-response-1-goal` and `-1-nogoal` stopped on
2026-11-19: a fall in the plain service room does not turn the agent, so the next-move rule is unfair
there, and the box-carry copies in `box-carry/` train instead. Six more stopped on 2026-11-20 (see
"Card fixes" below). The other cards are generated and checked but not trained. The 16 `k = 1` cards also carry three extra wordings of the
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
must reject everything the card rejects. Example: doors can be shut again, so
`Precedence(door_open, key_lost)` is not `also_ok` on an Absence or NotCoExistence card (it accepts
dropping the key after the door was opened and shut again). `Absence(key_lost)` and
`NotCoExistence(key_lost, door_open)` were `also_ok` on the Precedence key goal cards until
2026-11-20: next to the goal, which needs the door open, both read the stated "until" as "never".
Each alternative's flags (hard or soft) match the wording.

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

Chain reword (2026-11-19): the compiler's progress pay now reads the distance from the machine to its
final state, so a chain written as form B pays at every step. A needed step with no rule of its own
would pay nothing, so `tpl-precedence-1-goal`, `tpl-response-1-goal` and `cx-goal-many-rules` name
every step ("open the door with the key", "pick up the key, open the door with it") and
`expect` is the chain (`Existence(last)` plus the `Precedence` pairs) plus the card's own rule.
The orders the level forces (key before door before box or ball) are in `forced`. The older, shorter
answers stay in `also_ok`, except the full chain of `tpl-precedence-1-goal`, which is now `expect`.

Response goal card moved (2026-11-20): `tpl-response-1-goal` runs on UnlockPickup, not on
KeyCorridorS6R3. No method (no-RM, ARM-FM, FARM) learned KeyCorridorS6R3 in 71 runs, so a trained card
there tested nothing; UnlockPickup is the closest learned level (same key, locked door, box in another
room; ARM-FM 3 of 3 and FARM 1 of 3 on `base-unlock-pickup`). The trigger is `has_door_key` (the door
open when the key was last held or later, as in `tpl-response-2-goal` and `-3-goal`), and the box
replaces the ball. `tpl-response-3-nogoal` stays on KeyCorridorS6R3 as a generation and plan-check card.
The FARM bundles (the card and its three paraphrases) and the traces were made again for UnlockPickup on
2026-11-20; the old KeyCorridorS6R3 FARM bundles are kept in `kc-page-s6r3/farm/`.

RespondedExistence goal card fixed (2026-11-20): on BlockedUnlockPickup the box comes after the ball move
and after the key (the door opens only from the ball's cell and with the key; the box room has no other
entrance), so `tpl-responded-existence-2-goal` lists both orders in `forced`, and its old `also_ok` answer
with the key order is now `exact`. `Precedence(has_door_key, target_picked_up)` plus
`Existence(target_picked_up)`, without the `RespondedExistence`, is `also_ok`: the order and the goal force
the key, so it accepts the same traces (checked on the compiled DFAs, every reachable product state of the
two sets agrees). Strong models gave this answer in the model comparison and the scorer marked it wrong.
Both answers left `also_ok` on 2026-11-20 (see "Card fixes"): they drop the stated "if" rule.

Order audit (2026-11-20): an order the task states is required even when the level forces it. This
replaces the "Two forms" rule above for stated orders: `forced` keeps only orders the task does not
state, and an `also_ok` answer that drops a stated order is no longer correct.
- Lost `forced`: `tpl-existence-1-goal` ("then", "first", "after"), `tpl-response-1-goal` and
  `tpl-precedence-1-goal` ("open the door with it/the key", then the box).
- Lost `also_ok` answers: form A of `tpl-existence-1-goal`; `Existence(box)` alone on
  `tpl-existence-two-1/2-goal`; both answers of `tpl-response-1-goal` and `tpl-precedence-1-goal`;
  the `RespondedExistence` answer of `tpl-precedence-1-nogoal` and both answers of
  `tpl-precedence-4-goal`. Those last ones keep the order only because the run ends at the exit.
- Kept: `tpl-responded-existence-2-goal` keeps both box orders in `forced`. "Then" there follows an
  "if" rule, not a commanded step, so the task orders no event before the box; the same reading keeps
  the Response and RespondedExistence goal cards (`tpl-response-2/3-goal`,
  `tpl-responded-existence-1/3-goal`) without an order. An unordered list ("Open the door and pick up
  the box") still states no order.
- Answers that drop a stated rule other than an order (the `RespondedExistence` of the
  RespondedExistence goal cards, the door or room of `tpl-existence-2/3-goal`, the count of
  `tpl-existence-two-3-goal`) are unchanged and listed for review in the loop report. They left on
  2026-11-20 (see "Card fixes").

Card fixes (2026-11-20). An accepted answer that drops a clause the task states (an order, an "if"
rule, a template) is not correct, and an order the task does not state is never added from level
facts (user rules).
- `also_ok` answers removed: `Existence(last)` alone and the `Precedence` answer of
  `tpl-existence-2/3-goal` (they drop the door or room step, or add an unstated order); the
  key-before-box `Precedence` answer of `tpl-existence-two-1/2-goal`; all three answers of
  `tpl-existence-two-3-goal`; `Existence(box or ball)` alone on `tpl-responded-existence-1/2/3-goal` and
  the `Precedence` answer of `-2-goal`; `Absence(key_lost)` on `tpl-precedence-2-goal`, `-3-goal` and
  `-2-nogoal`, and `NotCoExistence(key_lost, door_open)` on the two goal cards (next to the goal both
  drop the "until").
- `tpl-existence-two-1/2-goal` say "and" in place of "then" in the task and paraphrases: `Precedence`
  cannot say the key was held twice before the box, so "then" stated a clause no answer could carry.
  `tpl-existence-two-3-goal` gains `Existence(door_open)` in `expect`: the task states the door step.
- Stopped training: `tpl-absence-1-nogoal`, `tpl-response-1-nogoal`, `tpl-responded-existence-1-nogoal`
  (an idle agent passes them; `lanes-guard`, `keygift-hard`, `tpl-response-1-nogoal-forced` and
  `tpl-responded-existence-2-nogoal` test those rules where the trigger comes); `tpl-existence-two-1-goal`
  (the goal forces the count); `tpl-responded-existence-1-goal` (KeyCorridorS6R3 was never learned, and
  the goal forces the rule); later the same day `tpl-existence-two-1-nogoal` (user): `has_key` is held,
  so one pickup kept for a second move pays the count, while `tpl-existence-two-5-nogoal` needs two kills.
- Started training: `tpl-responded-existence-2-nogoal` (the siren rings by itself, so an idle agent leaves
  the rule open on seeds 1 to 3), and two new hard cards on the service room, copies of the soft
  `-soft-1-goal` cards with the same plans and seeds: `tpl-existence-two-4-goal` ("Go to the exit, and be
  holding the box on at least two different moves.") and `tpl-responded-existence-4-goal` ("Go to the
  exit, and if the siren rings at any point, flip the switch at least once."). Then
  `tpl-existence-two-5-nogoal` ("Kill at least two zombies."), the hard copy of
  `tpl-existence-two-soft-1-nogoal` on Lanes: a held condition (`holding_box`, `has_key`) stays true on
  the next move, so its second count comes free once picked up, while two kills take two catches.
- Every training test runs seeds 1 to 3 (`runs.yaml`).

Stated-order rule (2026-11-20, user): only order words ("then", "after", "before") give an order;
"and" and commas do not. The "Then" of `tpl-responded-existence-2-goal` is an order word, so both box
orders are required and its `forced` is gone (this replaces the "Kept" reading of the order audit
above). No templates card uses `forced` any more.

Q4 ruling (2026-11-21, user): in `tpl-responded-existence-2-goal` the box is required and the key comes
before it; the ball is optional; if the ball moves, the key must be taken too, and both the key and
the box come after the ball move; no Precedence from the ball. The card's clauses are
Existence(target_picked_up), Precedence(has_door_key, target_picked_up),
RespondedExistence(blocker_moved, has_door_key) and Response(blocker_moved, target_picked_up), all
hard (Response(blocker_moved, has_door_key) would stay open on the solving plan, since the key is
dropped before the box). Known limit: these clauses also accept key, then ball, then box with no key
taken after the ball, which the level cannot produce; no answer from the 8 templates rejects that
trace and still accepts key then box with no ball. Its FARM bundle, generated again (production pair,
`--reasoning max`), lacks Response(blocker_moved, target_picked_up): `mismatch`. The old bundle, with
neither box order, is kept in `order-rule-r0/farm/`.

## Soft cards (2026-11-19)

28 cards word a rule as a wish ("try to ...", "preferably ...") and mark it soft in `expect`, so every
template has soft coverage next to its hard cards. Ids read `tpl-<template>-soft-<k>-<goal|nogoal>`,
`k` from 1 to 3 as for the hard cards; `k = 1` is trained (15 per arm, 26 with the hard ones) and
carries three extra wordings; the rest are generated and checked only.

- Goal cards (21): the soft rule plus a hard goal. The agent must act, and the soft rule is the
  tempting thing to break on the way (a shortcut, or an order that is faster the wrong way). Doing
  nothing fails the hard goal. Existence, ExistenceTwo, Precedence, ChainResponse, RespondedExistence
  and NotCoExistence have three each; Absence adds `tpl-absence-soft-1-goal` and Response adds `-1-` and
  `-2-` (`cx-goal-one-rule` and `cx-goal-many-rules` are the other two soft Absence goal cards, and
  `cx-goal-many-rules` the other soft Response one), so each has three.
- No-goal cards (7): soft only (rule D3: no pass or fail, soft breaks per episode), in a world that
  fires its own events: a siren, a forced box fall, or zombies in the Lanes level. An idle agent breaks
  the rule in every episode, so it does not look good. The seven are `tpl-existence-soft-1-nogoal`
  and `tpl-responded-existence-soft-1-nogoal` (siren room), `tpl-chain-response-soft-1-nogoal` (box
  falls), and `tpl-existence-two-soft-1-nogoal`, `tpl-absence-soft-1-nogoal`,
  `tpl-precedence-soft-1-nogoal` and `tpl-not-co-existence-soft-1-nogoal` (Lanes). Soft Absence and
  Response no-goal cards already existed (`lanes-rules`, `cx-rules-only`, `keygift-soft`; `cx-rules-only`
  is not trained since 2026-11-20). All seven
  are trained (idle shows as a soft break).
- Every card has a plan that keeps the rule and a plan that breaks it (`breaks` lists the clauses it
  breaks), and an idle plan breaks something on every card. The judge checks `breaks` on each card's
  `event_seeds` (1, 2, 3 for the ServiceRoom cards, 1, 3, 4 for the Lanes cards, the layout seed 1 for
  the key-level cards); a wider check on seeds 1 to 5 found one keep plan that is not seed-proof:
  the side-lane guard of `tpl-absence-soft-1-nogoal` loses one zombie on seed 2. The machine of the
  expected clauses pays keep > soft break > idle on those plans.
- No soft card carries `also_ok` (S2 rule: a stricter reading is only safe where the level forces the
  order, and none of these soft readings is). The ServiceRoom and Lanes soft cards use
  `env_reward_matches: false`, like the hard ones: the environment pays at the exit only when its own
  `require` holds, and Lanes never ends.
- A level that never forces the trigger stays out of the no-goal set (DoorKey, UnlockPickup,
  BlockedUnlockPickup, KeyCorridor: an idle agent passes a soft-only card there). Nothing makes the
  agent drop the key in UnlockPickup or DoorKey, so `tpl-not-co-existence-soft-2-goal` and `-3-` break
  the rule by a deliberate detour and test the soft reading of the template, not a shortcut.

## Contents

- `tasks.json`: the cards.
- `bundles/<arm>/<card-id>/`: the generated machine per arm (`farm` or `arm-fm`); a paraphrase is
  `<card-id>~p<k>`.
- `traces/<card-id>/`: trace records of the scripted plans.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.

Run folders, logs, checkpoints, Plotly HTML and GIFs stay under `outputs/`. See `../../README.md` for
what goes into Git.
