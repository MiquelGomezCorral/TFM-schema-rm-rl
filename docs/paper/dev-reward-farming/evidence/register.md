# Hack register: the reward-farming rows (copy)

Copied on 2026-11-23 from `.git/agent-memory/plans/testing-program-20261111/hacks.md` (private plan notes), lines
1-20, 23-27, 29, 32 and 39-40. The lines below the rule are verbatim. `S/` in the rows is that plan's `slices/`
folder; the slice lines the rows quote are in `slice-excerpts.md`.

H3, H4, H6 and H7 are the four farming cases. H5, H9 and H12 are weaker or partial:

- H5: greedy only. The sampled policy solves the card, and the loop passes through `box_fell`, a world event.
- H9: the row's main finding is an empty pass of the no-RM arm; its ARM-FM run farms the key loop of H6 and H7.
- H12: two probes on unmerged code (`rm_ends_episode: false`), stopped at 2.2-2.4M of 3M steps, never judged,
  one seed. shop-full's loop starts on the siren ring, so it is the siren task, not a loop the agent makes alone.

---

# Hack register: where agents pass or collect reward without doing what the card means

Rule (user, 2026-11-14): "whenever a hacking appears, you know it ... We have to write down and analyze." Every hack seen
in training or judging gets a row here, an analysis, and a card or environment version the agent cannot game. Paper
material: ask before copying to `docs/paper/`.

Kinds:

- **Empty pass:** a conditional rule's trigger never happens, so the rule passes untested.
- **No attempt:** the agent idles to the step limit because doing nothing passes or costs nothing.
- **Reward farming:** the machine's path cycles to collect positive reward again and again (`S/train-closed/cycles.py`).
- **Other:** anything else that games the judge or the reward.

Detection: the judge's per-rule activation share and non-empty judged success (judge-metrics slice), the positive and
negative reward split, the cycle check, and episode length at the step limit with zero reward.

## Register

| # | Found | Card(s) | Arm, seed | Kind | What the agent did (evidence) | Why it could | Fix version | Status |
|---|---|---|---|---|---|---|---|---|
| H3 | 2026-11-14 (audit, closed-set runs) | `base-doorkey` (DoorKey) | ARM-FM s1-s3 | reward farming | Picks up and drops the key 282 and 306 times per episode (seeds 1, 2), never opens the door; 640/640 steps, machine return 28.2 / 30.6 / 29.9, judged 0, env 0 (audit E9) | ARM-FM's machine pays +0.1 on key pickup and moves back to the start state on a drop, so the loop pays again and again (`base/bundles/arm-fm/base-doorkey/reward_machine.txt:6,9,15`) | Audit R5: pay first progress once, keep "already paid" across drops. A method's machine: fix is the user's call | decided (user 11:56): results only, no fix |
| H4 | 2026-11-14 (audit, closed-set runs) | `tpl-precedence-1-goal` (BlockedUnlockPickup) | ARM-FM s1-s3 | reward farming | Picks up and drops the key 206 and 214 times per episode (seeds 1, 2), never opens the door; 576/576 steps, machine return 30.6 / 32.3 / 33.9, judged 0 (audit E10) | Same pattern: the key pickup edge pays +0.15 and a drop returns to the earlier state (`templates/bundles/arm-fm/tpl-precedence-1-goal/reward_machine.txt:8,11,18`) | As H3 | decided (user 11:56): results only, no fix |
| H5 | 2026-11-14 (train-all phase 1) | `tpl-chain-response-1-goal` (ServiceRoom, box falls) | ARM-FM s1 | reward farming (greedy only) | Training episodes exit in 99.99% of the last 1.2M steps (mean length 24.5), but 46% of them lap the positive cycle `u1 -> u2 -> u1` (`holding_box`, +0.3 per lap) before exiting. The **greedy** test policy loops for the full 200 steps (final eval length 200, judged 0.00) while the **sampled** policy solves it (1.00) (`S/train-all/report.md` §1, `S/train-all/cycles.md`) | ARM-FM's machine pays again on every pickup after a fall, and the box falls on a schedule, so picking it up again is a loop the greedy policy prefers to leaving | Kind of H3/H4 (machine's own loop): results only, per the user's 11:56 rule. Report greedy and sampled side by side so the loop is visible | recorded, results only |
| H6 | 2026-11-14 (train-all phase 1) | `tpl-existence-two-1-nogoal` (DoorKey-8x8) | ARM-FM s1 | reward farming | Greedy 0.00 (no-RM solves DoorKey, 1.00); RM path cycles in 98% of the last 300k steps' episodes, every eval episode hits the 640-step limit, RM return ~29.6; 88 min wall vs ~30 for DoorKey ARM-FM (`S/train-all/report.md`, `tables.md`) | Static positive cycle `u0 -> u1 -> u0` on `key_lost`: take key (+0.1/+0.2), drop, take again (`S/train-all/cycles.md`); same pattern as H3 | Results only (user 11:56) | recorded, results only |
| H7 | 2026-11-14 (train-all phase 1) | `tpl-existence-two-1-goal` (UnlockPickup) | ARM-FM s1 | reward farming | Greedy 0.00; cycles in 100% of episodes, every eval episode hits the 288-step limit; 51 min (`S/train-all/report.md`, `tables.md`) | Same key pickup/drop loop as H6 | Results only (user 11:56) | recorded, results only |
| H9 | 2026-11-14 (re-judge, seed 1) | `tpl-responded-existence-1-nogoal` (UnlockPickup) | no-RM s1, ARM-FM s1 | empty pass (no-RM); reward farming (ARM-FM) | no-RM: `RespondedExistence(has_door_key, door_open)` triggers in 0% (judged 1.00, non-empty 0.00). ARM-FM: judged 0.01, key pickup/drop loop in 100% of episodes, RM return 28.2 | Conditional rule; ARM-FM machine pays the key pickup again after a drop | Forced card `tpl-responded-existence-1-nogoal-forced` (key held at reset, audit R4): merged (b332ecf), bundles ready; runs dropped by the user before start (16:40). Farming stays as results (user 11:56). Real test: reactive cards (`reactive-cards` page) | forced runs dropped; reactive cards proposed |
| H12 | 2026-11-15 (probe for Q1, unmerged `rm_ends_episode: false`, stopped at 2.2-2.4M of 3M) | `shop-serve`, `shop-full` (Shop) | ARM-FM s1 | reward farming | shop-serve: never serves (env return -9.5 = idle in every eval); last 200 training episodes machine return 5.9, RM path loops `u3 u5 u3 u5` for 600 steps: drops the dish and picks it up (`food_fell` +0.1, `holding_food` +0.2). shop-full: quiet siren, no serve (env 0.0); machine return 3.5, loops `u0 u5` on `switch_toggled` +0.3 (tp-rm-end/outputs/runs/bench__probe-a-*; shop-train status 00:47) | With final states no longer ending the episode, the machine's own positive cycles pay forever; same pattern as H3-H7 | None: the user chose B (keep the rule, 00:35) and dropped ARM-FM from the shop; results only | recorded, results only |

Detection note (H5): the loop shows only in greedy evaluation, below the 0.5 farming flag, so the cycle check alone misses
it. Compare greedy and sampled success per run; a big gap with a positive cycle in the machine marks a greedy loop.
