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
| `cx-box` | "Whenever the box falls, pick it up again." |

Each card also carries three extra wordings of the task. The cards stay `draft` until the author
approves them.

Layouts: training resets draw new procedural layouts (`layout: procedural`). Evaluation keeps the fixed
seeds `eval_seed_base + i`, the same for every run and arm. `layout_seed: 1` stays on the card only for
the scripted plans, the trace records and the card checks; the trainer ignores it. The service-room
cards keep their fixed room and draw new event timings.

Key-drop rules: `key_lost` means dropping the key while the door is still closed. `cx-rules-only` and
`cx-goal-one-rule` run on BlockedUnlockPickup, like `cx-goal-many-rules`, where a key-first run must
drop the key to move the ball (D10 card revision).

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
