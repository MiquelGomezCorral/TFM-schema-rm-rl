# Step 1 has a previous valuation: every proposition is false

Date: 2026-11-12. Real environments and the real runtime, no provider call, no model call.

## What it shows

A labeling rule that remembers ("the key was held on the previous step and now it is not") reads the
previous valuation of the episode, `env.episode_memory["previous_valuation"]`. At the first step of an
episode that map was empty, so the plain rule `prev["has_key"] and ...` raised `KeyError: 'has_key'` on
step 1. The labeling code of both pipelines, the benchmark pages and the model prompts all had to dodge it
with a guard.

Now the first step starts from a map that holds every proposition as false, so the plain rule works and
means what it says (nothing was held before the episode began). One change in
`RewardMachineRuntime.evaluate_labeling` covers every path that evaluates generated labeling.

On the four benchmark environment pages, each executable "Truth conditions in code" row was loaded in the
labeling sandbox with a fresh runtime and compared with the reference labeler, step by step, on seeds 1
to 50 (one layout per seed):

| Page | Scenario | Layouts | Before: runs that raised `KeyError` at step 1 | After: errors / differences from the reference |
| --- | --- | --- | --- | --- |
| DoorKey | solving plan | 50 | 50 (`has_key`) | 0 / 0 over 841 steps |
| DoorKey | plan that drops the key | 48 (2 plans cannot drop) | 48 | 0 / 0 over 412 steps |
| DoorKey | random walk (200 steps) | 50 | 50 | 0 / 0 over 10,000 steps |
| UnlockPickup | solve / drop key / random walk | 50 each | 50 / 50 / 50 (`has_door_key`) | 0 / 0 over 940 / 367 / 10,000 steps |
| BlockedUnlockPickup | solve / drop key / random walk | 50 each | 50 / 50 / 50 (`has_door_key`) | 0 / 0 over 1,328 / 346 / 10,000 steps |
| KeyCorridor | solve / random walk | 50 each | 50 / 50 (`key_found`) | 0 / 0 over 2,113 / 10,000 steps |

Before, every run stops at step 1 (0 steps checked), so "before" shows the crash, not a wrong value. The
rule that fires on a drop, `key_lost`, was true on 48, 50 and 50 layouts of the drop-key scenarios and on
64, 83 and 56 random-walk layouts (DoorKey, UnlockPickup, BlockedUnlockPickup), all equal to the reference.

The two pilot machines replay to the same result before and after (`check/pilot-replay-*.json`): their own
labeling reads `bool(prev) and prev["has_key"]`, which stays false on a non-empty all-false map.

## Task, formula and machine

The two pilot cards have a generated machine; the other cards have none yet (the full suites are not
generated).

**`base-doorkey`**: "Use the key to open the door, then reach the goal." Clauses, all hard:

- `Precedence(has_key, door_open)`: `(((~door_open) U has_key) | (G (~door_open)))`
- `Precedence(door_open, at_goal)`: `(((~at_goal) U door_open) | (G (~at_goal)))`
- `Existence(at_goal)`: `(F at_goal)`

Machine: [interactive graph](graphs/base-doorkey.html), [SVG](graphs/base-doorkey.svg).

<details>
<summary>RM text (base-doorkey)</summary>

[`graphs/base-doorkey.rm.txt`](graphs/base-doorkey.rm.txt): 5 states, final `u4`, rejecting `u2`; the
main path (excerpt) is

```text
(u0, !at_goal&!door_open&has_key) -> u1
(u0, !at_goal&door_open&!has_key) -> u2
(u0, !at_goal&door_open&has_key) -> u3
(u0, at_goal&door_open&has_key) -> u4
(u1, !at_goal&door_open) -> u3
(u3, at_goal) -> u4
```

</details>

**`base-unlock-pickup`**: "Acquire the matching key, unlock the door, and pick up the designated box in
the other room." Clauses, all hard: `Precedence(has_door_key, door_open)`
(`(((~door_open) U has_door_key) | (G (~door_open)))`), `Precedence(door_open, target_picked_up)`
(`(((~target_picked_up) U door_open) | (G (~target_picked_up)))`) and `Existence(target_picked_up)`
(`(F target_picked_up)`). Machine: [interactive graph](graphs/base-unlock-pickup.html),
[RM text](graphs/base-unlock-pickup.rm.txt).

The other two scenarios' cards are `base-blocked-unlock-pickup` ("Pick up the blocking ball and the key, in
either order, unlock the door, and then pick up the box in the other room.") and `cx-sequence` ("Find the
key, pick it up, open the locked door, go into the room, and then pick up the ball."), on KeyCorridor.
They only drive the plans; no machine was generated for them.

## Evidence

- `check/pages-before.json`, `check/pages-after.json`: every row, scenario, step count and error sample.
  The rerun below reproduced the table's numbers on this head.
- Before is the runtime of commit `6149c47`; after is `a77709b`.

## Files

- `check/prev_false_pages.py`: reads the rows out of the four `environment-code.md` pages and runs them.
- `check/pages-before.json`, `check/pages-after.json`; `check/pilot-replay-before.json`,
  `check/pilot-replay-after.json` (the pilot cards' replay summaries, identical).
- `graphs/`: the two pilot machines (HTML, SVG, RM text), drawn with `render-rm --html`.

## Rerun

From the repository root, inside `RM_RL_env`:

```bash
git show 6149c47:app/src/arm_fm/runtime.py > "$TMPDIR/runtime_before.py"
PYTHONPATH=app python -W ignore docs/paper/step1-previous-valuation/check/prev_false_pages.py before "$TMPDIR/runtime_before.py"
PYTHONPATH=app python -W ignore docs/paper/step1-previous-valuation/check/prev_false_pages.py after
```

Each prints one block per page and writes `pages-<label>.json` next to the script. No LLM call. The script
reads the pages under `experiments/benchmark/envs/` as they are on this head (the plain form).

## Code

`RewardMachineRuntime.evaluate_labeling` in `app/src/arm_fm/runtime.py`; commit `1a25106`
(`feat(runtime): every proposition is false in the previous valuation at the first step`), merged into the
wave as `50a7a96`. The first-step sentences in `app/src/prompts/compiler-rm/labeling-*.system.md` and in the
four pages' `environment-code.md` changed with it; the rule is in `docs/decisions/arm-fm/rm-execution.md`.

## Gaps

- KeyCorridor's `target_door_open` is a description, not an expression, so it is not in the table.
- The ARM-FM generator is not told the first-step rule: its prompt and the Labeling API text of the pages
  do not mention `previous_valuation`. Its labeling can still use the guarded form.
- The replay covers only the two pilot machines, not a sweep over many bundles.
