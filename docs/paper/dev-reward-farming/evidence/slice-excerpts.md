# Slice excerpts behind the farming rows (copy)

Copied on 2026-11-23 from `.git/agent-memory/plans/testing-program-20261111/` (private plan notes). Each
block is verbatim except for paths: the repository prefix is cut, so paths are repository-relative, and a worktree
outside the repository is written `<tp-train-closed worktree>` or `<worktrees>`. `[...]` marks a cut line start.
Run folder names `seedN-<date>T<time>-<pid>` carry the start time in UTC.

## Hack audit: E9 and E10 (H3, H4)

From `slices/hack-audit/report.md`, lines 7, 146-150, 154, 160, 164-169, 178-179, 185-187, 191, 291.

ARM-FM already farms reward on `base-doorkey` and `tpl-precedence-1-goal`: zero judged/environment success, full-length episodes, mean RM return about 28–34.

All rows below have a physically repeatable path, rather than just an abstract graph cycle. Default reward on unlisted ARM-FM edges is zero. Source transitions and rewards are in the cited machine. “Observed” requires finished judge/trace evidence; other rows are risks only.
| Card | Repeatable physical behavior | Net RM reward per loop | Evidence | Version |
|---|---|---|---|---|
| base-doorkey | pick up key, drop it before opening door, repeat (u0 → u1 → u0) | +0.1 | **Observed**, E9; `experiments/benchmark/base/bundles/arm-fm/base-doorkey/reward_machine.txt:6`, `:9`, `:15` | R5; R5-key closes this pre-door loop |
| tpl-precedence-1-goal | after ball moved, pick up/drop key before opening (u1 → u2 → u1) | +0.15 | **Observed**, E10; `experiments/benchmark/templates/bundles/arm-fm/tpl-precedence-1-goal/reward_machine.txt:8`, `:11`, `:18` | R5; R5-key closes this pre-door loop |

The box fall/recovery graph cycles have positive rewards but are bounded by one or two scheduled falls, so they are **not** unbounded farming evidence. A siren/toggle graph self-loop is also schedule-bounded; most toggles clear `siren_ringing` before labeling. `cx-siren` ARM-FM's `switch_toggled & siren_ringing` bonus usually cannot fire: toggling clears the siren before the sample (`app/src/arm_fm/service_room.py:167`); a same-step scheduled re-ring is an exception. These should not be counted as the nine repeatable loops.

All following folders are under:
`<tp-train-closed worktree>/outputs/runs/`.
Each named seed folder contains `judge.json`; source numbers are its `mean_*` fields over 100 episodes. Values in one cell are seed 1 / 2 / 3; E8 has only seeds 1 / 2. RM return excludes environment reward; no-RM has no RM return. Counts of activation below were read from the already saved `agent-traces/ep*.json`, not produced by rerunning a judge.

| Evidence | Card / arm | Judged success | Env success | Mean length / limit | Mean RM return | Hard breaks / ep | Soft open / ep | Exact run parent and seed folders |
|---|---|---|---|---|---|---|---|---|
| E9 | `base-doorkey` / arm-fm | 0 / 0 / 0 | 0 / 0 / 0 | 640 / 640 / 640 / limit 640 | 28.24 / 30.56 / 29.87 | 0 / 0 / 0 | 0 / 0 / 0 | `bench__closed-base__base-doorkey__arm-fm__ppo`<br>`seed1-20261113T000731-3723560`; `seed2-20261113T003716-3739355`; `seed3-20261113T015153-3777197` |
| E10 | `tpl-precedence-1-goal` / arm-fm | 0 / 0 / 0 | 0 / 0 / 0 | 576 / 576 / 576 / limit 576 | 30.62 / 32.28 / 33.91 | 0.03 / 0.09 / 0.27 | 0 / 0 / 0 | `bench__closed-templates__tpl-precedence-1-goal__arm-fm__ppo`<br>`seed1-20261113T011054-3756123`; `seed2-20261113T011221-3756900`; `seed3-20261113T023255-3797969` |
| E16 | `base-doorkey` / farm | 0.99 / 0.98 / 1 | 0.99 / 0.98 / 1 | 23.12 / 29.39 / 16.93 / limit 640 | 1.257 / 1.225 / 1.3 | 0 / 0 / 0 | 0 / 0 / 0 | `bench__closed-base__base-doorkey__farm__ppo`<br>`seed1-20261113T021335-3787881`; `seed2-20261113T023514-3799352`; `seed3-20261113T030954-3815366` |
| E17 | `base-doorkey` / no-rm | 0.97 / 0.99 / 0.97 | 0.97 / 0.99 / 0.97 | 35.85 / 23.38 / 35.92 / limit 640 | n/a / n/a / n/a | 0 / 0 / 0 | 0 / 0 / 0 | `bench__closed-base__base-doorkey__no-rm__ppo`<br>`seed1-20261112T231002-3562843`; `seed2-20261112T231002-3562844`; `seed3-20261112T235722-3698492` |
| E18 | `tpl-precedence-1-goal` / no-rm | 0 / 0 / 0 | 0 / 0 / 0 | 576 / 576 / 576 / limit 576 | n/a / n/a / n/a | 0 / 0 / 0.01 | 0 / 0 / 0 | `bench__closed-templates__tpl-precedence-1-goal__no-rm__ppo`<br>`seed1-20261113T004529-3743879`; `seed2-20261113T005817-3750209`; `seed3-20261113T010912-3755204` |

[...] E9: the first two seeds average 282.35 and 305.56 key acquisitions per episode, with zero door openings; E10's first two average 206.29 and 214.43 key acquisitions with zero door openings. The large RM returns therefore reflect repeated pickup/drop, not delayed successful progress. E11–E15 run to their limits and score 0; their hard goals prevent an empty-pass interpretation even when individual conditionals remain untested. E16–E17 show the base DoorKey control arms reaching the goal with judged/environment success at least 0.97 and short mean lengths; the high-return ARM-FM failure is arm-specific. E18 shows ordinary no-RM failure on the precedence card; the ARM-FM repeat pickups and large positive returns distinguish farming from that baseline failure.

- This is a static audit plus saved-run inspection. No new rollouts, counterfactual policies, provider calls, training, or judging were authorized. Proposed versions and static reward loops need later live confirmation; only E1, E4/E5, E9 and E10 support observed missing work or reward farming.

## Closed-set training (H3, H4)

From `slices/train-closed/report.md`, lines 11, 15, 39, 41-42, 45, 51, 106-109, 122-125, 130.

- 02:45 early look (not final): `base-doorkey` ARM-FM seed 1 at 1.42M steps has greedy eval 0.0 at every one of its 142 eval points (sampled max 0.1); its training episodes end in RM state `u0` with `rm_path` `u0 u1 u0 u1 ...` for the full 640 steps (RM return ~30, env success in 7 of 2241 episodes): the agent loops between two RM states instead of solving, while the same card's no-RM arm reaches 0.98. Candidate for the Not learning list; to be confirmed on all 3 seeds.
- 04:38 base driver finished (9 runs; judged and aggregated to `outputs/results/closed-base/`). Base: no-RM 0.98, FARM 0.99, ARM-FM 0.00 in all 3 seeds (reward farming, see § 5).

Every closed-set ARM-FM machine, parsed from `reward_machine.txt`; a lap is a simple cycle of the transition graph, reward = the REWARD_FUNCTION entry of each edge fired. FARM machines are not listed: the FARM compiler rejects positive cycles (`reward_layer.py:140`).

| card | positive reward cycle | cycle (states, guard of the closing edge) and net reward per lap |
|---|---|---|
| tpl-precedence-1-goal | **yes** | u1 -> u2 -> u1 (key_lost) = +0.15 |
| base-doorkey | **yes** | u0 -> u1 -> u0 (key_lost) = +0.1 |

- **tpl-precedence-1-goal / arm-fm** greedy final [0.0, 0.0, 0.0]; judged success (rules, 100 unseen layouts) 0.00; goal=True
  - seed 1: **reward farming** last 300k steps: RM path cycles in 1.00 of episodes, episode success 0.00 (527 episodes), entropy 0.03, explained variance 0.76
  - seed 2: **reward farming** last 300k steps: RM path cycles in 1.00 of episodes, episode success 0.00 (527 episodes), entropy 0.05, explained variance 0.77
  - seed 3: **reward farming** last 300k steps: RM path cycles in 1.00 of episodes, episode success 0.00 (528 episodes), entropy 0.01, explained variance 0.85
- **base-doorkey / arm-fm** greedy final [0.0, 0.0, 0.0]; judged success (rules, 100 unseen layouts) 0.00; goal=True
  - seed 1: **reward farming** last 300k steps: RM path cycles in 1.00 of episodes, episode success 0.00 (466 episodes), entropy 0.03, explained variance 0.71
  - seed 2: **reward farming** last 300k steps: RM path cycles in 1.00 of episodes, episode success 0.00 (466 episodes), entropy 0.01, explained variance 0.74
  - seed 3: **reward farming** last 300k steps: RM path cycles in 1.00 of episodes, episode success 0.00 (467 episodes), entropy 0.01, explained variance 0.73

- **Reward farming** (rm_path cycles in 100% of last-300k-step episodes, entropy 0.01-0.05, explained variance 0.7-0.85): `base-doorkey` ARM-FM and `tpl-precedence-1-goal` ARM-FM (3 seeds each). Both machines have a positive reward cycle (section 5). `tpl-chain-response-1-nogoal` ARM-FM also has a positive cycle (+0.1) but its greedy and sampled success is 1.00 (not farming in practice).

## Closed-set table (H3, H4)

From `slices/train-closed/tables.md`, lines 1-2, 16-17, 23-25.

| card | arm | env | bundle | greedy final s1/s2/s3 | sampled final s1/s2/s3 | step greedy>=0.8 | step sampled>=0.8 | rule breaks hard/soft per ep (s1/s2/s3) | wall min | mean greedy / sampled / judged |
|---|---|---|---|---|---|---|---|---|---|---|
| tpl-precedence-1-goal | no-rm | BlockedUnlockPickup | n/a (env reward) | 0.00/0.00/0.00 | 0.00/0.00/0.00 | never/never/never | never/never/never | 0.00-0.00/0.00-0.00/0.01-0.00 | 64/63/60 | 0.00 / 0.00 / 0.00 |
| tpl-precedence-1-goal | arm-fm | BlockedUnlockPickup | repaired (small model) | 0.00/0.00/0.00 | 0.00/0.00/0.00 | never/never/never | never/never/never | 0.03-0.00/0.09-0.00/0.27-0.00 | 80/80/89 | 0.00 / 0.00 / 0.00 |
| base-doorkey | no-rm | DoorKey-8x8 | n/a (env reward) | 0.98/0.98/0.98 | 1.00/1.00/1.00 | 573k/881k/664k | 451k/721k/541k | 0.00-0.00/0.00-0.00/0.00-0.00 | 47/57/40 | 0.98 / 1.00 / 0.98 |
| base-doorkey | arm-fm | DoorKey-8x8 | complete | 0.00/0.00/0.00 | 0.00/0.00/0.00 | never/never/never | never/never/never | 0.00-0.00/0.00-0.00/0.00-0.00 | 104/96/89 | 0.00 / 0.00 / 0.00 |
| base-doorkey | farm | DoorKey-8x8 | complete | 0.99/0.95/0.98 | 1.00/1.00/1.00 | 221k/254k/201k | 143k/180k/131k | 0.00-0.00/0.00-0.00/0.00-0.00 | 22/35/28 | 0.97 / 1.00 / 0.99 |

## Train-all phase 1 (H5, H6, H7)

From `slices/train-all/report.md`, lines 51, 53, 70, 71, 85.

- Tools (all in `S/train-all/`): `analyze2.py <worktree>` (table, flags `degenerate` for final mean length < 5 on an RM arm and `reward farming` for >= 0.5 cycling in the last 300k steps), `cycles2.py` -> `cycles.md` (static positive reward cycles of the 20 ARM-FM machines; 13 of 20 have one), `judge_finished.sh`, `cmp_dups.py`, `status.py`, `watch.sh`, `scheduler.sh`.
- `tpl-chain-response-1-goal` ARM-FM: training episodes exit in 99.99% of the last 1.2M steps (mean length 24.5, final RM state u3) but 46% of them lap the positive cycle `u1 -> u2 -> u1` (holding_box, +0.3 per lap, `cycles.md`) before exiting; the **greedy** policy loops for the full 200 steps (final eval length 200, judged 0.00). The greedy test is what the judge sees, so this card reads as a failure although the sampled policy solves it. Candidate for the coordinator: exploit of the positive cycle shows up only in greedy mode. Below the 0.5 farming flag, not escalated.
- 13:2x **ALARM sent**: reward farming (RM path cycles in 98-100% of last-300k episodes, greedy 0.00, episodes run to the time limit) in ARM-FM `tpl-existence-two-1-nogoal` (DoorKey, 88 min) and `tpl-existence-two-1-goal` (UnlockPickup, 51 min); static positive cycle u0->u1->u0 (key_lost) +0.1/+0.2 in cycles.md; no-RM solves DoorKey.
- 13:2x coordinator/user rule (11:56): reward-farming machines stay as results, no fix, no guarded variant; keep training; keep flagging farming in tables.md (cycle share, RM return, greedy vs sampled); **do not escalate further farming cases, list them here** (coordinator adds them to the hack register). Farming list so far: tpl-existence-two-1-nogoal ARM-FM (cycles 0.98, length 640), tpl-existence-two-1-goal ARM-FM (cycles 1.00, length 288).
- ARM-FM finished (13 of 18 incl. `tpl-absence-1-nogoal`; 3 KeyCorridor ARM-FM + probe still training): greedy >= 0.8 on 5 (`tpl-precedence-1-nogoal`, `cx-siren`, `cx-box`, `base-unlock-pickup`, `base-blocked-unlock-pickup`); sampled-only solve on 1 (`tpl-chain-response-1-goal`, greedy 0.00 / sampled 1.00); reward farming on 7 (`tpl-existence-two-1-nogoal`, `tpl-existence-two-1-goal`, `tpl-responded-existence-1-nogoal`, `tpl-response-1-nogoal`, `tpl-not-co-existence-1-goal`, `cx-goal-one-rule`, `cx-goal-many-rules`); machine too simple (episodes cannot start) on 1 (`tpl-absence-1-nogoal`, judged 0.00, raw 0.00); plain 0/0 on 1 (`tpl-existence-1-nogoal`, no farming flag).

## Train-all static cycles (H5, H6, H7, H9)

From `slices/train-all/cycles.md`, lines 1-2, 8-11.

| card | positive reward cycle | cycle (states, guard of the closing edge) and net reward per lap |
|---|---|---|
| tpl-chain-response-1-goal | **yes** | u1 -> u2 -> u1 (holding_box) = +0.3 |
| tpl-existence-two-1-nogoal | **yes** | u0 -> u1 -> u0 (key_lost) = +0.1 |
| tpl-existence-two-1-goal | **yes** | u0 -> u1 -> u0 (key_lost) = +0.2 |
| tpl-responded-existence-1-nogoal | **yes** | u0 -> u1 -> u0 (key_lost) = +0.2 |

## Train-all table, seed 1 and the later seeds 2-3 (H5, H6, H7, H9)

From `slices/train-all/tables.md`, lines 103-104, 111-118, 242-245, 376-377, 380-381, 388-389.

| card | arm | env | bundle | labeling | generation retry | greedy final | sampled final | step greedy>=0.8 | step sampled>=0.8 | rule breaks hard-soft per ep | final eval length | wall min | judged / raw / non-empty | untested rules | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tpl-chain-response-1-goal | no-rm | ServiceRoom | n/a (env reward) | – | – | 1.00 | 1.00 | 164k | 123k | 0.17-0.00 | 15.3 | 19 | 0.83 / 0.83 / 0.83 | – | code f2ed884 |
| tpl-chain-response-1-goal | arm-fm | ServiceRoom | complete | original | – | 0.00 | 1.00 | 82k | 41k | 0.00-0.00 | 200.0 | 33 | 0.00 / 0.00 / 0.00 | (F at_exit) (activated 0.00); (G (at_exit -> (F holding_box))) (activated 0.00) | code f2ed884 |
| tpl-existence-two-1-nogoal | no-rm | DoorKey-8x8 | n/a (env reward) | – | – | 0.98 | 1.00 | 573k | 451k | 0.00-0.00 | 29.8 | 33 | 0.97 / 0.97 / 0.97 | – | code f2ed884 |
| tpl-existence-two-1-nogoal | arm-fm | DoorKey-8x8 | complete | original | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 640.0 | 88 | 0.97 / 0.97 / 0.97 | – | reward farming: RM path cycles in 0.98 of last-300k episodes, final-eval RM return 29.6, greedy 0.00 / sampled 0.00; LF review: RM (LF ok); code f2ed884 |
| tpl-existence-two-1-goal | no-rm | UnlockPickup | n/a (env reward) | – | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 288.0 | 37 | 0.00 / 0.00 / 0.00 | (F (has_door_key & (X (F has_door_key)))) (activated 0.00); (F target_picked_up) (activated 0.00) | code f2ed884 |
| tpl-existence-two-1-goal | arm-fm | UnlockPickup | complete | original | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 288.0 | 51 | 0.00 / 0.00 / 0.00 | (F target_picked_up) (activated 0.00) | reward farming: RM path cycles in 1.00 of last-300k episodes, final-eval RM return 28.1, greedy 0.00 / sampled 0.00; LF review: RM (LF ok); code f2ed884 |
| tpl-responded-existence-1-nogoal | no-rm | UnlockPickup | n/a (env reward) | – | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 288.0 | 36 | 1.00 / 1.00 / 0.00 | ((F has_door_key) -> (F door_open)) (activated 0.00) | code f2ed884 |
| tpl-responded-existence-1-nogoal | arm-fm | UnlockPickup | complete | original | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 288.0 | 49 | 0.01 / 0.01 / 0.00 | – | reward farming: RM path cycles in 1.00 of last-300k episodes, final-eval RM return 26.5, greedy 0.00 / sampled 0.00; LF review: RM (LF ok); code f2ed884 |

### Seeds 2 and 3 (phase 4, PPO s07, 1.5M steps); seed-1 rows are above

| card | arm | env | bundle | labeling | generation retry | greedy final | sampled final | step greedy>=0.8 | step sampled>=0.8 | rule breaks hard-soft per ep | final eval length | wall min | judged / raw / non-empty | untested rules | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tpl-existence-two-1-goal (seed 2) | arm-fm | UnlockPickup |  | – | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 288.0 | 70 | 0.00 / 0.00 / 0.00 | (F target_picked_up) (activated 0.00) | reward farming: RM path cycles in 1.00 of last-300k episodes, final-eval RM return 27.3, greedy 0.00 / sampled 0.00; code b332ecf |
| tpl-existence-two-1-goal (seed 3) | arm-fm | UnlockPickup |  | – | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 288.0 | 85 | 0.00 / 0.00 / 0.00 | (F target_picked_up) (activated 0.00) | reward farming: RM path cycles in 1.00 of last-300k episodes, final-eval RM return 28.4, greedy 0.00 / sampled 0.00; code b332ecf |
| tpl-existence-two-1-nogoal (seed 2) | arm-fm | DoorKey-8x8 |  | – | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 640.0 | 122 | 0.39 / 0.39 / 0.39 | (F (has_key & (X (F has_key)))) (activated 0.39) | reward farming: RM path cycles in 0.81 of last-300k episodes, final-eval RM return 18.1, greedy 0.00 / sampled 0.00; code b332ecf |
| tpl-existence-two-1-nogoal (seed 3) | arm-fm | DoorKey-8x8 |  | – | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 640.0 | 142 | 0.93 / 0.93 / 0.93 | – | reward farming: RM path cycles in 1.00 of last-300k episodes, final-eval RM return 29.0, greedy 0.00 / sampled 0.00; code b332ecf |
| tpl-responded-existence-1-nogoal (seed 2) | arm-fm | UnlockPickup |  | – | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 288.0 | 81 | 0.00 / 0.00 / 0.00 | – | reward farming: RM path cycles in 1.00 of last-300k episodes, final-eval RM return 28.4, greedy 0.00 / sampled 0.00; code b332ecf |
| tpl-responded-existence-1-nogoal (seed 3) | arm-fm | UnlockPickup |  | – | – | 0.00 | 0.00 | never | never | 0.00-0.00 | 288.0 | 100 | 0.04 / 0.04 / 0.00 | – | reward farming: RM path cycles in 1.00 of last-300k episodes, final-eval RM return 27.6, greedy 0.00 / sampled 0.00; code b332ecf |

## Re-judge on main 0a388e8: RM returns and the cards' NL task and LTL (H3-H7, H9)

From `slices/rejudge/tables.md`, lines 13-14, 51-53, 72-74, 95, 99, 101, 105, 154-155, 157, 169, 175-176, 179, 182.

| suite | card | arm | seed | env | run | judge file | judged | raw judged | non-empty | untested rules (<50% activated) | env success (judge test) | greedy / sampled (final eval) | env return total (+ / −) | RM return total (+ / −) | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| closed-templates | tpl-precedence-1-goal | arm-fm | 1 | BlockedUnlockPickup | finished 1503k | re-judged (v1 kept) | 0.00 | 0.00 | 0.00 | Existence(target_picked_up) 0.00 | 0.00 | 0.00 / 0.00 | 0.00 (+0.00 / 0.00) | 30.62 (+30.62 / 0.00) | positive cycle in machine; farming: RM path laps in 1.00 of last-300k episodes |
| closed-templates | tpl-precedence-1-goal | arm-fm | 2 | BlockedUnlockPickup | finished 1503k | re-judged (v1 kept) | 0.00 | 0.00 | 0.00 | Existence(target_picked_up) 0.00 | 0.00 | 0.00 / 0.00 | 0.00 (+0.00 / 0.00) | 32.28 (+32.28 / 0.00) | positive cycle in machine; farming: RM path laps in 1.00 of last-300k episodes |
| closed-templates | tpl-precedence-1-goal | arm-fm | 3 | BlockedUnlockPickup | finished 1503k | re-judged (v1 kept) | 0.00 | 0.00 | 0.00 | Existence(target_picked_up) 0.00 | 0.00 | 0.00 / 0.00 | 0.00 (+0.00 / 0.00) | 33.91 (+33.91 / 0.00) | positive cycle in machine; farming: RM path laps in 1.00 of last-300k episodes |
| closed-base | base-doorkey | arm-fm | 1 | DoorKey-8x8 | finished 1503k | re-judged (v1 kept) | 0.00 | 0.00 | 0.00 | Precedence(has_key, door_open) 0.00; Precedence(door_open, at_goal) 0.00; Existence(at_goal) 0.00 | 0.00 | 0.00 / 0.00 | 0.00 (+0.00 / 0.00) | 28.23 (+28.23 / 0.00) | positive cycle in machine; farming: RM path laps in 1.00 of last-300k episodes |
| closed-base | base-doorkey | arm-fm | 2 | DoorKey-8x8 | finished 1503k | re-judged (v1 kept) | 0.00 | 0.00 | 0.00 | Precedence(has_key, door_open) 0.00; Precedence(door_open, at_goal) 0.00; Existence(at_goal) 0.00 | 0.00 | 0.00 / 0.00 | 0.00 (+0.00 / 0.00) | 30.56 (+30.56 / 0.00) | positive cycle in machine; farming: RM path laps in 1.00 of last-300k episodes |
| closed-base | base-doorkey | arm-fm | 3 | DoorKey-8x8 | finished 1503k | re-judged (v1 kept) | 0.00 | 0.00 | 0.00 | Precedence(has_key, door_open) 0.00; Precedence(door_open, at_goal) 0.00; Existence(at_goal) 0.00 | 0.00 | 0.00 / 0.00 | 0.00 (+0.00 / 0.00) | 29.87 (+29.87 / 0.00) | positive cycle in machine; farming: RM path laps in 1.00 of last-300k episodes |
| ta1-tpl-fast | tpl-chain-response-1-goal | arm-fm | 1 | ServiceRoom | finished 1503k | re-judged (v1 kept) | 0.00 | 0.00 | 0.00 | Existence(at_exit) 0.00; Response(at_exit, holding_box) 0.00 | 0.00 | 0.00 / 1.00 | 0.00 (+0.00 / 0.00) | 0.65 (+0.65 / 0.00) | positive cycle in machine |
| ta1-tpl-fast | tpl-existence-two-1-goal | arm-fm | 1 | UnlockPickup | finished 1503k | judged new | 0.00 | 0.00 | 0.00 | Existence(target_picked_up) 0.00 | 0.00 | 0.00 / 0.00 | 0.00 (+0.00 / 0.00) | 27.85 (+27.85 / 0.00) | positive cycle in machine; farming: RM path laps in 1.00 of last-300k episodes |
| ta1-tpl-fast | tpl-existence-two-1-nogoal | arm-fm | 1 | DoorKey-8x8 | finished 1503k | judged new | 0.97 | 0.97 | 0.97 | none | 0.00 | 0.00 / 0.00 | 0.00 (+0.00 / 0.00) | 30.89 (+30.89 / 0.00) | positive cycle in machine; farming: RM path laps in 0.98 of last-300k episodes |
| ta1-tpl-fast | tpl-responded-existence-1-nogoal | arm-fm | 1 | UnlockPickup | finished 1503k | judged new | 0.01 | 0.01 | 0.00 | none | 0.00 | 0.00 / 0.00 | 0.00 (+0.00 / 0.00) | 28.17 (+28.17 / 0.00) | positive cycle in machine; farming: RM path laps in 1.00 of last-300k episodes |

| card | goal | NL task | LTLf (each declared rule) |
|---|---|---|---|
| base-doorkey | goal | Use the key to open the door, then reach the goal. | `Precedence(has_key, door_open)` hard: `(((~door_open) U has_key) | (G (~door_open)))`<br>`Precedence(door_open, at_goal)` hard: `(((~at_goal) U door_open) | (G (~at_goal)))`<br>`Existence(at_goal)` hard: `(F at_goal)` |
| tpl-chain-response-1-goal | goal | Carry the box to the exit. Whenever the box falls, pick it up again on your very next move. | `ChainResponse(box_fell, holding_box)` hard: `(G (box_fell -> (X holding_box)))`<br>`Existence(at_exit)` hard: `(F at_exit)`<br>`Response(at_exit, holding_box)` hard: `(G (at_exit -> (F holding_box)))` |
| tpl-existence-two-1-goal | goal | Be holding the key on at least two different moves, then pick up the box in the other room. | `ExistenceTwo(has_door_key)` hard: `(F (has_door_key & (X (F has_door_key))))`<br>`Existence(target_picked_up)` hard: `(F target_picked_up)` |
| tpl-existence-two-1-nogoal | no goal | Be holding the key on at least two different moves. | `ExistenceTwo(has_key)` hard: `(F (has_key & (X (F has_key))))` |
| tpl-precedence-1-goal | goal | Move the ball away from the door before you take the key, then open the door and pick up the box. | `Precedence(blocker_moved, has_door_key)` hard: `(((~has_door_key) U blocker_moved) | (G (~has_door_key)))`<br>`Existence(target_picked_up)` hard: `(F target_picked_up)` |
| tpl-responded-existence-1-nogoal | no goal | If you pick up the key, you must also open the door. | `RespondedExistence(has_door_key, door_open)` hard: `((F has_door_key) -> (F door_open))` |

## Shop probe with final states not ending the episode (H12)

From `slices/shop-train/report.md`, lines 251-277.

The question (the user's Q1): if no RM state ends the episode (option A, suite key `rm_ends_episode: false`), does
ARM-FM learn to serve? Two runs, ARM-FM **shop-serve** and **shop-full**, v9 tasks file, seed 1, `reward_source: rm`,
`eval_frequency: 50000`, 3M steps planned. They ran from the worktree `tp-rm-end` (its code and its `outputs/runs/`),
because the key exists only there (uncommitted changes to `run_suite.py`, `dqn.py`, `environments.py`, `config.py`;
**I edited nothing there**). Runs files: `runs/probe-a-serve.json`, `runs/probe-a-full.json` (absolute bundle paths from
main; the saved `config.yaml` shows `rm_ends_episode: false`, `agent_view_size: 9`, `reward_source: rm`). Started 23:27
(serve) and 23:36 (full). **Stopped 00:46 by PID** after the user's decisions: Q1 = B (today's rule, `rm_ends_episode`
is not merged) and "stop trying with ARM-FM, just keep FARM". The run folders keep what they wrote
(`tp-rm-end/outputs/runs/bench__probe-a-{serve,full}__*__arm-fm__ppo/`: `eval.csv`, `train.csv`, `episodes.csv`).
`agent.pt` is written once at the end, so **it does not exist: no greedy or sampled judge, no serves-per-episode probe**.

| run (ARM-FM, final states not ending the episode) | steps reached | greedy machine return first above 0.0 | greedy machine return later | sampled machine return | greedy / sampled env return | last 200 training episodes |
|---|---|---|---|---|---|---|
| shop-serve | 2,400,256 | 102,400 (0.10) | 0.83 from 352k to the end | first above 0 at 53,248; best 6.14, last 5.75 | -9.5 in every eval (idle) / best -9.4 | env -9.5, machine 5.9, RM path `u3 u5 u3 u5 ...` for 600 steps |
| shop-full | 2,158,592 | 151,552 (0.28); idle is -29.65 | 3.6 from 352k (one dip to -28.8 at 1.25M) | first above 0 at 102,400 (2.84); best 3.60 | first above -9.5 at 102,400 (-8.55), above -1 at 151,552 (-0.95), 0.0 later / 0.0 | env 0.0, machine 3.5, RM path `u0 u5 u0 u5 ...` |

What it shows:

- **No serve was learned.** Env return pays +1 per serve; it never rises above the idle -9.5 (shop-serve) or above 0.0, a
  quiet siren with no serve (shop-full), in any greedy or sampled eval. At most one serve in one 10-episode sampled eval
  (shop-serve, -9.4). Serves per episode could not be probed without `agent.pt`.
- **The machine return does go above idle, by a loop.** shop-serve: the RM path alternates `u3 -> u5 -> u3` (the machine pays
  `food_fell` +0.1 and `holding_food` +0.2 per round trip), 5.9 machine return and -9.5 env return: the policy farms
  the loop instead of serving (`shop-serve/reward_machine.txt`). shop-full: the path alternates `u0 -> u5 -> u0` (`siren_ringing`
  then `switch_toggled` +0.3), so it solves the siren part, exactly what the siren card taught, and stops there.
- **Answer to Q1 for these two machines, 2.2M to 2.4M steps:** letting the episode run on does not make ARM-FM learn to
  serve; it learns the paid sub-behaviour (siren, or the drop-and-pick-up loop). Not judged, not run to 3M, one seed.

## Shop probe stopped (H12)

From `overnight-log.md`, line 371.

- 00:47 probe for Q1 stopped 00:46 (by PID; outputs kept in tp-rm-end/outputs/runs/bench__probe-a-*; no agent.pt). Partial: under rm_ends_episode false ARM-FM never serves; it farms machine loops (serve: drop/pick dish, machine 5.9, env -9.5; full: siren toggle +0.3, machine 3.5, env 0.0). Registered as H12. Grid: g03 no-RM Shop 5M siren 1.00/1.00; g04 done 00:45, judging; g07-g10 running.
