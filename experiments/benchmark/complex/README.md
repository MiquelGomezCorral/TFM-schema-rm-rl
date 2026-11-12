# Complex suite

Harder tasks than the templates: longer, rules only, several hard and soft rules, and rules that react
to events in the small service room. Six cards, all trained:

| Card | What it tests |
| --- | --- |
| `cx-sequence` | A long sequence of steps. |
| `cx-rules-only` | Rules and no goal. |
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
drop the key to move the ball (D10 card revision).

Card fix 2: `cx-sequence`, `cx-goal-one-rule` and `cx-goal-many-rules` mark the orders the world
forces anyway in a `forced` list (indices into `expect`); those clauses are optional extras when
the stored clauses are compared with the card. The soft door rule of `cx-rules-only` and
`cx-goal-many-rules` is worded as the state it checks (the door open when the key was last held, or
later). `cx-box` asks to carry the box to the exit, checked at the exit step, so a direct exit
fails. `key_found` in `cx-sequence` needs a clear view of the key.

## Contents

- `tasks.json`: the cards.
- `ablation.json`: three of these cards, of different sizes, used to switch off one reward part at a
  time. It holds notes, not card content: `../ablation/runs.yaml` takes its ids through `only` and
  reads the cards from `tasks.json`.
- `bundles/<arm>/<card-id>/`: the generated machine per arm (`farm` or `arm-fm`).
- `traces/<card-id>/`: trace records of the scripted plans.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.

Run folders, logs, checkpoints, Plotly HTML and GIFs stay under `outputs/`. See `../../README.md` for
what goes into Git.
