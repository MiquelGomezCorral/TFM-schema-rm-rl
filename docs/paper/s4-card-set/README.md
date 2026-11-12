# The task-card set and its judged plans

Date: 2026-11-12, from the S4 slice of the testing program (trace-bank run on the merged head
`3c36563`, templates rerun after the fix in `0053158`). The cards are **under revision (D10)**: the
user asked on 2026-11-12 for every card's environment and rule to be checked before approval. The
numbers below describe the set as it was on that morning.

## What it shows

Every benchmark task is a card, fixed before any machine is generated: the wording both pipelines
receive, the clauses it should compile to (with their LTLf formulas), and a few plans (a solving one
and wrong ones, each saying which clauses it breaks). The trace bank plays every plan in its
environment and the independent judge checks the clauses on the reference labels. A card is sound
when each solving plan is judged a success and each wrong plan breaks exactly the clauses it says.

- **58 cards, 179 judged plan runs, no card with a problem.** Base 4 cards (8 runs), templates 48
  cards (145 runs: 8 DECLARE templates x 3 tasks x with and without a goal), complex 6 cards (26 runs).
- The live round found one bad plan: the "pick up then drop" plan of `tpl-existence-two-1-nogoal`
  held the key on two steps in DoorKey, because the trace bank turns before a drop, so one-step
  holding cannot be authored there. The plan was removed (145/146 became 145/145).
- **Response and Precedence are not trace-equivalent.** The base DoorKey card lists a Response pair
  as an accepted alternative for its Precedence pair. They differ: see below.
- **Response on a state that can turn false has a limit.** `tpl-response-*` cards carry the note.

## Response against Precedence

Card `base-doorkey`. Natural-language task: "Use the key to open the door, then reach the goal."
Expected LTL: `Precedence(has_key, door_open)` = `((~door_open) U has_key) | (G ~door_open)`,
`Precedence(door_open, at_goal)` and `Existence(at_goal)`, all hard. The card's `also_ok` replaces the
Precedence clauses with `Response(has_key, door_open)` = `G (has_key -> (F door_open))` and
`Response(door_open, at_goal)`. Reward Machine: none, a card is an input. The machines both pipelines
generated for the same wording are in the S6 entry (`smoke-doorkey-base`).

`has_key` stays true while the agent holds the key, so Response asks for a door opening after every
step of holding. Two traces, judged by the benchmark's own judge (`check/response_vs_precedence.py`):

| Trace | Precedence | Response |
| --- | --- | --- |
| picks up the key, never opens the door | holds | open at the end |
| opens the door, then it shuts again, key still held | holds | open at the end |

Over every trace of up to 4 steps on `has_key` and `door_open` (340, including ones DoorKey cannot
produce), 156 are judged differently. So a machine built from the Response pair is not the same task
as the card. It is a card issue (the base cards are sample-owned, reported upward), not a pipeline
failure.

## The set, by suite

| Suite | Cards | Plan runs | Notes |
| --- | --- | --- | --- |
| base | 4 | 8 | the four MiniGrid tasks of the base paper; equal to the sample file |
| templates | 48 | 145 | 3 tasks per template, with and without a goal; 16 are marked for training |
| complex | 6 | 26 | rules only, tasks only, longer, mixed; 2 of the 6 use the event room (10 template cards do too) |

`results/trace-bank-<suite>.log` is the readable record: each card's task, its clauses with LTLf, and
each plan's verdicts (`holds`, `broken@step`, `open_at_end`). `results/trace-bank-<suite>-summary.json`
is the same with steps, environment success and judged success per run. Example from the complex log:

```text
cx-rules-only: Stay off the goal. Try not to lose the key before the door is open, and if you pick up
the key, try to open the door afterwards.
  ['Absence', ['at_goal'], 'hard']  (~(F at_goal))
  ['Absence', ['key_lost'], 'soft']  (~(F key_lost))
  ['Response', ['has_key', 'door_open'], 'soft']  (G (has_key -> (F door_open)))
  solve-s1: ok  holds holds holds
  wrong-0-s1: ok  broken@19 holds holds
```

## What this does not show

- The cards were drafted by an agent and are not yet approved by the user (D10).
- A plan run tests the card and the judge, not a learner or a pipeline.
- Known gaps from the slice: the service-room finish clause cannot get its own wrong plan under the plan
  grammar; the older known-limit sentences on three Response cards over-generalise; the base card
  `base-blocked-unlock-pickup` lacks the ball-before-key order.

## Files

- `results/`: the three logs and three summary files copied from the run (outputs are git-ignored in
  the repository).
- `check/response_vs_precedence.py`: the Response against Precedence check.

## Rerun

The trace bank, from the repository root, inside `RM_RL_env` (no LLM call; the cards are
`experiments/benchmark/<suite>/tasks.json`):

```bash
PYTHONPATH=app python app/main.py trace-bank --tasks experiments/benchmark/templates/tasks.json --output <output dir>
```

The Response against Precedence check:

```bash
PYTHONPATH=app python -W ignore docs/paper/s4-card-set/check/response_vs_precedence.py
```

It prints the two named traces and `156 of 340 traces up to 4 steps are judged differently`.

## Code

`app/src/benchmark/declare_judge.py` (the judge), the `trace-bank` command, the cards under
`experiments/benchmark/`. The slice merged into the wave as commit `47403ef` (`merge: tp-s4-cards`).
