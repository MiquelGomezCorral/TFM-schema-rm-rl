# Card review, delta pass on the card fixes (Opus 5.5, 2026-11-20)

Copied from the reviewer's text return in the coordinator's session log; the reviewer wrote no file of its own.
It reviews the card-fix worktree `tp-card-fixes` (main `d4e09fe` plus the loop-2 card edits), before the
second card-fix round. Its checks are in `delta-checks/` (`sweep.out`, `tb-*.out`).

**What this change does:** It applies the loop 2 stated-order card edits plus the card-only fixes from the baseline review. That covers 27 files under `experiments/benchmark/` in `tp-card-fixes`, on main `d4e09fe`, not committed. Five suites now train on 3 seeds. Seven idle-passable or weak cards stop training and three forcing cards start. Accepted answers that drop a stated clause are removed. Two new hard service-room cards are added.

## Must fix

1. **Two base cards still accept the goal alone and reject the answer the rules ask for** (P1, `base/tasks.json:70`, `:71-77`, `:174`; `pilot/tasks.json:130`, `:134`; `smoke/tasks.json:70`, `:71`; in-scope)
   - **What this is:** `base-unlock-pickup` ("Acquire the matching key, unlock the door, and pick up the designated box") and `base-key-corridor` keep both orders in `forced`. `forced` marks clauses that scoring treats as optional extras.
   - **Problem:** In the scorer (`app/src/benchmark/rm_facts.py:139-141`), "exact" means `expect` minus the `forced` clauses. So `Existence(box)` alone scores exact even though it drops two stated steps. This delta removed that same answer from `tpl-existence-2-goal`. Meanwhile one `Existence` per stated step scores mismatch, and that is what the generator rules ask for an unordered list. `base-unlock-pickup` also keeps the `Response` chain as an accepted answer; `Response` is not a step form, and the same chain was removed from `base-doorkey`. The delta copied all of this onto the pilot and smoke copies, which before required both orders. The `base-key-corridor` note says `expect` names the key step, but that clause is in `forced`, so an answer can drop it.
   - **Fix:** The user picks the reading. If the list states no order: `expect` becomes `E(has_door_key)`, `E(door_open)`, `E(target_picked_up)` (corridor: `has_matching_key`, `target_door_open`, `target_picked_up`), with no `forced` and no `also_ok`, in all three copies. If it does state an order: drop `forced` and the `Response` answer, as on `base-doorkey`.
   - **If we skip it:** A FARM machine that drops two steps scores right. A correct per-step machine scores wrong, and the "no training on wrong machines" gate holds back a trained final-run card.

## Should fix

2. **The `until` fix is half done: `NotCoExistence` accepts exactly the runs of the removed `Absence`** (P2, `templates/tasks.json:1260`, `:1344`, `templates/README.md:35-38`, in-scope)
   - **What this is:** `tpl-precedence-2-goal` and `-3-goal` lost `Absence(key_lost)` + goal because it reads "until the door is open" as "never".
   - **Problem:** The goal needs the door open, and `key_lost` fires only with the door closed. So `NotCoExistence(key_lost, door_open)` + goal bans the same open-shut-drop run that `Absence` bans. The README draws a difference that does not exist on goal cards.
   - **Fix:** Set `also_ok: []` on both cards and drop the README's `NotCoExistence` example. The alternative is to restore `Absence` on both (S2 rule); either way, treat the two answers the same.
   - **If we skip it:** Two answers with the same meaning get opposite scores.

3. **A `cx-sequence` paraphrase no longer matches `expect`** (P2, `complex/tasks.json:58`, in-scope)
   - **What this is:** Loop 2 made the four orders required.
   - **Problem:** Paraphrase 3 ("Find the key, take it, open the locked door, walk into the room behind it, and pick up the ball") has no order word, so it states none of the four orders it is now scored for.
   - **Fix:** "..., walk into the room behind it, and then pick up the ball."
   - **If we skip it:** A rule-following `~p3` machine scores mismatch on a trained card.

4. **The new `tpl-responded-existence-4-goal` misses the packet's "clean pay order" bar** (P2, `templates/tasks.json:1933`, in-scope, waits on fix 3)
   - **Problem:** It fails "started must pay more than not started" (class A, like `cx-siren`). The gate will block it. It replaces a card that was also flagged, so the trained count of flagged answers stays at 7.
   - **Fix:** None at card level; it waits on the user's pay-order decision.
   - **If we skip it:** One more trained card waits on the gate.

5. **Forced-start now trains 3 seeds against a recorded user decision** (P2, `forced-start/runs.yaml:11`, `docs/decisions/benchmark/thesis-benchmark.md:153-157`, `:332`, unclear)
   - **Problem:** The record says only seed 1 of `tpl-response-1-nogoal-forced` trains (user, 2026-11-14), and that forced cards keep their originals' train flags. Now the original is `train: false` and the copy trains on 3 seeds. The later 3-seed rule probably wins, but this is a protected-invariant conflict.
   - **Fix:** The root asks the user and updates the record.
   - **If we skip it:** The record and the run disagree at the freeze.

## Nice to have

6. **The new box card tests the pickup, not the count** (P3, `templates/tasks.json:493`)
   - The box falls 2-6 steps after a pickup. So any pickup that is not dropped at once already holds it on two moves. `tpl-existence-two-1-nogoal` has the same weakness: a key not dropped at once is held two moves.
   - It is still better than the old card, because the detour to the box is a real choice.
   - A real hard count needs an event, for example a hard copy of `tpl-existence-two-soft-1-nogoal` ("kill at least two zombies"). That is test design.
7. **The siren-room RespondedExistence cards behave as `Existence(switch)`.** The siren always rings by step 4 and the switch cannot be reached before it. They test the obligation and the template the generator writes, not the condition.
8. **Stale text.**
   - `base/README.md:26` still says the `Response` chain "stays `also_ok`", and the next paragraph contradicts it.
   - `REPRODUCE.md:178` says the runs.yaml files carry seed 1.
   - `forcing/README.md:90`: `check_forcing.py` has no flag to set its -5 time-limit penalty to 0, so the new table cannot be reproduced with the given command.

## Problem-solution check

Every packet item is applied as asked, except the base-unlock-pickup scoring (1) and the `until` answers (2).

On the two new cards:
- **NL task matches `expect`:** yes, both. No accepted answer is missing: `Response` (a flip after every ring; half the episodes ring twice), `Existence(switch)` (drops the "if" rule) and `Existence(holding_box)` (weaker) are rightly left out.
- **Forcing:** idle is open at the end on seeds 1-3, and the shortcut breaks the rule.
- **Plans and pays:** they match the card. Box card: solve 13 > pickup-drop 2 > exit-only 1 > idle 0. Siren card: solve 11 > rush 0 > idle -1.

Train flags are on the right cards. README and `runs.yaml` counts are right: templates 79 cards, 26 trained (11 hard + 15 soft), 234 runs; base 36, complex 45, forced-start 9, forcing 24, box-carry 27, ablation 54.

## Checks (head `d4e09fe` plus the working tree)

| Check | Result | Coder's claim |
|---|---|---|
| Trace bank, all 9 suites | templates 79 cards 421/421; base 8/8, box-carry 105/105, complex 29/29, forced-start 7/7, forcing 33/33, pilot 4/4, shop 72/72, smoke 6/6 | same |
| `sweep.py`, `CARD_ROOT=tp-card-fixes` | 131 answers, 0 errors, 26 pay-order flags | 149 → 131, 25 → 26 |
| Row-by-row against the coder's `after/sweep.jsonl` | identical (summaries and trace pays) | |
| Trained final answers with a pay-order flag | 7 (list below) | |
| `run-suite --dry-run` on the 7 final suites | counts above; templates: 108 runs no-data (18 trained cards have no bundles); ablation: 21 no-data (18 from `lanes-rules` without ablation bundles, 3 for a variant that changes nothing) | |
| `unittest tests.test_arm_fm tests.test_web` | 65 OK | |

The 7 flagged trained answers are `cx-siren`, `tpl-absence-1-goal` also_ok#0, `tpl-not-co-existence-1-goal`, `tpl-responded-existence-4-goal`, and the soft goal cards for Precedence, RespondedExistence and NotCoExistence.

## Coverage matrix (49 trained cards)

| Template | Hard, goal | Hard, no goal | Soft, goal | Soft, no goal |
|---|---|---|---|---|
| Existence | weak, level forces it (`-1-goal`) | OK | not judged | OK |
| ExistenceTwo | **new** `-4-goal`: pickup real, count free | count free | not judged | OK (Lanes, event count) |
| Absence | OK | `lanes-guard` OK | not judged | counted once per episode |
| Response | OK (`cx-siren`, `cx-box`) | OK (KeyGift, shop) | not judged | OK |
| Precedence | OK | **gap** | not judged | OK |
| ChainResponse | OK (carry) | OK (carry) | not judged | OK |
| RespondedExistence | **new** `-4-goal` OK (pay-order flag) | **now trained** `-2-nogoal` OK | not judged | OK |
| NotCoExistence | OK (pay-order flag) | **gap** | not judged | OK |

The 32 cells split like this:

| Status | Cells | Change from baseline |
|---|---|---|
| OK | 18 | +2 (both RespondedExistence hard cells) |
| Soft rule not judged (goal cards) | 8 | |
| Weak or partly weak | 3 | ExistenceTwo hard goal improved but still weak on the count |
| Gap | 2 | was 4 |
| Counted once per episode | 1 | |

## Groups

`groups-v2.json` holds 10 groups, same schema; the 9 final-run groups cover the 49 trained cards once each:
- Base sequences: 5
- Hard template + goal on the key levels: 5
- Service room, hard goal + rule: 7, with both new cards
- Hard no-goal forcing worlds: 7, with `tpl-responded-existence-2-nogoal`
- Forced start: 1
- Shop: 6
- Soft rule + goal: 10
- Soft only: 8
- Ablation: 3, same cards as other groups

The tenth, "stopped training", lists the 7 dropped cards. The "Then after an if rule" question now touches only generation cards.

## What blocks the freeze

1. **Card fixes:** finding 1 (needs the reading decided), then 2 and 3.
2. **Pay-order gate:** 7 trained answers wait on the user (land the check change, or write a class-A exemption).
3. **Soft rule next to a goal is never judged:** 10 trained cards; needs a pass bar from the user.
4. **KeyCorridorS6R3 never learned (0/71):** `base-key-corridor` and `cx-sequence` still train there and wait on the learnability probe.
5. **ARM-FM on the 15 soft cards:** user decision.
6. **Bundles:** 18 trained template cards have none, plus the `lanes-rules` ablation. The forcing bundles are stale. All bundles get regenerated at the freeze.
7. **Shop settings:** promise cost and embeddings are untested, and levels 3-5 have no learning result.
8. **Records:** the root updates `thesis-benchmark.md` (forced flags and seeds, carry flags, end judgment; finding 5).
9. **Regression set:** still written nowhere in the repository.

**Verdict:** Request changes, fix 1 first, then 2 and 3.

**Not checked:** `pre-commit` (it can rewrite files), the full unit suite, any training or LLM generation. I reasoned that `NotCoExistence` and `Absence` accept the same runs from the level facts; I did not compare their machines state by state.

**Roster:** direct mode, one reviewer (claude, claude-opus-5-5), no delegation and no subscription swaps. Live gaps: learnability of both new cards (the siren card has `cx-siren`'s rush-trap pay shape) and the generator's actual output on the base cards.
