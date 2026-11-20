# Complex suite

Harder tasks than the templates: longer, rules only, several hard and soft rules, and rules that react
to events in the small service room. Six cards; all but `cx-rules-only` are trained:

| Card | What it tests |
| --- | --- |
| `cx-sequence` | A long sequence of steps. |
| `cx-rules-only` | Rules and no goal (not trained since 2026-11-20: an idle agent passes it). |
| `cx-goal-one-rule` | A goal plus one rule. |
| `cx-goal-many-rules` | A goal plus several hard and soft rules. |
| `cx-siren` | "Whenever the siren rings, turn it off." |
| `cx-box` | "Carry the box to the exit, and whenever the box falls, pick it up again." |

Each card also carries three extra wordings of the task. The cards stay `draft` until the author
approves them.

Layouts: training resets draw new procedural layouts (`layout: procedural`). Evaluation keeps the fixed
seeds `eval_seed_base + i`, the same for every run and arm. `layout_seed: 1` stays on the card only for
the scripted plans, the trace records and the card checks; the trainer ignores it. The service-room
cards keep their fixed room and draw new event timings.

Key-drop rules: `key_lost` means dropping the key while the door is still closed. `cx-rules-only` and
`cx-goal-one-rule` run on BlockedUnlockPickup, like `cx-goal-many-rules`, where a key-first run must
drop the key to move the ball (D10 card revision). The soft `Absence(key_lost)` cards have no `also_ok`
for it: `Precedence(door_open, key_lost)` would be weaker (rule in `templates/README.md`).

Card fix 2: `cx-sequence`, `cx-goal-one-rule` and `cx-goal-many-rules` mark the orders the world
forces anyway in a `forced` list (indices into `expect`); those clauses are optional extras when
the stored clauses are compared with the card. The soft door rule of `cx-rules-only` and
`cx-goal-many-rules` is worded as the state it checks (the door open when the key was last held, or
later). `cx-box` asks to carry the box to the exit, checked at the exit step, so a direct exit
fails. `key_found` in `cx-sequence` needs a clear view of the key.

Chain reword (2026-11-19): `cx-goal-many-rules` now says "open the door with the key" and its
`expect` is the chain (`Precedence(has_door_key, door_open)`, `Precedence(door_open, box)`,
`Existence(box)`) plus its ball-first rule and two soft rules; both chain orders are in `forced`
(see `templates/README.md`).

2026-11-20: `cx-goal-many-rules` lost one `also_ok` answer, the one with `Precedence(door_open, box)`,
`Existence(blocker_moved)` and `Existence(box)` but no `Existence(has_door_key)`. It has no key step, so
the soft `Response(has_door_key, door_open)` charges the key pickup -1 with nothing to offset it, and
about one seed in three never learns it. The same day it also lost the answer with `Existence(blocker_moved)` and
`Existence(box)` but no `Existence(has_door_key)` and no door step: the same trap (solve pay 1, -1, 1, 11), never
trained. Four answers remain; the later ones are renumbered.

Order audit (2026-11-20): an order the task states is required even when the world forces it, so
`forced` now keeps only orders the task does not state, and an `also_ok` answer that drops a stated
order is no longer correct. All three cards state their orders ("and then", "then", "after", "open
the door with the key", "Then ... and pick up the box") and lost `forced`. `cx-sequence` lost its
one-Existence-per-step answer, `cx-goal-one-rule` its answer with two Existences and no order, and
`cx-goal-many-rules` its four remaining answers (none has `Precedence(has_door_key, door_open)`).
`cx-sequence`'s p3 lists the steps with no order word; it is scored against the same card. On
2026-11-20 p3 gained the task's closing "and then", and p1's second sentence did too, so every
wording states the four orders it is scored for.

Card fixes (2026-11-20): `cx-rules-only` stopped training (`train: false`) and left
`closed-set.json`: an idle agent passes it, and `lanes-rules` (forcing suite) covers rules with no
goal, as it already does in the ablation suite. It stays a generation card. `cx-goal-one-rule` lost
its `Response` answer: `Response` is not a step form, so it does not carry the stated order; its
answer with the `Precedence` and both Existences stays. Training runs seeds 1 to 3.

## Contents

- `tasks.json`: the cards.
- `ablation.json`: three cards of different sizes (two of these and the forcing suite's
  `lanes-rules`), used to switch off one reward part at a time. It holds notes, not card content: `../ablation/runs.yaml` takes its ids through `only` and
  reads the cards from `tasks.json`.
- `bundles/<arm>/<card-id>/`: the generated machine per arm (`farm` or `arm-fm`).
- `traces/<card-id>/`: trace records of the scripted plans.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.

Run folders, logs, checkpoints, Plotly HTML and GIFs stay under `outputs/`. See `../../README.md` for
what goes into Git.
