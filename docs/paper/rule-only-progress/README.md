# Rule-only progress, simulated (proposal P2)

Date: 2026-10-26. Open `index.html` in a browser; everything it needs is in this folder.

## What it shows

A task made only of rules has no goal, so its Reward Machine has no final state. Before this change the
progress reward measured the distance to a final state, so these tasks paid 0 for progress ("today" on
the page and below means that code, commit `e0a054a`). This entry simulates proposal P2 before the code
was changed: with no final state, progress is measured toward the states where no rule clause is still
waiting on something (each clause is kept or already broken). The code now does this; see "Code".

Each step closer pays +0.1 and each step away costs 0.1. P2 only applies when the task has no final state.

The page has a table of all 16 machines, one card per changed machine (the task in plain words, the LTLf,
and the Reward Machine today and with P2, each with an "RM text" fold-out), the traces walked on both
machines with their totals, and a section on what P2 leaves open. The simulation is a runtime patch of the
code at `e0a054a`; no tracked code file changed while it ran.

## The examples

The trigger costs 0.1 until the promise is kept, so the examples use events the environment causes and
the agent only recovers. When the agent controls the trigger, the 0.1 comes back when it keeps the
promise, so the total is the same (apart from discounting).

| Template | Example (hard) |
| --- | --- |
| Response `(box_fell, box_on_shelf)` | "Whenever the box falls off the shelf, put it back." |
| ChainResponse `(alarm_rings, alarm_off)` | "When the alarm rings, switch it off at the very next step." |
| RespondedExistence `(power_cut, generator_on)` | "If the power ever goes out, the generator must run at some point in the episode (before or after the cut)." |
| Existence `(has_key)`, ExistenceTwo `(door_open)` | DoorKey goals the agent should reach; they only pay. |
| Absence, Precedence, NotCoExistence | Unchanged by P2; they keep their DoorKey examples. |

Only the names changed, so each renamed machine must be the same machine as the one it replaces. The check
walks both on every input sequence up to 5 steps (1,364 sequences, today and with P2) and compares state
counts and rewards: all 9 pairs match, including the earlier task "Whenever you lose the key, pick it up
again" (`Response(key_lost, has_key)`), which is the same Response machine.

## Evidence

- 16 machines: the eight IBM templates alone, hard and soft, soft with the recurrent soft rules on. Four
  soft rows (Absence, Precedence, ChainResponse, NotCoExistence) differ with the setting off; that makes
  20 compiled machines in all, and the check covers all 20.
- 8 of the 16 change: soft Existence and soft ExistenceTwo; RespondedExistence, Response and
  ChainResponse, hard and soft. Soft ChainResponse with the setting off changes too.
- 8 stay the same. Hard Existence and hard ExistenceTwo have a final state, and their text is identical
  to today's. Absence, Precedence and NotCoExistence never leave a clause waiting.
- The positive-cycle check (`_has_positive_cycle`) is false on all 20 machines; the script stops if it is true.
- Every machine with a final state is unchanged.
- Rewards come from the runtime on the reloaded RM text and are cross-checked against the layer's priced
  edge on every step (the script stops if they differ). The 35 traces (counting hard, soft and recurrent-off rows separately) are in `check/traces.txt`.

Totals, today and with P2 (`x` is the trigger, `y` the answer):

| Case | Today | P2 |
| --- | --- | --- |
| Kept (`x y`), Response and ChainResponse | 0 | 0 (-0.1, then +0.1) |
| Broken then fixed (`x - - y`), Response | 0 | 0 |
| Left open at the end (`x - -`, `x -`, `- x`) | 0 | -0.1 |
| ChainResponse broken (`x - y`), hard | -1 | -1.1 |
| ChainResponse broken (`x - y`), soft | -0.5 | -0.5 (-0.1, -0.4, 0) |
| Soft Existence done | 0 | +0.1 |
| Soft ExistenceTwo, one of two / both | 0 / 0 | +0.1 / +0.2 |

## What P2 leaves open

- **A promise left open costs only 0.1.** The box that stays on the floor until the episode ends totals
  -0.1; putting it back totals 0. Finishing a hard goal pays +1.
- **A late fix costs nothing.** `x y` and `x - - y` both total 0. Only the learner's discount prices the
  wait: a fix 50 steps late loses about 0.04 (0.1 × (1 − 0.99^50), computed, not measured).
- **Breaks keep the price they already had.** Soft ChainResponse stays at -0.5. Hard ChainResponse goes
  from -1 to -1.1; the extra 0.1 is the step where the alarm rings.
- **Soft goals get 0.1 and nothing more.** The +1 for finishing needs a hard goal.
- **Hard and soft are the same machine for Response and RespondedExistence.** Both can always be
  repaired, so "you must" and "preferably" pay the same.
- **Two scales.** Rules that wait are priced in tenths; Absence, Precedence and NotCoExistence keep
  -0.5 or the well.

The deeper gap is that nothing judges the end of the episode. The next step, in the user's framing: the
end judgment is the machine "accepting" or "rejecting" the "string of propositions" generated by the
environment, "a link between the environments and the regular expressions / language generations / graphs
world".

## Files

- `index.html`: the page. `data.json`: its content.
- `graphs/`: 18 Reward Machine graphs (live HTML), today and with P2, for the 9 changed machines.
- `check/p2_sim.py`: compiles the machines, applies the P2 patch, walks the traces and runs the checks.
- `check/results.json`, `check/rm-texts.txt`, `check/traces.txt`: its outputs (every machine's RM text
  today and with P2, the traces, and the rename check).
- `check/build_page.py`: builds `data.json` from `results.json`.
- `check/real_code_check.py`: compiles the same 20 machines with the real code (no patch) and compares them
  with the P2 texts in `rm-texts.txt`.

## Rerun

From the repository root, inside `RM_RL_env`. No LLM call.

The simulation patches the code of "today", so it only reproduces on the code before the change. Run it
against a copy of that code (it rewrites `results.json`, `rm-texts.txt` and `traces.txt`; on `e0a054a`
they come out byte-identical to the ones here):

```bash
COPY=$(mktemp -d); git archive e0a054a app | tar -x -C "$COPY"
PYTHONPATH="$COPY/app" python -W ignore docs/paper/rule-only-progress/check/p2_sim.py
```

It ends with `20 machines, 9 changed; positive-cycle check false on every machine; every machine with a
final unchanged; every renamed example matches the one it replaces`. On the current code it would add
the P2 progress to progress already paid, so do not run it there. To rebuild the page, run
`check/build_page.py` the same way, then `fill.py` of the artifacts skill on `data.json`.

The real code, with no patch:

```bash
PYTHONPATH=app python -W ignore docs/paper/rule-only-progress/check/real_code_check.py
```

It ends with `PASS: the real code, no patch, compiles all 20 machines to exactly their P2 text; 9
changed, 11 unchanged`.

## Code

Implemented in `app/src/compiler/reward_layer.py` on branch `feat/rule-only-rewards` (base commit
`e0a054a`; not committed when this entry was updated). With no final state, `_progress` takes the
states where no clause is pending as targets, cuts their outgoing edges, collapses cycles and scores
0 where no target is reachable; an edge into such a state pays no progress, like an edge into the well.
With no final, `_price_edges` counts a soft clause as paid when its waiting starts or stops on an
edge that pays progress (a proxy, approximate both ways). Machines with a final are priced as before,
inert warnings included.

The simulation lacked that last rule: it paid the score difference into a state with no way to a
target (+0.2 for `a & !b & !g` with soft `Existence(g)`, hard `Response(a, b)` and hard
`NotCoExistence(a, b)`, and 0 after the correction). None of the 20 one-clause machines has such a
state, so their texts and every number on the page are the same.

What the real code shows:

- The 20 machines compile to exactly the P2 texts in `check/rm-texts.txt` (9 differ from today's, 11
  are unchanged), as the simulation promised.
- 65 machines compiled before and after (the template catalogue with a goal, 25 sample tasks, the 20
  alone): the 42 with a final are byte-identical; 11 of the 23 without one changed.
- No machine has a positive reward cycle.
- One live run of the real flow, "Whenever you drop the key, pick it up again" (DoorKey, three runs),
  gave the two-state machine with -0.1 on the drop and +0.1 on the pick-up, and no inert warning.
