# Chain prompt loop: rounds

Scoring (tools/chain_score.py): right = card passes and, on an ordered case, no hard Existence on an earlier
step; accepted = ordered case that passes only with an Existence on an earlier step; wrong = card rejects or
the run failed. Models: generator deepseek-v4.1-flash, critic glm-5.3-flash (pinned per run).

## n6 earlier samples (rescored, current cards)

Folders: tp-final-prompt gen-loop2 n6 + n6r, tp-final-live live-loop main, gen-loop2 guard (2 per guard card).
231 runs: right 188, accepted 16, wrong 27. Ordered runs 33: chain 15 (45.5%), accepted 16, wrong 2.
Accepted form: the generator's first proposal writes Existence of every commanded step next to the Precedence;
the critic accepts it (its worked example teaches exactly that set).

Scorer rules added after v0 (tools/chain_score.py): (1) Precedences the level forces (transitive closure of a
card's `forced` Precedences, plus the forced chain pairs of the three cards this loop may not edit) are optional
extras next to `expect`; (2) a hard Existence(x) that the rest of the set already forces (another hard Existence
reached from x by hard Precedences) is logically redundant: a set that passes once those are dropped scores
"accepted" on an ordered case (it still writes one Existence per step) and "right" elsewhere.

## v0 = n6 prompts on main 0389b0b (baseline, fresh)

Cases: 42 (29 regression + W6 + O1-O8 + G1, G2, G4, G7), 3 runs each, 126 runs.
Counts: right 91, accepted 17, wrong 18. Ordered runs 42: chain 22 (52.4%), accepted 17, wrong 3.
n6 earlier samples rescored with the same rules: 231 runs, right 190, accepted 16, wrong 25; ordered 33: chain 15
(45.5%). Pooled n6 (earlier + v0): ordered 75 runs, chain 37 (49%).
Typical accepted set (O7, base-blocked-unlock-pickup): Existence(blocker_moved), Existence(has_door_key),
Existence(target_picked_up), Precedence(blocker_moved,door_open), Precedence(has_door_key,door_open),
Precedence(door_open,target_picked_up): the full chain plus an Existence on every step.
Fresh v0 vs earlier n6 samples (same prompts): W1a 1/3 (was 9/9), W2a 1/3 (7/9), W4a 1/3 (7/9) -- drift of the
pipeline since n6 (bounded critic view, pricing), not of the prompts; the regression base is n6 pooled (earlier+v0).
Conclusion: half of the ordered runs write one Existence per step, almost always next to the full chain.

## v1: chain rule in the generator, template row, critic example (20:31)

Change: generator `reward-ltlf-creator.system.md` sequence bullet rewritten (Existence of the last step plus one
Precedence per pair; earlier steps get no Existence; keep every Precedence of a stated order even when the level
guarantees it; a lone commanded step = no step ordered after it); "prerequisites ... and the task does not state".
`declare-templates.md` "do a, then b" row: Existence(b) + Precedence(a, b), no Existence(a) (the old row led with
Existence(a) + Precedence(a, b)); listed-sequence row: "no Existence for them". Critic: worked example "Observe a,
then b" now accepts Existence(b) + Precedence(a, b) (it accepted the per-step set); goal sentence: in a stated
order do not demand an Existence for an earlier step, ask for a missing Precedence instead.
Counts: 126 runs, right 101, accepted 12, wrong 13. Ordered 42: chain 26 (61.9%), accepted 12, wrong 4.
Regressions: G10 1/3 (base 0.80): drops Response(key_found,target_door_open) for an Existence (v0 had the same set
once). Remaining accepted sets come from the generator's first proposal (critic accepts): W4b/O1 Existence(door_open)
next to the chain; O7 (two steps "in either order" before the door) Existence on every step; O8-r3 the critic wrongly
rejected Precedence(blocker_moved,has_door_key) as unstated.
Conclusion: +10 points of chain, wrong down 18 -> 13; the generator still writes one Existence per commanded phrase.

## v2: generator last check, critic redundancy rejection (20:36)

Change: generator goal bullet notes the stated-order exception; new "Last check before you answer" bullet (drop a
hard Existence that a Precedence chain links to a later goal; steps in any order before c each get a Precedence to
c). Critic item on wording: "One redundancy is worth a rejection" (an Existence of an earlier step next to the last
step's Existence and the chain; ask to remove it).
Counts: 126 runs, right 102, accepted 12, wrong 12. Ordered 42: chain 27 (64.3%), accepted 12, wrong 3.
Regressions flagged: W1b 1/3 (base 0.92: dropped the carry Response(at_exit,holding_box)), W2b 1/3 (base 0.75: once
the carry Response dropped, once the critic demanded a goal the task never commands). Neither touches an ordered
rule; read as noise, recheck on v3's runs.
Traces: the critic redundancy rule never fired (O7-r2: "each of the four commanded events has a hard Existence ...
accepted"); the critic once rejected a correct chain (O6-r2: "Precedence only orders the events if they occur") and
pushed it to Existence(door_open). Accepted sets still come from gen#1.
Conclusion: +2 points; the per-step habit is in the generator's first proposal, driven by "do a -> Existence(a)".

## v3: goal bullet, "do a" row, any-order example (20:41)

Change: generator goal bullet: "When the task orders its steps, only the last step is such a goal: each earlier
step gets a Precedence to the step after it instead of an Existence". declare-templates "do a" row: "when a later
step is ordered after a, a Precedence from a to that step instead". New worked example "Do a and b in any order,
then c": Existence(c), Precedence(a, c), Precedence(b, c), no Existence for a and b.
Counts: 126 runs, right 95, accepted 7, wrong 24. Ordered 42: chain 28 (66.7%), accepted 7, wrong 7.
Regressions flagged: U2 1/3 (carry Response dropped / Precedence(holding_box,at_exit)), U4 0/3 ("Taking the key
means you must open the door too": Response, Precedence(key_lost,..), RespondedExistence(key_lost,..): template and
proposition grounding, no order rule involved). Other new wrongs: G11-r3 the critic demanded Existence(door_open) for
a "never both" rule; O8-r3 read the any-order example into a plain sequence (Precedence(blocker_moved,door_open));
O2/O3 one broken chain link each; G1-r2 an unstated Precedence(door_open,at_goal).
Conclusion: O7 (any-order join) now writes the chain 2/3, but the accepted habit on the two-step "open the door and
then pick up" family stays, and wrong doubled (12 -> 24), mostly grounding noise outside ordered rules. Next: one
critic-only change, so its effect is isolated.

## v4: critic rejection example for a redundant Existence (20:46)

Change (critic only): after the "Precedence alone" rejection example, a third case: `Existence(a)` next to
`Existence(b)` and `Precedence(a, b)` only repeats what the other two force -> reject: "Remove Existence(a); keep
Existence(b) and Precedence(a, b)."
Counts: 126 runs, right 109, accepted 2, wrong 15. Ordered 42: chain 37 (88.1%), accepted 2, wrong 3.
Regressions flagged: U2 1/3, U4 1/3 (as in v3). U2 (and W2b-r3): "If you reach the exit, you must be carrying the
box" -> the critic quotes the carry row and demands Existence(at_exit) for an "if" condition (same set in n6 W2b).
U4 "Taking the key means you must open the door too": Precedence(has_door_key,door_open) / key_lost confusion since
v3's "do a" row change, which blurs a conditional "means ... too" into an order.
Conclusion: the critic example is the lever (+21 points over v3); the per-step sets left are W5a-r1 and G7-r2.

## v5: revert the v3 "do a" row; carry row "if you reach a" (20:51)

Change: declare-templates "do a" row back to `Existence(a)` (suspected of U4); carry row: "When reaching `a` is only
the condition of an "if" ("if you reach `a`, you must hold `c`"), it is `Response(a, c)` alone: no `Existence(a)`".
Counts: 126 runs (5 rate-limited samples rerun at parallel 2), right 99, accepted 8, wrong 19. Ordered 42: chain 28
(66.7%), accepted 8, wrong 6.
Regressions flagged: W1a 1/3 (carry Response dropped, as in n6), W4a 1/3 (shop Response chain via holding_food, as
in n6), U4 1/3 (Response(has_door_key,door_open) x2: the revert did not fix it), G10 1/3 (the critic rejects the
card's Response(key_found,target_door_open) over "on the last step"; v0 fails it too). U2 recovered 3/3.
Traces: the critic accepted redundant sets again (O1-r3 "Existence(door_open) is stated ('open the door')", O7-r1,
G1-r1, G7-r1); in v4 it rejected 5 of them. The critic's goal check still says a step inside "a, then b" needs "a
hard Existence on that event, or another hard clause that forces it".
Conclusion: v4's 88% did not hold without the "do a" row (or was partly luck): critic acceptance is noisy. Pooled
v4+v5 chain 77.4%.

## v6: critic goal check, "do a" row back, "b too" with "must" (20:56)

Change: critic goal check (item 2): "In such an order the hard Existence of the last step with the hard Precedence
chain forces every earlier step, so the earlier steps need no Existence of their own" (it said a step inside "a,
then b" needs "a hard Existence on that event, or another hard clause that forces it"). declare-templates: v3 "do
a" row restored; "only "b also / too / as well" (with or without "must") ... means RespondedExistence".
Counts: 126 runs, right 110, accepted 5, wrong 11. Ordered 42: chain 32 (76.2%), accepted 5, wrong 5.
Regressions: none lost (U4 2/3, G10 2/3 back near base).
Wrong/accepted traces: invented level prerequisites as Precedence (O4-r3 "Grab the key first, then make your way to
the goal" + door chain; G2-r3, W4b-r2); the critic doubts that forcing runs down a chain (O3-r1 critic#2 "no
clause makes them happen", O7-r1 "nothing forces the earlier steps") and pushes an Existence back in.
Conclusion: lowest wrong so far (11 vs n6 rate 12%); chain short of 90%. Pooled v5+v6 chain 71.4%.

## v7: no Precedence for unnamed steps; forcing runs down a chain (21:01)

Change: generator "Keep every Precedence" bullet adds "Never add a Precedence to or from a step the task does not
name, even one the environment requires first." declare-templates Precedence row adds "The forcing runs down a whole
chain: Existence(c), Precedence(b, c) and Precedence(a, b) force b and then a."
Counts: 126 runs (6 rate-limited samples rerun), right 109, accepted 4, wrong 13. Ordered 42: chain 32 (76.2%),
accepted 4, wrong 6.
Regressions: W2b 1/3 (carry Response dropped / an Existence(at_exit) on an "if"); v6+v7 pooled: none lost.
Left: the five-step list (O2 "Find the key, pick it up, open the locked door, go into the room, and then pick up the
ball") still gets one Existence per step 2/3; a plain sequence written as Response 4 times (O2-r3, O6-r2, G7-r2,
G10-r2); invented level prerequisites gone (O4, G1, G2 3/3).
Conclusion: v6+v7 pooled chain 76.2% (64/84), wrong 24/252 = 9.5% (n6 43/357 = 12.0%), no regression case lost.
The 90% stop cannot be reached with one version left (v8 would need > 42/42), so the last slot goes to 3 more runs
of the v7 prompts instead of an edit that one round could not measure.

## v7 replicate (runs r4-r6, same prompts) (21:05)

Counts v7 with 6 runs per case: 252 runs, right 214, accepted 11, wrong 27 (10.7%). Ordered 84: chain 63 (75.0%),
accepted 11, wrong 10.
Final judgment, last two versions pooled (v6 + v7, 378 runs): chain 95/126 = 75.4% (target 90%: NOT met); no
regression-set case lost (W5a 6/9 and U3 6/9 sit exactly on the 2/3 line); wrong 38/378 = 10.1% vs n6 43/357 =
12.0% (met). Against fresh main (v0): chain 52.4% -> 75.4%, accepted 40% -> 13% of ordered runs, wrong 14.3% -> 10.1%.
W5a misses are the soft ban "try not to drop the key while the door is still closed" dropped or written as
Precedence(door_open,key_lost); U3 misses are RespondedExistence for "you have to be carrying the key then, or pick
it up later" (Response). Neither touches the ordered rule.
Observation: a chain-form machine pays nothing until the last step (v7/O6-r1: only +11 at the goal); the per-step
form pays +1 per earlier step reached (v0/O6-r1: +1 on has_key). Same automaton, different progress pay.
Stop: version limit. v1-v7 used; v8 not spent on an edit because v7+v8 could not reach 90% pooled.

## Fix round after the review of the v7 diff (2026-11-19, 21:20 onward)

Review points: P1 a soft last step drops an earlier hard command; P2a "lone" defined three ways;
P2b the critic rejects a card's also_ok set (deliberate, needs the critic intro to agree);
P3 a stale card note and long lines.

New cases S1-S4 (local cards `outputs/chain-loop/cards/local-soft`, new wording, last step soft):
- S1 "Grab the key, and after that get to the goal square if you can."
- S2 "Pick up the key, then open the door, and then, ideally, walk onto the goal."
- S3 "Open the door, then, if possible, pick up the box in the other room."
- S4 "Take the key, then open the door. After that, try to pick up the box in the other room."
The order into the soft step may be hard or soft (both pass); the level forces it, so it is optional.

### v7s: S1-S4 on the v7 prompts (6 runs)
- 24 runs: 17 right, 0 accepted, 7 wrong. Wrong: the soft goal made hard (S1 x3, S2, S3), Response (S3),
  S2-r1 dropped door_open. The exact P1 set (hard Precedence + soft goal, no Existence of the first step)
  did not show up; v7 mostly made the goal hard instead.

### v8: soft last step, one "lone" definition, critic optional change, card note, wraps
- Edits: scripts/v8_edits.py and v8b_critic.py (the critic used "lone" once for "alone").
- 42 cases x 6: 252 runs, 217 right, 9 accepted, 26 wrong; ordered chain 65/84 = 77.4% (v7 x6: 75.0%).
- S1-S4 x 6: 17 right, 4 accepted, 3 wrong (v7s: 7 wrong).
- Flagged vs v7 x6: U5 3/6, G10 2/6. Six more runs of U5, G10, W6, U6, W4a, W3a:
  U5 7/12 and G10 6/12 (lost vs v6+v7 8/9, 7/9), W6 5/12 (not in the set; was 9/9), W4a 7/12, U6 10/12.
- Traces: the critic read "the one optional change you may ask for" as optional and accepted redundant
  sets with a note (G10-r12, U5-r8); U5 first proposals put Existence(door_open) on the first step 6/12
  (v7 1/6); W6/U6 wrote the soft ban as Precedence(door_open, key_lost) and the critic accepted it.
- Verdict: not kept as final; v9 rewords the critic exception and tightens the lone definition.

### v9: critic "reject and ask to remove"; lone definition by contrasts (scripts/v9_edits.py)
- 42 cases x 6: 204 right, 14 accepted, 34 wrong; ordered chain 55/84 = 65.5%. Lost: W4a 3/6, U5 3/6.
- S1-S4: 15 right, 2 accepted, 7 wrong. W6 1/6: the soft ban as Precedence(door_open, key_lost) got worse.
- Verdict: reverted to v8.

### v7c: control, v7 prompts again on W6, U5, G10 (6 runs)
- W6 4/6, U5 5/6, G10 3/6. No Precedence(door_open, key_lost). G10's drop is drift or noise.

### v10: v8 minus the lone item "a step ordered before an event the task never commands" (scripts/v10_edits.py)
- 42 cases x 6: 210 right, 13 accepted, 29 wrong; ordered chain 55/84 = 65.5%. None lost vs v6+v7+v7c.
- S1-S4: 14 right, 2 accepted, 8 wrong. Soft ban as order still 9/36 in the six key_lost cases.

### v7n: control, v7 prompts on the 14 ordered cases + S1-S4 (6 runs), same hour as v10
- Ordered chain 59/84 = 70.2% (v7 earlier: 75.0%). S1-S4: 16 right, 8 wrong (6 soft goal made hard).
- Soft ban as order: 1/24.

### v11: v10 with a hard Precedence in both new worked examples (scripts/v11_edits.py) - final
- Screen (W4b, W5a, O1, U5, W6, U6, S1-S4): soft ban as order 1/36 (v10 9/36).
- 42 cases x 6 (+ W1b to 12): 214 right, 7 accepted, 31 wrong; ordered chain 68/84 = 81.0%.
  None lost vs v6+v7+v7c+v7n (W1b 3/6 at 6 runs, 8/12 at 12).
- S1-S4: 18 right, 6 wrong (3 soft goal made hard, 2 hard step unforced, 1 Response).
- Soft-case error kinds over the fix round (96 runs): soft goal made hard 8, hard step unforced 9 (7 on
  three-step tasks, Existence on the first step), other 7. v7 (48 runs): 11, 1, 3.
- Live prompts = v11 (`scripts/use_prompts.py v11` restores it; snapshots in each version's prompts/).
