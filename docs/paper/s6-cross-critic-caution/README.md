# Cross-critic caution: FARM's critic rejects ARM-FM machines for having no clauses

Date: 2026-11-12, from the S6 live smoke (L6.1 and L6.3) on three DoorKey and UnlockPickup cards.
Three machines, one model pair (generator `deepseek-v4.1-flash`, critic `glm-5.3-flash`): a caution
for reading the cross-critic table, not a measurement of ARM-FM's machines.

## What it shows

The benchmark lets each pipeline's critic judge the other pipeline's machines. FARM's critic reads the
task, the environment and the **clause list** the compiler built, then checks the machine against them.
ARM-FM writes its machine directly and has no clauses. We pass FARM's critic the machine with an empty
clause list and a note saying so. On all three smoke cards it rejected the machine, and each rejection
opens by saying the clause list is empty and asks to add clauses:

| Card | Natural-language task | LTL for ARM-FM | FARM critic, opening words |
| --- | --- | --- | --- |
| `smoke-doorkey-base` | Use the key to open the door, then reach the goal. | none (machine written directly) | "CHANGES REQUIRED: the clause list is empty while the task requires three events ..." |
| `smoke-doorkey-response` | Whenever you hold the key, open the door afterwards, and reach the goal. | none | "CHANGES REQUIRED: no clauses were compiled from the task, so the machine was written directly by a model. Add hard clauses ..." |
| `smoke-unlock-pickup-base` | Acquire the matching key, unlock the door, and pick up the designated box in the other room. | none | "CHANGES REQUIRED: the clause list is empty, yet the task commands three events unconditionally and in order ..." |

The same happened in LI.2 on the event room: both rejections of ARM-FM's last candidates say the clause
list is empty (`cx-siren`: "the clause set is empty ... Add that hard Response clause"; `cx-box`: "The
clause list is empty, so the compiled machine was not built from clauses"). Those candidates were
not accepted by ARM-FM's own critic either, so a rejection was likely whatever the reason given.

What each critic asks for tells the same story. The requested fix in all three smoke rejections is
"add these clauses" (for example `Existence(has_key)`, `Precedence(has_key, door_open)`), which an ARM-FM
machine cannot act on. The critic's information note says the same thing in the data: it "cannot
check clause fidelity, which it normally judges".

## The Reward Machines

The three ARM-FM machines, each accepted by ARM-FM's own critic (status `complete`). Graphs are live
HTML (drag a state, click an edge); the RM text is beside each.

| Card | Graph | RM text |
| --- | --- | --- |
| `smoke-doorkey-base` | [graph](graphs/arm-fm-doorkey-base.html) | [text](graphs/arm-fm-doorkey-base.rm.txt) |
| `smoke-doorkey-response` | [graph](graphs/arm-fm-doorkey-response.html) | [text](graphs/arm-fm-doorkey-response.rm.txt) |
| `smoke-unlock-pickup-base` | [graph](graphs/arm-fm-unlock-pickup-base.html) | [text](graphs/arm-fm-unlock-pickup-base.rm.txt) |

`smoke-doorkey-base` as text:

```text
STATES: u0, u1, u2, u3        INITIAL_STATE: u0        FINAL_STATES: u3
(u0, has_key) -> u1            reward 0.1
(u1, door_open) -> u2          reward 0.3
(u2, at_goal) -> u3            reward 1
(u2, else) -> u1               (a regression when the door is no longer open)
```

## The other direction

ARM-FM's critic also rejected all three FARM machines. Its reasons mix a format convention (FARM's
compiled text leaves the per-state `else` self-loop implicit by design, see
`docs/decisions/arm-fm/rm-execution.md`) with claims about the environment that we did not check. Its
information note says it did not see the clauses or the compiler warnings. The record keeps the two
directions apart, and so does this entry: the FARM-critic column is not evidence about the ARM-FM
machines' quality.

## What this does not show

- It does not show that the three ARM-FM machines are right or wrong; the smoke ran no judge or training.
- Three cards and one model pair. The pattern is consistent (3 of 3, and 2 of 2 in LI.2), but it is a
  handful.
- The fix is a table rule, not a code change: report the cross-critic columns per direction, with the
  information note, and never read the FARM critic's verdict on an ARM-FM machine as a quality score.

## Files

- `evidence/l6-smoke-evidence.json`: for each of the six smoke bundles, the task, the clauses, the RM text,
  the generation stamp and the cross-critic verdict with its full text and information note.
- `evidence/l63-critic-{farm,arm-fm}.out`: the cross-critic command output (3 judged, 0 accepted).
- `graphs/`: the three ARM-FM machines.

## Rerun

The smoke needs the provider and the bundles of the run, so it is not rerun from this folder. The
verdicts are in the evidence file. To list them:

```bash
python -c "import json; [print(e['arm'], e['card'], e['cross_critic']['verdict'], e['cross_critic']['flag'][:90]) for e in json.load(open('docs/paper/s6-cross-critic-caution/evidence/l6-smoke-evidence.json'))]"
```

## Code

The `cross-critic` command and the explicit `arm_fm_critic` opt-in of `generate-suite`
(`app/scripts/`), merged into the wave as `merge: tp-s6-generation` (commit `ab1ecbc`). The decision
that keeps the two directions apart is in `docs/decisions/benchmark/thesis-benchmark.md`.
