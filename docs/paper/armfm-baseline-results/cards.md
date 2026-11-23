# Cards of the ARM-FM baseline

Written by `build.py`; do not edit. Per card: the task in plain words (`tasks.json`), the card's expected
clauses with their LTLf, any other accepted reading, and the FARM and ARM-FM machines its runs trained or
were judged on (`reward_machine.txt`, verbatim). No-RM runs use no machine.

## armfm-doorkey-5x5

**Task:** Use the key to open the door, then reach the goal.

**World:** `MiniGrid-DoorKey-5x5-v0`, a new map each episode.

**Results:** test 1.

**LTL** (expected clauses):
- Precedence(has_key, door_open) hard: `(((~door_open) U has_key) | (G (~door_open)))`
- Precedence(door_open, at_goal) hard: `(((~at_goal) U door_open) | (G (~at_goal)))`
- Existence(at_goal) hard: `(F at_goal)`

**FARM machine** (`experiments/benchmark/armfm-paper/bundles/farm/armfm-doorkey-5x5/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u2
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !at_goal&!door_open&has_key) -> u1
(u0, !at_goal&door_open&!has_key) -> u2
(u0, !at_goal&door_open&has_key) -> u3
(u0, at_goal&!door_open&!has_key) -> u2
(u0, at_goal&!door_open&has_key) -> u2
(u0, at_goal&door_open&!has_key) -> u2
(u0, at_goal&door_open&has_key) -> u4
(u1, !at_goal&door_open) -> u3
(u1, at_goal&!door_open) -> u2
(u1, at_goal&door_open) -> u4
(u3, at_goal) -> u4
REWARD_FUNCTION:
(u0, !at_goal&!door_open&has_key, u1) -> 1
(u0, !at_goal&door_open&!has_key, u2) -> -10
(u0, !at_goal&door_open&has_key, u3) -> 2
(u0, at_goal&!door_open&!has_key, u2) -> -10
(u0, at_goal&!door_open&has_key, u2) -> -10
(u0, at_goal&door_open&!has_key, u2) -> -10
(u0, at_goal&door_open&has_key, u4) -> 13
(u1, !at_goal&door_open, u3) -> 1
(u1, at_goal&!door_open, u2) -> -11
(u1, at_goal&door_open, u4) -> 12
(u3, at_goal, u4) -> 11
```

**ARM-FM machine** (`experiments/benchmark/armfm-paper/bundles/arm-fm/armfm-doorkey-5x5/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
TRANSITION_FUNCTION:
(u0, has_key) -> u1
(u0, else) -> u0
(u1, door_open) -> u2
(u1, else) -> u1
(u2, at_goal) -> u3
(u2, else) -> u2
(u3, else) -> u3
REWARD_FUNCTION:
(u0, has_key, u1) -> 0.1
(u1, door_open, u2) -> 0.2
(u2, at_goal, u3) -> 1
```

## armfm-doorkey-5x5-fixed

**Task:** Use the key to open the door, then reach the goal.

**World:** `MiniGrid-DoorKey-5x5-v0`, one fixed map (layout seed 1).

**Results:** test 1.

**LTL** (expected clauses):
- Precedence(has_key, door_open) hard: `(((~door_open) U has_key) | (G (~door_open)))`
- Precedence(door_open, at_goal) hard: `(((~at_goal) U door_open) | (G (~at_goal)))`
- Existence(at_goal) hard: `(F at_goal)`

**FARM machine:** the one of [armfm-doorkey-5x5](#armfm-doorkey-5x5) (`experiments/benchmark/armfm-paper/bundles/farm/armfm-doorkey-5x5`).

**ARM-FM machine:** the one of [armfm-doorkey-5x5](#armfm-doorkey-5x5) (`experiments/benchmark/armfm-paper/bundles/arm-fm/armfm-doorkey-5x5`).

## armfm-doorkey-8x8-fixed

**Task:** Use the key to open the door, then reach the goal.

**World:** `MiniGrid-DoorKey-8x8-v0`, one fixed map (layout seed 1).

**Results:** test 1.

**LTL** (expected clauses):
- Precedence(has_key, door_open) hard: `(((~door_open) U has_key) | (G (~door_open)))`
- Precedence(door_open, at_goal) hard: `(((~at_goal) U door_open) | (G (~at_goal)))`
- Existence(at_goal) hard: `(F at_goal)`

**FARM machine** (`experiments/benchmark/base/bundles/farm/base-doorkey/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u2
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !at_goal&!door_open&has_key) -> u1
(u0, !at_goal&door_open&!has_key) -> u2
(u0, !at_goal&door_open&has_key) -> u3
(u0, at_goal&!door_open&!has_key) -> u2
(u0, at_goal&!door_open&has_key) -> u2
(u0, at_goal&door_open&!has_key) -> u2
(u0, at_goal&door_open&has_key) -> u4
(u1, !at_goal&door_open) -> u3
(u1, at_goal&!door_open) -> u2
(u1, at_goal&door_open) -> u4
(u3, at_goal) -> u4
REWARD_FUNCTION:
(u0, !at_goal&!door_open&has_key, u1) -> 1
(u0, !at_goal&door_open&!has_key, u2) -> -10
(u0, !at_goal&door_open&has_key, u3) -> 2
(u0, at_goal&!door_open&!has_key, u2) -> -10
(u0, at_goal&!door_open&has_key, u2) -> -10
(u0, at_goal&door_open&!has_key, u2) -> -10
(u0, at_goal&door_open&has_key, u4) -> 13
(u1, !at_goal&door_open, u3) -> 1
(u1, at_goal&!door_open, u2) -> -11
(u1, at_goal&door_open, u4) -> 12
(u3, at_goal, u4) -> 11
```

**ARM-FM machine** (`experiments/benchmark/base/bundles/arm-fm/base-doorkey/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
TRANSITION_FUNCTION:
(u0, has_key) -> u1
(u0, else) -> u0
(u1, door_open) -> u2
(u1, else) -> u1
(u2, at_goal) -> u3
(u2, else) -> u2
(u3, else) -> u3
REWARD_FUNCTION:
(u0, has_key, u1) -> 0.1
(u1, door_open, u2) -> 0.2
(u2, at_goal, u3) -> 1
```

## armfm-doorkey-16x16

**Task:** Use the key to open the door, then reach the goal.

**World:** `MiniGrid-DoorKey-16x16-v0`, a new map each episode.

**Results:** test 1.

**LTL** (expected clauses):
- Precedence(has_key, door_open) hard: `(((~door_open) U has_key) | (G (~door_open)))`
- Precedence(door_open, at_goal) hard: `(((~at_goal) U door_open) | (G (~at_goal)))`
- Existence(at_goal) hard: `(F at_goal)`

**FARM machine** (`experiments/benchmark/armfm-paper/bundles/farm/armfm-doorkey-16x16/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u2
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !at_goal&!door_open&has_key) -> u1
(u0, !at_goal&door_open&!has_key) -> u2
(u0, !at_goal&door_open&has_key) -> u3
(u0, at_goal&!door_open&!has_key) -> u2
(u0, at_goal&!door_open&has_key) -> u2
(u0, at_goal&door_open&!has_key) -> u2
(u0, at_goal&door_open&has_key) -> u4
(u1, !at_goal&door_open) -> u3
(u1, at_goal&!door_open) -> u2
(u1, at_goal&door_open) -> u4
(u3, at_goal) -> u4
REWARD_FUNCTION:
(u0, !at_goal&!door_open&has_key, u1) -> 1
(u0, !at_goal&door_open&!has_key, u2) -> -10
(u0, !at_goal&door_open&has_key, u3) -> 2
(u0, at_goal&!door_open&!has_key, u2) -> -10
(u0, at_goal&!door_open&has_key, u2) -> -10
(u0, at_goal&door_open&!has_key, u2) -> -10
(u0, at_goal&door_open&has_key, u4) -> 13
(u1, !at_goal&door_open, u3) -> 1
(u1, at_goal&!door_open, u2) -> -11
(u1, at_goal&door_open, u4) -> 12
(u3, at_goal, u4) -> 11
```

**ARM-FM machine** (`experiments/benchmark/armfm-paper/bundles/arm-fm/armfm-doorkey-16x16/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
TRANSITION_FUNCTION:
(u0, has_key) -> u1
(u0, else) -> u0
(u1, door_open) -> u2
(u1, else) -> u1
(u2, at_goal) -> u3
(u2, else) -> u2
(u3, else) -> u3
REWARD_FUNCTION:
(u0, has_key, u1) -> 0.1
(u1, door_open, u2) -> 0.1
(u2, at_goal, u3) -> 1
```

## armfm-doorkey-16x16-fixed

**Task:** Use the key to open the door, then reach the goal.

**World:** `MiniGrid-DoorKey-16x16-v0`, one fixed map (layout seed 1).

**Results:** test 1.

**LTL** (expected clauses):
- Precedence(has_key, door_open) hard: `(((~door_open) U has_key) | (G (~door_open)))`
- Precedence(door_open, at_goal) hard: `(((~at_goal) U door_open) | (G (~at_goal)))`
- Existence(at_goal) hard: `(F at_goal)`

**FARM machine:** the one of [armfm-doorkey-16x16](#armfm-doorkey-16x16) (`experiments/benchmark/armfm-paper/bundles/farm/armfm-doorkey-16x16`).

**ARM-FM machine:** the one of [armfm-doorkey-16x16](#armfm-doorkey-16x16) (`experiments/benchmark/armfm-paper/bundles/arm-fm/armfm-doorkey-16x16`).

## armfm-unlock-to-unlock

**Task:** Pick up the first key, open its matching door, pick up the second key, open its matching door, and then pick up the target ball.

**World:** `BabyAI-UnlockToUnlock-v0`, a new map each episode.

**Results:** test 1.

**LTL** (expected clauses):
- Existence(has_prerequisite_key) hard: `(F has_prerequisite_key)`
- Existence(prerequisite_door_open) hard: `(F prerequisite_door_open)`
- Existence(has_target_door_key) hard: `(F has_target_door_key)`
- Existence(target_door_open) hard: `(F target_door_open)`
- Existence(target_ball_picked_up) hard: `(F target_ball_picked_up)`
- Precedence(has_prerequisite_key, prerequisite_door_open) hard: `(((~prerequisite_door_open) U has_prerequisite_key) | (G (~prerequisite_door_open)))`
- Precedence(prerequisite_door_open, has_target_door_key) hard: `(((~has_target_door_key) U prerequisite_door_open) | (G (~has_target_door_key)))`
- Precedence(has_target_door_key, target_door_open) hard: `(((~target_door_open) U has_target_door_key) | (G (~target_door_open)))`
- Precedence(target_door_open, target_ball_picked_up) hard: `(((~target_ball_picked_up) U target_door_open) | (G (~target_ball_picked_up)))`

**Also accepted, reading 1:**
- Precedence(has_prerequisite_key, prerequisite_door_open) hard: `(((~prerequisite_door_open) U has_prerequisite_key) | (G (~prerequisite_door_open)))`
- Precedence(prerequisite_door_open, has_target_door_key) hard: `(((~has_target_door_key) U prerequisite_door_open) | (G (~has_target_door_key)))`
- Precedence(has_target_door_key, target_door_open) hard: `(((~target_door_open) U has_target_door_key) | (G (~target_door_open)))`
- Precedence(target_door_open, target_ball_picked_up) hard: `(((~target_ball_picked_up) U target_door_open) | (G (~target_ball_picked_up)))`
- Existence(target_ball_picked_up) hard: `(F target_ball_picked_up)`

**FARM machine** (`experiments/benchmark/armfm-paper/bundles/farm/armfm-unlock-to-unlock/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4, u5, u6
INITIAL_STATE: u0
FINAL_STATES: u6
REJECTING_STATES: u1
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u0, !has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u0, !has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u0, !has_prerequisite_key&!has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u1
(u0, !has_prerequisite_key&!has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u0, !has_prerequisite_key&!has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u0, !has_prerequisite_key&!has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u0, !has_prerequisite_key&has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u1
(u0, !has_prerequisite_key&has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u0, !has_prerequisite_key&has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u0, !has_prerequisite_key&has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u0, !has_prerequisite_key&has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u1
(u0, !has_prerequisite_key&has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u0, !has_prerequisite_key&has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u0, !has_prerequisite_key&has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u0, has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u2
(u0, has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u0, has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u0, has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u0, has_prerequisite_key&!has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u3
(u0, has_prerequisite_key&!has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u0, has_prerequisite_key&!has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u0, has_prerequisite_key&!has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u0, has_prerequisite_key&has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u1
(u0, has_prerequisite_key&has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u0, has_prerequisite_key&has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u0, has_prerequisite_key&has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u0, has_prerequisite_key&has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u4
(u0, has_prerequisite_key&has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u5
(u0, has_prerequisite_key&has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u0, has_prerequisite_key&has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open) -> u6
(u2, !has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u2, !has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u2, !has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u2, !has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u3
(u2, !has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u2, !has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u2, !has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u2, has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u1
(u2, has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u1
(u2, has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u2, has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open) -> u1
(u2, has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open) -> u4
(u2, has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open) -> u5
(u2, has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open) -> u1
(u2, has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open) -> u6
(u3, !has_target_door_key&!target_ball_picked_up&target_door_open) -> u1
(u3, !has_target_door_key&target_ball_picked_up&!target_door_open) -> u1
(u3, !has_target_door_key&target_ball_picked_up&target_door_open) -> u1
(u3, has_target_door_key&!target_ball_picked_up&!target_door_open) -> u4
(u3, has_target_door_key&!target_ball_picked_up&target_door_open) -> u5
(u3, has_target_door_key&target_ball_picked_up&!target_door_open) -> u1
(u3, has_target_door_key&target_ball_picked_up&target_door_open) -> u6
(u4, !target_ball_picked_up&target_door_open) -> u5
(u4, target_ball_picked_up&!target_door_open) -> u1
(u4, target_ball_picked_up&target_door_open) -> u6
(u5, target_ball_picked_up) -> u6
REWARD_FUNCTION:
(u0, !has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -10
(u0, !has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -10
(u0, !has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -10
(u0, !has_prerequisite_key&!has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open, u1) -> -10
(u0, !has_prerequisite_key&!has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -10
(u0, !has_prerequisite_key&!has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -10
(u0, !has_prerequisite_key&!has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -10
(u0, !has_prerequisite_key&has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&!target_door_open, u1) -> -10
(u0, !has_prerequisite_key&has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -10
(u0, !has_prerequisite_key&has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -10
(u0, !has_prerequisite_key&has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -10
(u0, !has_prerequisite_key&has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open, u1) -> -10
(u0, !has_prerequisite_key&has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -10
(u0, !has_prerequisite_key&has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -10
(u0, !has_prerequisite_key&has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -10
(u0, has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&!target_door_open, u2) -> 1
(u0, has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -10
(u0, has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -10
(u0, has_prerequisite_key&!has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -10
(u0, has_prerequisite_key&!has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open, u3) -> 2
(u0, has_prerequisite_key&!has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -10
(u0, has_prerequisite_key&!has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -10
(u0, has_prerequisite_key&!has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -10
(u0, has_prerequisite_key&has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&!target_door_open, u1) -> -10
(u0, has_prerequisite_key&has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -10
(u0, has_prerequisite_key&has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -10
(u0, has_prerequisite_key&has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -10
(u0, has_prerequisite_key&has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open, u4) -> 3
(u0, has_prerequisite_key&has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open, u5) -> 4
(u0, has_prerequisite_key&has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -10
(u0, has_prerequisite_key&has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open, u6) -> 15
(u2, !has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -11
(u2, !has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -11
(u2, !has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -11
(u2, !has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open, u3) -> 1
(u2, !has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -11
(u2, !has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -11
(u2, !has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -11
(u2, has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&!target_door_open, u1) -> -11
(u2, has_target_door_key&!prerequisite_door_open&!target_ball_picked_up&target_door_open, u1) -> -11
(u2, has_target_door_key&!prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -11
(u2, has_target_door_key&!prerequisite_door_open&target_ball_picked_up&target_door_open, u1) -> -11
(u2, has_target_door_key&prerequisite_door_open&!target_ball_picked_up&!target_door_open, u4) -> 2
(u2, has_target_door_key&prerequisite_door_open&!target_ball_picked_up&target_door_open, u5) -> 3
(u2, has_target_door_key&prerequisite_door_open&target_ball_picked_up&!target_door_open, u1) -> -11
(u2, has_target_door_key&prerequisite_door_open&target_ball_picked_up&target_door_open, u6) -> 14
(u3, !has_target_door_key&!target_ball_picked_up&target_door_open, u1) -> -12
(u3, !has_target_door_key&target_ball_picked_up&!target_door_open, u1) -> -12
(u3, !has_target_door_key&target_ball_picked_up&target_door_open, u1) -> -12
(u3, has_target_door_key&!target_ball_picked_up&!target_door_open, u4) -> 1
(u3, has_target_door_key&!target_ball_picked_up&target_door_open, u5) -> 2
(u3, has_target_door_key&target_ball_picked_up&!target_door_open, u1) -> -12
(u3, has_target_door_key&target_ball_picked_up&target_door_open, u6) -> 13
(u4, !target_ball_picked_up&target_door_open, u5) -> 1
(u4, target_ball_picked_up&!target_door_open, u1) -> -13
(u4, target_ball_picked_up&target_door_open, u6) -> 12
(u5, target_ball_picked_up, u6) -> 11
```

**ARM-FM machine** (`experiments/benchmark/armfm-paper/bundles/arm-fm/armfm-unlock-to-unlock/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4, u5
INITIAL_STATE: u0
FINAL_STATES: u5
TRANSITION_FUNCTION:
(u0, has_prerequisite_key) -> u1
(u0, else) -> u0
(u1, prerequisite_door_open) -> u2
(u1, required_key_lost) -> u1
(u1, else) -> u1
(u2, has_target_door_key) -> u3
(u2, else) -> u2
(u3, target_door_open) -> u4
(u3, required_key_lost) -> u3
(u3, else) -> u3
(u4, target_ball_picked_up) -> u5
(u4, else) -> u4
(u5, else) -> u5
REWARD_FUNCTION:
(u0, has_prerequisite_key, u1) -> 0.1
(u1, prerequisite_door_open, u2) -> 0.1
(u1, required_key_lost, u1) -> -0.1
(u2, has_target_door_key, u3) -> 0.1
(u3, target_door_open, u4) -> 0.1
(u3, required_key_lost, u3) -> -0.1
(u4, target_ball_picked_up, u5) -> 1
```

## xland-x1-197

**Task:** Stand directly above the yellow pyramid, facing it, and step forward to turn it into a purple star, then pick up the purple star to turn it into a blue pyramid, then stand so that the blue pyramid is one tile to your right on the map.

**World:** `XLand-R4-13x13-v0`, ruleset `medium-1m-197`, a new map each episode.

**Results:** test 2; test 3 (xland-mix3); test 3 (xland-mix5); test 5.

**LTL** (expected clauses):
- Existence(blue_pyramid_on_right) hard: `(F blue_pyramid_on_right)`
- Precedence(purple_star_made, blue_pyramid_made) hard: `(((~blue_pyramid_made) U purple_star_made) | (G (~blue_pyramid_made)))`
- Precedence(blue_pyramid_made, blue_pyramid_on_right) hard: `(((~blue_pyramid_on_right) U blue_pyramid_made) | (G (~blue_pyramid_on_right)))`

**Also accepted, reading 1:**
- Existence(blue_pyramid_on_right) hard: `(F blue_pyramid_on_right)`
- Precedence(purple_star_made, purple_star_picked_up) hard: `(((~purple_star_picked_up) U purple_star_made) | (G (~purple_star_picked_up)))`
- Precedence(purple_star_picked_up, blue_pyramid_on_right) hard: `(((~blue_pyramid_on_right) U purple_star_picked_up) | (G (~blue_pyramid_on_right)))`

**FARM machine** (`experiments/benchmark/xland/bundles/farm/xland-x1-197/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u2
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !blue_pyramid_made&!blue_pyramid_on_right&purple_star_made) -> u1
(u0, !blue_pyramid_made&blue_pyramid_on_right&!purple_star_made) -> u2
(u0, !blue_pyramid_made&blue_pyramid_on_right&purple_star_made) -> u2
(u0, blue_pyramid_made&!blue_pyramid_on_right&!purple_star_made) -> u2
(u0, blue_pyramid_made&!blue_pyramid_on_right&purple_star_made) -> u3
(u0, blue_pyramid_made&blue_pyramid_on_right&!purple_star_made) -> u2
(u0, blue_pyramid_made&blue_pyramid_on_right&purple_star_made) -> u4
(u1, !blue_pyramid_made&blue_pyramid_on_right) -> u2
(u1, blue_pyramid_made&!blue_pyramid_on_right) -> u3
(u1, blue_pyramid_made&blue_pyramid_on_right) -> u4
(u3, blue_pyramid_on_right) -> u4
REWARD_FUNCTION:
(u0, !blue_pyramid_made&!blue_pyramid_on_right&purple_star_made, u1) -> 1
(u0, !blue_pyramid_made&blue_pyramid_on_right&!purple_star_made, u2) -> -10
(u0, !blue_pyramid_made&blue_pyramid_on_right&purple_star_made, u2) -> -10
(u0, blue_pyramid_made&!blue_pyramid_on_right&!purple_star_made, u2) -> -10
(u0, blue_pyramid_made&!blue_pyramid_on_right&purple_star_made, u3) -> 2
(u0, blue_pyramid_made&blue_pyramid_on_right&!purple_star_made, u2) -> -10
(u0, blue_pyramid_made&blue_pyramid_on_right&purple_star_made, u4) -> 13
(u1, !blue_pyramid_made&blue_pyramid_on_right, u2) -> -11
(u1, blue_pyramid_made&!blue_pyramid_on_right, u3) -> 1
(u1, blue_pyramid_made&blue_pyramid_on_right, u4) -> 12
(u3, blue_pyramid_on_right, u4) -> 11
```

**ARM-FM machine** (`experiments/benchmark/xland/bundles/arm-fm/xland-x1-197/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
TRANSITION_FUNCTION:
(u0, purple_star_made) -> u1
(u0, else) -> u0
(u1, purple_star_picked_up & blue_pyramid_made) -> u2
(u1, else) -> u1
(u2, blue_pyramid_on_right) -> u3
(u2, else) -> u2
(u3, else) -> u3
REWARD_FUNCTION:
(u0, purple_star_made, u1) -> 0.1
(u1, purple_star_picked_up & blue_pyramid_made, u2) -> 0.2
(u2, blue_pyramid_on_right, u3) -> 1
```

## xland-zc

**Task:** Pick up the blue key to turn it into a blue pyramid, then stand so that the blue pyramid is one tile to your right on the map.

**World:** `XLand-R4-13x13-v0`, ruleset `figure10-c`, a new map each episode.

**Results:** test 2; test 4 (zero-shot target).

**LTL** (expected clauses):
- Existence(blue_pyramid_on_right) hard: `(F blue_pyramid_on_right)`
- Precedence(blue_pyramid_made, blue_pyramid_on_right) hard: `(((~blue_pyramid_on_right) U blue_pyramid_made) | (G (~blue_pyramid_on_right)))`

**Also accepted, reading 1:**
- Existence(blue_pyramid_on_right) hard: `(F blue_pyramid_on_right)`
- Precedence(blue_key_picked_up, blue_pyramid_on_right) hard: `(((~blue_pyramid_on_right) U blue_key_picked_up) | (G (~blue_pyramid_on_right)))`

**FARM machine** (`experiments/benchmark/xland/bundles/farm/xland-zc/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
REJECTING_STATES: u1
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !blue_key_picked_up&blue_pyramid_on_right) -> u1
(u0, blue_key_picked_up&!blue_pyramid_on_right) -> u2
(u0, blue_key_picked_up&blue_pyramid_on_right) -> u3
(u2, blue_pyramid_on_right) -> u3
REWARD_FUNCTION:
(u0, !blue_key_picked_up&blue_pyramid_on_right, u1) -> -10
(u0, blue_key_picked_up&!blue_pyramid_on_right, u2) -> 1
(u0, blue_key_picked_up&blue_pyramid_on_right, u3) -> 12
(u2, blue_pyramid_on_right, u3) -> 11
```

**ARM-FM machine** (`experiments/benchmark/xland/bundles/arm-fm/xland-zc/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2
INITIAL_STATE: u0
FINAL_STATES: u2
TRANSITION_FUNCTION:
(u0, blue_key_picked_up & blue_pyramid_made) -> u1
(u0, else) -> u0
(u1, blue_pyramid_on_right) -> u2
(u1, else) -> u1
(u2, else) -> u2
REWARD_FUNCTION:
(u0, blue_key_picked_up & blue_pyramid_made, u1) -> 0.1
(u1, blue_pyramid_on_right, u2) -> 1
```

## xland-x2-212

**Task:** Face the purple ball and step forward to turn it into a white key, then stand directly to the right of the white key, facing it, and step forward to turn it into a grey star, then stand so that the grey star is one tile to your right on the map.

**World:** `XLand-R4-13x13-v0`, ruleset `medium-1m-212`, a new map each episode.

**Results:** test 3 (xland-mix3); test 3 (xland-mix5); test 5.

**LTL** (expected clauses):
- Existence(grey_star_on_right) hard: `(F grey_star_on_right)`
- Precedence(white_key_made, grey_star_made) hard: `(((~grey_star_made) U white_key_made) | (G (~grey_star_made)))`
- Precedence(grey_star_made, grey_star_on_right) hard: `(((~grey_star_on_right) U grey_star_made) | (G (~grey_star_on_right)))`

**FARM machine** (`experiments/benchmark/xland/bundles/farm/xland-x2-212/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u2
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !grey_star_made&!grey_star_on_right&white_key_made) -> u1
(u0, !grey_star_made&grey_star_on_right&!white_key_made) -> u2
(u0, !grey_star_made&grey_star_on_right&white_key_made) -> u2
(u0, grey_star_made&!grey_star_on_right&!white_key_made) -> u2
(u0, grey_star_made&!grey_star_on_right&white_key_made) -> u3
(u0, grey_star_made&grey_star_on_right&!white_key_made) -> u2
(u0, grey_star_made&grey_star_on_right&white_key_made) -> u4
(u1, !grey_star_made&grey_star_on_right) -> u2
(u1, grey_star_made&!grey_star_on_right) -> u3
(u1, grey_star_made&grey_star_on_right) -> u4
(u3, grey_star_on_right) -> u4
REWARD_FUNCTION:
(u0, !grey_star_made&!grey_star_on_right&white_key_made, u1) -> 1
(u0, !grey_star_made&grey_star_on_right&!white_key_made, u2) -> -10
(u0, !grey_star_made&grey_star_on_right&white_key_made, u2) -> -10
(u0, grey_star_made&!grey_star_on_right&!white_key_made, u2) -> -10
(u0, grey_star_made&!grey_star_on_right&white_key_made, u3) -> 2
(u0, grey_star_made&grey_star_on_right&!white_key_made, u2) -> -10
(u0, grey_star_made&grey_star_on_right&white_key_made, u4) -> 13
(u1, !grey_star_made&grey_star_on_right, u2) -> -11
(u1, grey_star_made&!grey_star_on_right, u3) -> 1
(u1, grey_star_made&grey_star_on_right, u4) -> 12
(u3, grey_star_on_right, u4) -> 11
```

**ARM-FM machine** (`experiments/benchmark/xland/bundles/arm-fm/xland-x2-212/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
TRANSITION_FUNCTION:
(u0, white_key_made) -> u1
(u0, else) -> u0
(u1, grey_star_made) -> u2
(u1, else) -> u1
(u2, grey_star_on_right) -> u3
(u2, else) -> u2
(u3, else) -> u3
REWARD_FUNCTION:
(u0, white_key_made, u1) -> 0.1
(u1, grey_star_made, u2) -> 0.2
(u2, grey_star_on_right, u3) -> 1
```

## xland-x3-260

**Task:** Pick up the blue key to turn it into a green star, then put the green star down one tile to your left on the map to turn it into an orange star, then pick up the orange star.

**World:** `XLand-R4-13x13-v0`, ruleset `medium-1m-260`, a new map each episode.

**Results:** test 3 (xland-mix3); test 3 (xland-mix5); test 5.

**LTL** (expected clauses):
- Existence(orange_star_held) hard: `(F orange_star_held)`
- Precedence(green_star_made, orange_star_made) hard: `(((~orange_star_made) U green_star_made) | (G (~orange_star_made)))`
- Precedence(orange_star_made, orange_star_held) hard: `(((~orange_star_held) U orange_star_made) | (G (~orange_star_held)))`

**Also accepted, reading 1:**
- Existence(orange_star_held) hard: `(F orange_star_held)`
- Precedence(blue_key_picked_up, orange_star_made) hard: `(((~orange_star_made) U blue_key_picked_up) | (G (~orange_star_made)))`
- Precedence(orange_star_made, orange_star_held) hard: `(((~orange_star_held) U orange_star_made) | (G (~orange_star_held)))`

**FARM machine** (`experiments/benchmark/xland/bundles/farm/xland-x3-260/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u1
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !blue_key_picked_up&!orange_star_held&orange_star_made) -> u1
(u0, !blue_key_picked_up&orange_star_held&!orange_star_made) -> u1
(u0, !blue_key_picked_up&orange_star_held&orange_star_made) -> u1
(u0, blue_key_picked_up&!orange_star_held&!orange_star_made) -> u2
(u0, blue_key_picked_up&!orange_star_held&orange_star_made) -> u3
(u0, blue_key_picked_up&orange_star_held&!orange_star_made) -> u1
(u0, blue_key_picked_up&orange_star_held&orange_star_made) -> u4
(u2, !orange_star_held&orange_star_made) -> u3
(u2, orange_star_held&!orange_star_made) -> u1
(u2, orange_star_held&orange_star_made) -> u4
(u3, orange_star_held) -> u4
REWARD_FUNCTION:
(u0, !blue_key_picked_up&!orange_star_held&orange_star_made, u1) -> -10
(u0, !blue_key_picked_up&orange_star_held&!orange_star_made, u1) -> -10
(u0, !blue_key_picked_up&orange_star_held&orange_star_made, u1) -> -10
(u0, blue_key_picked_up&!orange_star_held&!orange_star_made, u2) -> 1
(u0, blue_key_picked_up&!orange_star_held&orange_star_made, u3) -> 2
(u0, blue_key_picked_up&orange_star_held&!orange_star_made, u1) -> -10
(u0, blue_key_picked_up&orange_star_held&orange_star_made, u4) -> 13
(u2, !orange_star_held&orange_star_made, u3) -> 1
(u2, orange_star_held&!orange_star_made, u1) -> -11
(u2, orange_star_held&orange_star_made, u4) -> 12
(u3, orange_star_held, u4) -> 11
```

**ARM-FM machine** (`experiments/benchmark/xland/bundles/arm-fm/xland-x3-260/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
TRANSITION_FUNCTION:
(u0, blue_key_picked_up) -> u1
(u0, else) -> u0
(u1, orange_star_made) -> u2
(u1, else) -> u1
(u2, orange_star_held) -> u3
(u2, else) -> u2
(u3, else) -> u3
REWARD_FUNCTION:
(u0, blue_key_picked_up, u1) -> 0.1
(u1, orange_star_made, u2) -> 0.2
(u2, orange_star_held, u3) -> 1
```

## xland-x4-859

**Task:** Stand directly above the green pyramid, facing it, and step forward to turn it into a brown pyramid, then stand directly above the brown pyramid, facing it, and step forward to turn it into a blue ball, then step forward with the blue ball next to you.

**World:** `XLand-R4-13x13-v0`, ruleset `medium-1m-859`, a new map each episode.

**Results:** test 3 (xland-mix5); test 5.

**LTL** (expected clauses):
- Existence(blue_ball_reached) hard: `(F blue_ball_reached)`
- Precedence(brown_pyramid_made, blue_ball_made) hard: `(((~blue_ball_made) U brown_pyramid_made) | (G (~blue_ball_made)))`
- Precedence(blue_ball_made, blue_ball_reached) hard: `(((~blue_ball_reached) U blue_ball_made) | (G (~blue_ball_reached)))`

**FARM machine** (`experiments/benchmark/xland/bundles/farm/xland-x4-859/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u2
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !blue_ball_made&!blue_ball_reached&brown_pyramid_made) -> u1
(u0, !blue_ball_made&blue_ball_reached&!brown_pyramid_made) -> u2
(u0, !blue_ball_made&blue_ball_reached&brown_pyramid_made) -> u2
(u0, blue_ball_made&!blue_ball_reached&!brown_pyramid_made) -> u2
(u0, blue_ball_made&!blue_ball_reached&brown_pyramid_made) -> u3
(u0, blue_ball_made&blue_ball_reached&!brown_pyramid_made) -> u2
(u0, blue_ball_made&blue_ball_reached&brown_pyramid_made) -> u4
(u1, !blue_ball_made&blue_ball_reached) -> u2
(u1, blue_ball_made&!blue_ball_reached) -> u3
(u1, blue_ball_made&blue_ball_reached) -> u4
(u3, blue_ball_reached) -> u4
REWARD_FUNCTION:
(u0, !blue_ball_made&!blue_ball_reached&brown_pyramid_made, u1) -> 1
(u0, !blue_ball_made&blue_ball_reached&!brown_pyramid_made, u2) -> -10
(u0, !blue_ball_made&blue_ball_reached&brown_pyramid_made, u2) -> -10
(u0, blue_ball_made&!blue_ball_reached&!brown_pyramid_made, u2) -> -10
(u0, blue_ball_made&!blue_ball_reached&brown_pyramid_made, u3) -> 2
(u0, blue_ball_made&blue_ball_reached&!brown_pyramid_made, u2) -> -10
(u0, blue_ball_made&blue_ball_reached&brown_pyramid_made, u4) -> 13
(u1, !blue_ball_made&blue_ball_reached, u2) -> -11
(u1, blue_ball_made&!blue_ball_reached, u3) -> 1
(u1, blue_ball_made&blue_ball_reached, u4) -> 12
(u3, blue_ball_reached, u4) -> 11
```

**ARM-FM machine** (`experiments/benchmark/xland/bundles/arm-fm/xland-x4-859/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
TRANSITION_FUNCTION:
(u0, brown_pyramid_made) -> u1
(u0, else) -> u0
(u1, blue_ball_reached) -> u3
(u1, blue_ball_made & !blue_ball_reached) -> u2
(u1, else) -> u1
(u2, blue_ball_reached) -> u3
(u2, else) -> u2
(u3, else) -> u3
REWARD_FUNCTION:
(u0, brown_pyramid_made, u1) -> 0.1
(u1, blue_ball_reached, u3) -> 1.2
(u1, blue_ball_made & !blue_ball_reached, u2) -> 0.2
(u2, blue_ball_reached, u3) -> 1
```

## xland-x5-594

**Task:** Stand directly below the brown key, facing it, and step forward to turn it into a pink ball, then stand so that the pink ball is one tile to your right on the map.

**World:** `XLand-R4-13x13-v0`, ruleset `medium-1m-594`, a new map each episode.

**Results:** test 3 (xland-mix5); test 5.

**LTL** (expected clauses):
- Existence(pink_ball_on_right) hard: `(F pink_ball_on_right)`
- Precedence(pink_ball_made, pink_ball_on_right) hard: `(((~pink_ball_on_right) U pink_ball_made) | (G (~pink_ball_on_right)))`

**FARM machine** (`experiments/benchmark/xland/bundles/farm/xland-x5-594/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
REJECTING_STATES: u1
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !pink_ball_made&pink_ball_on_right) -> u1
(u0, pink_ball_made&!pink_ball_on_right) -> u2
(u0, pink_ball_made&pink_ball_on_right) -> u3
(u2, pink_ball_on_right) -> u3
REWARD_FUNCTION:
(u0, !pink_ball_made&pink_ball_on_right, u1) -> -10
(u0, pink_ball_made&!pink_ball_on_right, u2) -> 1
(u0, pink_ball_made&pink_ball_on_right, u3) -> 12
(u2, pink_ball_on_right, u3) -> 11
```

**ARM-FM machine** (`experiments/benchmark/xland/bundles/arm-fm/xland-x5-594/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2
INITIAL_STATE: u0
FINAL_STATES: u2
TRANSITION_FUNCTION:
(u0, pink_ball_made) -> u1
(u0, else) -> u0
(u1, pink_ball_on_right) -> u2
(u1, else) -> u1
(u2, else) -> u2
REWARD_FUNCTION:
(u0, pink_ball_made, u1) -> 0.1
(u1, pink_ball_on_right, u2) -> 1
```

## xland-za

**Task:** Pick up the blue key and put it down next to the purple ball to make an orange star, then pick up the orange star.

**World:** `XLand-R4-13x13-v0`, ruleset `figure10-a`, a new map each episode.

**Results:** test 4 (training mix).

**LTL** (expected clauses):
- Existence(orange_star_held) hard: `(F orange_star_held)`
- Precedence(blue_key_picked_up, orange_star_made) hard: `(((~orange_star_made) U blue_key_picked_up) | (G (~orange_star_made)))`
- Precedence(orange_star_made, orange_star_held) hard: `(((~orange_star_held) U orange_star_made) | (G (~orange_star_held)))`

**FARM machine** (`experiments/benchmark/xland/bundles/farm/xland-za/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u1
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !blue_key_picked_up&!orange_star_held&orange_star_made) -> u1
(u0, !blue_key_picked_up&orange_star_held&!orange_star_made) -> u1
(u0, !blue_key_picked_up&orange_star_held&orange_star_made) -> u1
(u0, blue_key_picked_up&!orange_star_held&!orange_star_made) -> u2
(u0, blue_key_picked_up&!orange_star_held&orange_star_made) -> u3
(u0, blue_key_picked_up&orange_star_held&!orange_star_made) -> u1
(u0, blue_key_picked_up&orange_star_held&orange_star_made) -> u4
(u2, !orange_star_held&orange_star_made) -> u3
(u2, orange_star_held&!orange_star_made) -> u1
(u2, orange_star_held&orange_star_made) -> u4
(u3, orange_star_held) -> u4
REWARD_FUNCTION:
(u0, !blue_key_picked_up&!orange_star_held&orange_star_made, u1) -> -10
(u0, !blue_key_picked_up&orange_star_held&!orange_star_made, u1) -> -10
(u0, !blue_key_picked_up&orange_star_held&orange_star_made, u1) -> -10
(u0, blue_key_picked_up&!orange_star_held&!orange_star_made, u2) -> 1
(u0, blue_key_picked_up&!orange_star_held&orange_star_made, u3) -> 2
(u0, blue_key_picked_up&orange_star_held&!orange_star_made, u1) -> -10
(u0, blue_key_picked_up&orange_star_held&orange_star_made, u4) -> 13
(u2, !orange_star_held&orange_star_made, u3) -> 1
(u2, orange_star_held&!orange_star_made, u1) -> -11
(u2, orange_star_held&orange_star_made, u4) -> 12
(u3, orange_star_held, u4) -> 11
```

**ARM-FM machine** (`experiments/benchmark/xland/bundles/arm-fm/xland-za/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
TRANSITION_FUNCTION:
(u0, blue_key_picked_up) -> u1
(u0, else) -> u0
(u1, orange_star_made) -> u2
(u1, else) -> u1
(u2, orange_star_held) -> u3
(u2, else) -> u2
(u3, else) -> u3
REWARD_FUNCTION:
(u0, blue_key_picked_up, u1) -> 0.1
(u1, orange_star_made, u2) -> 0.2
(u2, orange_star_held, u3) -> 1
```

## xland-zb

**Task:** Pick up the blue star to turn it into a blue pyramid, then stand so that the blue pyramid is one tile to your right on the map.

**World:** `XLand-R4-13x13-v0`, ruleset `figure10-b`, a new map each episode.

**Results:** test 4 (training mix).

**LTL** (expected clauses):
- Existence(blue_pyramid_on_right) hard: `(F blue_pyramid_on_right)`
- Precedence(blue_pyramid_made, blue_pyramid_on_right) hard: `(((~blue_pyramid_on_right) U blue_pyramid_made) | (G (~blue_pyramid_on_right)))`

**Also accepted, reading 1:**
- Existence(blue_pyramid_on_right) hard: `(F blue_pyramid_on_right)`
- Precedence(blue_star_picked_up, blue_pyramid_on_right) hard: `(((~blue_pyramid_on_right) U blue_star_picked_up) | (G (~blue_pyramid_on_right)))`

**FARM machine** (`experiments/benchmark/xland/bundles/farm/xland-zb/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
FINAL_STATES: u3
REJECTING_STATES: u2
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !blue_pyramid_on_right&blue_star_picked_up) -> u1
(u0, blue_pyramid_on_right&!blue_star_picked_up) -> u2
(u0, blue_pyramid_on_right&blue_star_picked_up) -> u3
(u1, blue_pyramid_on_right) -> u3
REWARD_FUNCTION:
(u0, !blue_pyramid_on_right&blue_star_picked_up, u1) -> 1
(u0, blue_pyramid_on_right&!blue_star_picked_up, u2) -> -10
(u0, blue_pyramid_on_right&blue_star_picked_up, u3) -> 12
(u1, blue_pyramid_on_right, u3) -> 11
```

**ARM-FM machine** (`experiments/benchmark/xland/bundles/arm-fm/xland-zb/reward_machine.txt`):

```text
REWARD_MACHINE:
STATES: u0, u1, u2
INITIAL_STATE: u0
FINAL_STATES: u2
TRANSITION_FUNCTION:
(u0, blue_pyramid_made) -> u1
(u0, else) -> u0
(u1, blue_pyramid_on_right) -> u2
(u1, else) -> u1
(u2, else) -> u2
REWARD_FUNCTION:
(u0, blue_pyramid_made, u1) -> 0.1
(u1, blue_pyramid_on_right, u2) -> 1
```
