# A rule-only task end to end: `shop-siren`, and `cx-rules-only` below it

Date: 2026-11-25, for the thesis section "Reward assignment" (`sec:rule-only`) and its Figure 3.9, the
TikZ drawing of the siren machine (`paper/images/farm/rm-rule-only.tex`). The first example is card
`shop-siren`, the machine the final FARM run trained on. The second, from 2026-11-24, is the larger
`cx-rules-only` that the section used before; its material starts at "Second example" below.

## shop-siren: what it shows

A task that only sets one rule and names no goal, compiled to a Reward Machine with 2 states and no
final state, and what that machine pays: a ring opens a promise (-1), the toggle that silences the
siren keeps it (+1). The page holds the card, its clause and LTLf, the machine, one 6-step trace with
state and pay at each step, the card's plan check, and what the final run learned on this machine
(FARM 1.0 on 3 of 3 seeds, no-RM 1 of 3). The graph is the repository's own `render-rm --html` output:
[evidence/graph/shop-siren.html](evidence/graph/shop-siren.html). The machine is the stored bundle
file, rebuilt from its clause by the frozen compiler: no model call.

## shop-siren: the card

Card `shop-siren` (suite `shop`, level 1, `gym_id` `MiniGrid-Shop-v0`, `goal: false`, template
`Response`, `experiments/benchmark/shop/tasks.json`):

> Keep the shop quiet: whenever the siren rings, turn it off.

The generator (`deepseek-v4.1-flash`, reasoning `max`, critic `glm-5.3-flash`) wrote 1 clause in 1
attempt with 0 critic interventions (110.8 s):

| # | Sentence | Template | Priority | LTLf |
|---|---|---|---|---|
| 1 | Whenever the siren is ringing, the agent toggles the siren switch to turn it off. | `Response(siren_ringing, switch_toggled)` | hard | `G (siren_ringing → (F switch_toggled))` |

The LTLf as the run's `judge.json` stores it: raw `(G(siren_ringing->(Fswitch_toggled)))`, readable
`(G (siren_ringing -> (F switch_toggled)))`.

The shop is `MiniGrid-Shop-v0` (`experiments/benchmark/envs/shop/environment.md`): the siren starts by
itself (first at step 3 to 30, then 25 to 69 steps after each toggle) and rings until the agent
toggles the switch. `switch_toggled` is true on every toggle of the switch, also when the siren is
silent. The clients and the food slips run too, so the room is the one every card sees.

## shop-siren: the machine

`evidence/graph/shop-siren.rm`, byte-equal to the bundle's `reward_machine.txt`:

```
REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES:
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, siren_ringing&!switch_toggled) -> u1
(u1, switch_toggled) -> u0
REWARD_FUNCTION:
(u0, siren_ringing&!switch_toggled, u1) -> -1
(u1, switch_toggled, u0) -> 1
```

- `u0`: the shop is quiet. No promise is open.
- `u1`: the siren rings and has not been silenced. The promise of the `Response` is open.
- A step no transition lists stays put and pays 0 (`DEFAULT_REWARD`): walking, a toggle on a silent
  siren, a siren that keeps ringing.
- There is no final state, no well and no end judgment. A hard `Response` can be broken only by the
  episode ending with the siren on, and the run's `time_limit_penalty` is 0.0, so a ring left open
  keeps its -1 and nothing more. A ring that is answered nets 0.
- Both pays are the progress part of the reward layer (`_progress`,
  `app/src/compiler/reward_layer.py`): the machine rebuilt with the progress part off pays 0 on every
  transition.
- The bundle is in commit `e6c3acba` (`data(benchmark): final-run bundles generated on the freeze
  (809dfe3)`), stamped `809dfe3f932528c90be33232ddd684a883d8fbb0` (not dirty), and no later commit
  touches `reward_machine.txt`. `state_descriptions.json` holds the two state texts and
  `embeddings.json` their 768-dimension vectors (`nomic-embed-text`).

## shop-siren: one trace

This 6-step episode is made up to show the edges, not a recorded run. Each step lists the propositions
that are true after it. The script runs it through the real `RewardMachineRuntime` and checks every
step.

| Step | Labels true | State | Pay | Total | What happens |
|---|---|---|---|---|---|
| 1 | none | u0 -> u0 | 0 | 0 | the shop is quiet, nothing happens |
| 2 | `siren_ringing` | u0 -> u1 | -1 | -1 | the siren starts ringing: the promise opens |
| 3 | `siren_ringing` | u1 -> u1 | 0 | -1 | the agent walks to the switch, the siren still rings |
| 4 | `switch_toggled` | u1 -> u0 | +1 | 0 | the agent toggles the switch, the siren stops: the promise is kept |
| 5 | `siren_ringing` | u0 -> u1 | -1 | -1 | the siren rings again: the promise opens |
| 6 | `switch_toggled` | u1 -> u0 | +1 | 0 | the agent toggles the switch again: the promise is kept |

## shop-siren: the plan check

`experiments/benchmark/shop/bundles/farm/shop-siren.plan_check.json` holds 12 real runs of the card's
plans on the shop (event seeds 1 to 3, 600 steps, `[plain, discounted]` pay), with no problem found:

- `solve` (the scripted shop worker): ends in `u0`, plain pay 0 (discounted -0.1753, -0.212, -0.2107).
- `wrong-0` (serves the clients, never switches the siren off) and `wrong-1` (does nothing for 600
  steps): end in `u1`, plain pay -1 (discounted -0.8601, -0.7778, -0.7857).
- `idle`: the plan that only waits, which the check adds for a machine with no final state, the same
  run as `wrong-1`: `u1`, -1.

Doing nothing is not a pass: the first ring always comes within the first 30 steps and leaves the
machine in `u1` for good.

## shop-siren: what the final run learned

The final FARM run trained PPO (1,500,000 steps, 3 seeds) with `reward_source: rm` on this bundle
(`bundle:` in its `run-config.yaml`), started 2026-11-22 14:27. The no-RM arm trained on the
environment's own reward. Judged success is `mean_judged_success` of each run's `judge.json`, over 100
evaluation episodes.

| Method | Seed 1 | Seed 2 | Seed 3 |
|---|---|---|---|
| FARM (this machine) | 1.0 | 1.0 | 1.0 |
| no-RM | 0.0 | 0.0 | 1.0 |

Caveat on the encoding: this card trained with the machine state as an embedding (`rm_state_encoding:
embedding`, the default since `58984baf`; each FARM run's resolved `config.yaml` says so and its
`run-config.yaml` has no such key), not as a one-hot vector. The 1.0 is the result with the embeddings
of the two state texts. The no-RM arm has no machine state, so the setting does not apply to it. Three
runs per method are counts, not rates: the arms differ by 3 of 3 against 1 of 3.

## shop-siren: evidence

- `evidence/shop-siren-check-output.txt`: the checks the script passed (rebuilt machine equals the
  stored text, the states, the two transitions and their pays, both pays are progress, the trace, the
  plan check, the six judged results, the embedding encoding, the README tables).
- `evidence/shop-siren-clauses.md`, `shop-siren-trace.md`: the tables above.
  `evidence/shop-siren-results.json`: the six judged results with their run folder names (the run
  folders are git-ignored under `outputs/runs/`).
- `evidence/graph/shop-siren.{rm,svg,html}`: the machine and its `render-rm --html` graph.
- `check/siren_example.py`: the script that writes all of the above.

## shop-siren: gaps

- The 6-step trace is made up. The plan check lists end states and pays of 12 real runs, not their steps.
- The manifest says `provenance.status: "reconstructed"`, `generator: "compiler-adaptation"`. That is
  the label every compiler-adapted bundle gets (`generation.py`), not a sign of a rebuilt machine.
- The run folders are not in Git. A rerun needs the main checkout that holds `outputs/runs/`.
- Embedding encoding, not one-hot (above). Three seeds per method.

## shop-siren: rerun

From the repository root, inside `RM_RL_env`, no model call (MONA runs locally):

```bash
env OMP_NUM_THREADS=4 PYTHONPATH=app python -W ignore docs/paper/rule-only-example/check/siren_example.py
```

It reuses `rebuild`, `walk`, `trace_table` and `clause_table` of `check/rule_only_example.py` (same
folder) and fails if the rebuilt machine differs from the bundle's `reward_machine.txt`. The compiler
files are the same on the freeze and on main `2e62e243`, where it was checked.

# Second example: `cx-rules-only`

Date: 2026-11-24, for the thesis section "Reward assignment" (`sec:rule-only`). One card, the frozen
pipeline (commit `809dfe3`), no model call: everything below is recomputed from the clauses the
bundle stores.

## What it shows

A task that only sets rules and names no goal, compiled to a Reward Machine with no final state, and
what that machine pays: the card, its three clauses with their LTLf, the 3 states and 17
transitions, the pay of every case split into its parts, one 6-step trace with state and pay at each
step, and the recorded plan traces of the same card. The graph is the repository's own
`render-rm --html` output: [evidence/graph/cx-rules-only.html](evidence/graph/cx-rules-only.html).
It merges edges by outcome ("6 cases", "mixed r") and is cramped, so the tables carry the numbers.

## The card

Card `cx-rules-only` (suite `complex`, `gym_id` `MiniGrid-BlockedUnlockPickup-v0`, `goal: false`):

> Do not pick up the box in the other room. Try not to drop the key while the door is still closed.
> Whenever you are holding the key, try to have the door open at that moment or open it afterwards.

The generator (`deepseek-v4.1-flash`, reasoning `max`, critic `glm-5.3-flash`) wrote 3 clauses in 1
attempt with 0 critic interventions:

| # | Sentence | Template | Priority | LTLf |
|---|---|---|---|---|
| 1 | Never pick up the target box. | `Absence(target_picked_up)` | hard | `¬(F target_picked_up)` |
| 2 | Try not to lose the key before the door is opened. | `Absence(key_lost)` | soft | `¬(F key_lost)` |
| 3 | Whenever the key is held, try to have the door open at that moment or later. | `Response(has_door_key, door_open)` | soft | `G (has_door_key → (F door_open))` |

The label `key_lost` already carries the door condition (true when the key was held at the previous
step, is not now, and the door is not open), so `Absence(key_lost)` is "do not drop the key while
the door is closed": `app/src/benchmark/reference_labels.py:99` and `app/src/models/environment.py:67`.

No clause is an `Existence`, so there is no goal and the machine has no final state
(`FINAL_STATES:` is empty). The compiler says so in its warning: "Rule-only task: no hard goal
clause, so the machine has no final state; progress is paid toward the states where no clause is
pending, and episodes end on a well, the environment's end, or the time limit".

## The machine

3 states, initial `u0`, no final state, rejecting state `u1` (the well); 17 transitions (10 from
`u0`, 7 from `u2`). The text is `evidence/graph/cx-rules-only.rm`, byte-equal to the bundle's
`reward_machine.txt`.

- `u0`: the start. The promise of clause 3 is not open.
- `u1`: the well. The hard rule was broken (the target box was picked up). The episode ends.
- `u2`: the key is held and the door is shut. Clause 3 is pending: a promise is open.

## How the code pays it

`app/src/compiler/reward_layer.py`. The frozen switches are `reward_progress`, `reward_well`,
`reward_soft_break`, `recurrent_soft_penalty`, `fold_soft_absence`, `hard_ceiling` and
`minimize_machine` on; `reward_end_judgment` and `reward_promise_cost` off; `soft_break_cost` 1.0,
`gamma` 0.99, step limit 576 (`evidence/result.json`).

- **Progress** (`_progress`, `reward_layer.py:740`). Potential-based. With no final, each clause is
  counted alone (`counted = range(len(owed[product.initial]))`, line 772) and the targets are the
  states where no clause is pending (line 763). A state owes the stages its clauses still have to
  go, and `u2` owes one more than `u0` (clause 3 waits for `door_open`). An edge pays
  `PROGRESS_REWARD` (1.0) per stage repaid and charges 1.0 per stage opened, so a promise opened
  and kept nets 0, and one opened and never kept leaves its charge standing.
- **Soft break**. Each new break of a soft clause pays `-soft_break_cost`, -1. With the recurrent
  soft penalty every new `key_lost` costs again.
- **Hard break**. An edge into the well pays `hard_break_charge(1.0, 0.99, 576, 1)`
  (`reward_layer.py:678`) = -100.693893827: more than any stream of soft breaks over the step limit
  at that discount (99.69), plus one progress unit. Its progress part is
  `min(0, potential[source] - potential[start])`, 0 here, so a hard break totals the same wherever
  it happens.
- **Nothing else**. A case no transition lists stays put and pays `DEFAULT_REWARD` 0 (the `else`
  rows). The machine has no end judgment (`judgment` is `None`), so it pays nothing when the
  environment or the time limit ends the episode.

## Pay of each case

Every case of each live state, over the 16 valuations of the 4 propositions the machine uses
(`door_open`, `has_door_key`, `key_lost`, `target_picked_up`), grouped by where it goes and what it
pays (the guards are merged to the fewest cubes, and the script checks each group holds exactly its
valuations). `Progress` is the pay minus the pay of the same machine rebuilt with the progress part
off (`reward_progress=False`, same 3 states); `Break or well` is what that rebuild pays.

| From | When | To | Pay | Progress | Break or well | What happens |
|---|---|---|---|---|---|---|
| u0 | else | u0 | 0 | 0 | 0 | nothing |
| u0 | `(!has_door_key & !target_picked_up & key_lost) or (door_open & !target_picked_up & key_lost)` | u0 | -1 | 0 | -1 | a soft rule breaks |
| u0 | `has_door_key & !door_open & !target_picked_up & !key_lost` | u2 | -1 | -1 | 0 | a promise opens |
| u0 | `has_door_key & !door_open & !target_picked_up & key_lost` | u2 | -2 | -1 | -1 | a soft rule breaks and a promise opens |
| u0 | `target_picked_up` | u1 (well) | -100.694 | 0 | -100.694 | hard rule broken: the well |
| u2 | else | u2 | 0 | 0 | 0 | nothing |
| u2 | `!door_open & !target_picked_up & key_lost` | u2 | -1 | 0 | -1 | a soft rule breaks |
| u2 | `door_open & !target_picked_up & !key_lost` | u0 | +1 | +1 | 0 | a promise is kept |
| u2 | `door_open & !target_picked_up & key_lost` | u0 | 0 | +1 | -1 | a soft rule breaks and a promise is kept |
| u2 | `target_picked_up` | u1 (well) | -100.694 | 0 | -100.694 | hard rule broken: the well |

The 17 stored transitions with the same split are in `evidence/edge-pays-full.md`. The cases with
`door_open & key_lost` are listed because the machine treats the four propositions as independent;
the real `key_lost` is false whenever the door is open, so the environment never produces them.

## One trace

This 6-step episode (`check/trace.json`) is made up to show the edges, not a recorded run; it
crosses all three rules. The four recorded plan traces of the same card are listed beside it, in
the next section. Each step lists the propositions that are true. The script runs it through the
real `RewardMachineRuntime` and checks every step against the reward layer's own numeric
transitions.

| Step | Labels true | State | Pay | Total | What happens |
|---|---|---|---|---|---|
| 1 | none | u0 -> u0 | 0 | 0 | walking, nothing happens |
| 2 | `has_door_key` | u0 -> u2 | -1 | -1 | picks the key up, the door is closed: the promise opens |
| 3 | `key_lost` | u2 -> u2 | -1 | -2 | drops the key, the door is still closed: the soft rule breaks |
| 4 | `has_door_key` | u2 -> u2 | 0 | -2 | picks the key up again: the promise stays open |
| 5 | `has_door_key`, `door_open` | u2 -> u0 | +1 | -1 | opens the door: the promise is kept |
| 6 | `door_open`, `target_picked_up` | u0 -> u1 | -100.694 | -101.694 | picks up the target box: the hard rule breaks, the episode ends |

## Recorded plan traces of the same card

The four recorded runs in `experiments/benchmark/complex/traces/cx-rules-only/` (real environment
labels, seed 1) walked through the same machine. Only the steps where the machine moves or pays are
listed.

| Plan trace | Steps | Steps where the machine moves or pays | Total |
|---|---|---|---|
| `solve-s1` | 21 | 13: u0 -> u2 (-1); 21: u2 -> u0 (+1) | 0 |
| `wrong-0-s1` | 28 | 13: u0 -> u2 (-1); 21: u2 -> u0 (+1); 28: u0 -> u1 (-100.694) | -100.694 |
| `wrong-1-s1` | 27 | 3: u0 -> u2 (-1); 4: u2 -> u2 (-1); 27: u2 -> u0 (+1) | -1 |
| `wrong-2-s1` | 576 | 13: u0 -> u2 (-1) | -1 |

The plan that solves the card totals 0, picking up the box ends in the well, dropping the key costs
1, and holding the key to the time limit without opening the door leaves the -1 of the open promise
standing.

## The card in the candidate list

Cards with no `Existence` among their expected clauses, a bundle built by the frozen code (stamp
`809dfe3`), 3 to 5 states:

- 3 states: `cx-rules-only` (chosen; 3 clauses, hard and soft), `tpl-responded-existence-1-nogoal`
  and its `-forced` form (hard), `tpl-responded-existence-2-nogoal` (training card),
  `tpl-responded-existence-3-nogoal`, `tpl-responded-existence-soft-1-nogoal` (training card),
  `tpl-precedence-1-nogoal`, `-2-`, `-3-`.
- 4 states: `tpl-not-co-existence-1-nogoal`, `-2-`, `-3-`.
- 5 states: `tpl-chain-response-1-nogoal`, `-2-`, `-3-`, and the box-carry forms
  (`tpl-chain-response-1-nogoal-carry` is a training card).

Left out: cards of 1 or 2 states (a start and a well, or a single state), shop cards (17 to 129
states), and `shop-ladder-*` (bundles stamped `881b22d`, not the freeze). `cx-rules-only` is the
only candidate with a hard rule, a soft rule and a promise in one small machine, so a break of each
kind and a promise opened and kept all show in 3 states. The level benchmark counts its rewordings
`cx-rules-only~p1` and `~p3`: accepted in all 3 runs at each of the 5 levels (`none`, `low`,
`medium`, `high`, `max`) of `docs/paper/level-benchmark-freeze/records/`.

## Evidence

- `evidence/check-output.txt`: the checks the script passed (rebuilt machine equals the stored
  text, every edge into the well pays `hard_break_charge`, the trace and the plan traces equal the
  layer's own transitions, the README tables equal the evidence tables).
- `evidence/clauses.md`, `edge-pays.md`, `edge-pays-full.md`, `trace.md`, `plan-traces.md`: the
  tables above. `evidence/result.json`: the same data with the DFA state labels of each clause and
  the switches.
- `evidence/graph/cx-rules-only.{rm,svg,html}`: the machine and its `render-rm --html` graph.

## Gaps

- The 6-step trace is made up to show the edges, not a recorded episode. The recorded ones are in
  the last table.
- `cx-rules-only` is a generation card (`train: false`): no learned result exists for it.
- The progress split rebuilds the machine with progress off. The well charge depends on the soft
  break pricing, so only the progress part is additive; the table never splits the well charge.
- The manifest says `provenance.status: "reconstructed"`. That is the label every
  compiler-adapted bundle gets (`generation.py`), not a sign of a rebuilt machine.
- The thesis draws a TikZ figure by hand, Figure 3.9 (`paper/images/farm/rm-rule-only.tex`), of the
  `shop-siren` machine, not of this one; the repository has no generic RM-to-TikZ exporter.

## Files

`README.md`, `check/rule_only_example.py`, `check/trace.json`, and `evidence/` as listed above.

## Rerun

From the repository root, inside `RM_RL_env`, no model call (MONA runs locally). Without `-I`,
which ignores `PYTHONPATH`. On the frozen code:

```bash
git archive 809dfe3 app | tar -x -C <empty folder>
env OMP_NUM_THREADS=4 PYTHONPATH=<empty folder>/app python -W ignore docs/paper/rule-only-example/check/rule_only_example.py
```

`evidence/check-output.txt` then names the code it ran on. The compiler is the same files at HEAD
(below), so `PYTHONPATH=app` on the checkout gives the same evidence. The script fails if the
rebuilt machine differs from the bundle's `reward_machine.txt`.

## Code

The bundle `experiments/benchmark/complex/bundles/farm/cx-rules-only/` is stamped with commit
`809dfe3f932528c90be33232ddd684a883d8fbb0` (not dirty). `git diff 809dfe3 HEAD -- app/src/compiler`
is empty on main `7a005656`. The other `app/` differences since the freeze (new `Configuration`
options, the `env_rm_state` reward source in `runtime.py`, the tagger flag in `ablate_rm.py`) do not
touch the rebuild or the pay. The rebuild owner is `app/scripts/ablate_rm.py` (`_stored_task`,
`_recorded_switches`, `_build`); the graph is `app/scripts/render_rm.py` (`render_file`).
