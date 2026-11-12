# Which reward part pays for what: sequences against switches

Date: 2026-11-12, from the S8 slice of the testing program (final slice head `35b7944`, the six
ablated copies and the sequence table rerun on it). One machine, one task, six hand-written label
sequences: a check that each switch removes its own part and nothing else, not a result about
learning.

## What it shows

A FARM machine pays through five reward parts: progress, the well charge, the soft-break penalty, the
soft-pending charge and the end judgment (plus the recurrent soft penalty, a sixth switch). The S8
command `ablate-rm` rebuilds the same bundle with one part off, from the stored clauses, with no model
call (except recurrent-off, which rewrites the 10 state descriptions with one call). The table plays
six label sequences on the full machine (`none`) and on each ablated copy and shows the per-step
rewards. Every change sits in the column of the switch that owns it:

- progress off: the small step payments become 0 (`0, 0.2, 1.1` becomes `0, 0, 1`); completion still
  pays 1.
- well off: the well edge costs 3 instead of 4 (the 1 for entering the well is gone).
- end judgment off: the well edge costs 1 and an open task at the time limit costs 0.5 (the flat
  time-limit penalty), instead of 4 and 2.5.
- soft_break off: a soft violation costs nothing (`-0.5` becomes `0`).
- recurrent soft penalty off: the second break of a soft clause is free; the first still costs 0.5.
- soft_pending off: no change in these sequences, because a real DoorKey episode cannot leave the door
  shut; its RM text differs on the finishing edges (see the note below the table).

## The task

- **Natural-language task:** "Pick up the key, open the door, then reach the goal. Never reach the goal
  before the door is open. Try not to lose the key, and whenever you pick up the key, try to open the
  door afterwards." Environment: MiniGrid DoorKey (`examples/arm-fm/minigrid-doorkey/environment.md`).
- **LTL:** the eight clauses the compiler recorded (`manifest.json`, `generation["clauses"]`). The
  Precedence of `door_open` before `at_goal` appears twice in the record; the machine is the same.

  | Clause | Kind | Formula |
  | --- | --- | --- |
  | Existence(has_key) | hard | `F has_key` |
  | Precedence(has_key, door_open) | hard | `(~door_open U has_key) \| G ~door_open` |
  | Existence(door_open) | hard | `F door_open` |
  | Precedence(door_open, at_goal) (twice) | hard | `(~at_goal U door_open) \| G ~at_goal` |
  | Existence(at_goal) | hard | `F at_goal` |
  | Absence(key_lost) | soft | `~(F key_lost)` |
  | Response(has_key, door_open) | soft | `G (has_key -> (F door_open))` |

- **Reward Machine (full, `none`):** [graph](graphs/none.html), [text](graphs/none.rm.txt). Ten states,
  final `u7`, rejecting `u4` (the well). The model pair was `deepseek-v4.1-flash` (generator) and
  `glm-5.3-flash` (critic) on the real generation.

## Sequences against switches

Per-step rewards, the episode total in brackets, `*` = different from `none`. "Open at time limit" is a
run cut by the step limit with the task unfinished; the other five end on their own.

| Sequence | none | progress | well | soft_break | soft_pending | end_judgment | recurrent_soft_penalty |
| --- | --- | --- | --- | --- | --- | --- | --- |
| solve | 0, 0.2, 1.1 [1.3] | 0, 0, 1 [1] * | same | same | same | same | same |
| well first | -4 | -4 | -3 * | -4 | -4 | -1 * | -4 |
| soft break, then solve | 0, -0.5, 0, 0.2, 1.1 [0.8] | 0, -0.5, 0, 0, 1 [0.5] * | same | 0, 0, 0, 0.2, 1.1 [1.3] * | same | same | same |
| open at time limit | 0, -2.5 | 0, -2.5 | same | same | same | 0, -0.5 [-0.5] * | same |
| finish with the soft answer owed | -4, 0, 0 [-4] | same | -3 * | same | same | -1 * | same |
| break twice | 0, -0.5, 0, -0.5 [-1] | same | same | 0, 0, 0, 0 [0] * | same | same | 0, -0.5, 0, 0 [-0.5] * |

`evidence/live2-check.txt` is the printed table, with every cell, and the bundle check above it: the
six ablated bundles are `complete`, `none` is a no-op, five differ from the source only in
`reward_machine.txt` (and the attempt records), recurrent-off also in `state_descriptions.json` and
`embeddings.json`. The rows "well first" and "finish with the soft answer owed" were made distinct in
review round 4, so that a swapped well and end judgment would show.

Note on `soft_pending`: the extra check in the slice report gives `none` `[0.2, 0.6]` against
`soft_pending` `[0.2, 1.1]` on a sequence that ends with the soft answer owed. That sequence is not a
row of the table above.

## The Reward Machines

Live HTML graphs (drag a state, click an edge), the RM text beside each:

| Variant | Graph | RM text |
| --- | --- | --- |
| `none` (full) | [graph](graphs/none.html) | [text](graphs/none.rm.txt) |
| progress off | [graph](graphs/progress.html) | [text](graphs/progress.rm.txt) |
| well off | [graph](graphs/well.html) | [text](graphs/well.rm.txt) |
| soft_break off | [graph](graphs/soft_break.html) | [text](graphs/soft_break.rm.txt) |
| soft_pending off | [graph](graphs/soft_pending.html) | [text](graphs/soft_pending.rm.txt) |
| end_judgment off | [graph](graphs/end_judgment.html) | [text](graphs/end_judgment.rm.txt) |
| recurrent soft penalty off | [graph](graphs/recurrent_soft_penalty.html) | [text](graphs/recurrent_soft_penalty.rm.txt) |

The end-judgment-off text shows the cost directly: the lines `ACCEPTING_STATES`, `HARD_FAILED_REWARD`
and `SOFT_FAILED_REWARD` are gone and every edge into the well `u4` pays -1 where the full machine
pays -4.

## What this does not show

- It does not show that a learner trained on an ablated machine does worse or better; that is a later
  training run.
- One task and one machine. The sequences are hand-written label traces stepped through the runtime,
  not episodes of the environment, except where the slice report says a real-wrapper check was made
  (the time-limit row).
- An ablated copy carries no critic verdict and its generation counts as a first-attempt win in
  `aggregate_judgments` (a gap of the slice, listed in its report).
- Recurrent-off made three real description calls in development and on the final head, not one.

## Files

- `graphs/`: the full machine and the six ablated copies, as live HTML, SVG and RM text.
- `evidence/live2-check.txt`: the bundle check and the sequence table as printed.
- `evidence/recurrent-off.log`: the recurrent-off run (warning that the source stores no clause
  sentences, 10 descriptions and embeddings regenerated).

## Rerun

The ablated copies need the source bundle, which is an output (git-ignored) of the S8 run, and the
recurrent-off copy needs the provider and a local embedding server. The command shape, from the
repository root inside `RM_RL_env`:

```bash
PYTHONPATH=app python app/main.py ablate-rm --bundle <FARM bundle> --off progress --output <output dir>
```

`--off` takes `none`, `progress`, `well`, `soft_break`, `soft_pending`, `end_judgment` or
`recurrent_soft_penalty`. The graphs of this entry were rendered from the RM texts with:

```bash
PYTHONPATH=app python app/main.py render-rm --rm-file docs/paper/s8-sequence-switch-table/graphs/none.rm.txt --svg-dir docs/paper/s8-sequence-switch-table/graphs/none.svg --html
```

## Code

`RewardSwitches` (`app/src/compiler/reward_layer.py`) and `app/scripts/ablate_rm.py`. The slice merged
into the wave as the S8 checkpoint `a690013`, the correction `c7140e9` and the final head `35b7944`.
