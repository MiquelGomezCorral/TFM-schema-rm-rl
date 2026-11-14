## Variants

Medians and the latest are over the seeds that reach the number; `never` means no seed does.

| card | variant | seeds | solved greedy | solved sampled | median first solve (greedy) | median steps to 0.8 greedy / sampled | latest steps to 0.8 (greedy) | mean final greedy / sampled |
|---|---|---|---|---|---|---|---|---|
| base-doorkey | env | 5 (5 finished) | 1 of 5 | 1 of 5 | 381k | 504k / 373k | 504k | 16% / 21% |
| base-unlock-pickup | rm | 5 (5 finished) | 5 of 5 | 5 of 5 | 512k | 573k / 451k | 893k | 97% / 100% |
| base-unlock-pickup | env | 5 (5 finished) | 1 of 5 | 1 of 5 | 1262k | 1331k / 1151k | 1331k | 17% / 21% |
| base-unlock-pickup | rm-tuned | 5 (5 finished) | 2 of 5 | 2 of 5 | 1206k | 1327k / 1133k | 1352k | 35% / 40% |
| base-unlock-pickup | env-tuned | 5 (5 finished) | 0 of 5 | 0 of 5 | never | never / never | never | 0% / 0% |
| base-unlock-pickup | rm-epsilon | 5 (5 finished) | 3 of 5 | 3 of 5 | 520k | 594k / 442k | 643k | 59% / 60% |
| base-unlock-pickup | rm-entropy | 5 (5 finished) | 4 of 5 | 4 of 5 | 442k | 543k / 393k | 573k | 78% / 80% |
| base-unlock-pickup | rm-tuned-epsilon | 5 (5 finished) | 0 of 5 | 0 of 5 | never | never / never | never | 0% / 0% |
| base-unlock-pickup | rm-tuned-entropy | 5 (5 finished) | 3 of 5 | 3 of 5 | 782k | 823k / 672k | 1130k | 58% / 60% |

Optimizer health, mean over the first 500k steps (policy drift per update, share of samples at the clip, critic fit):

| card | variant | approx_kl | clipfrac | explained variance |
|---|---|---|---|---|
| base-doorkey | env | 0.009 | 0.34 | -2.56 |
| base-unlock-pickup | rm | 0.017 | 0.45 | 0.08 |
| base-unlock-pickup | env | 0.013 | 0.43 | -2.69 |
| base-unlock-pickup | rm-tuned | 0.039 | 0.35 | -0.10 |
| base-unlock-pickup | env-tuned | 0.037 | 0.34 | -2.23 |
| base-unlock-pickup | rm-epsilon | 0.016 | 0.44 | 0.07 |
| base-unlock-pickup | rm-entropy | 0.015 | 0.46 | 0.11 |
| base-unlock-pickup | rm-tuned-epsilon | 0.039 | 0.36 | -0.14 |
| base-unlock-pickup | rm-tuned-entropy | 0.040 | 0.37 | -0.12 |

## Runs

| card | variant | seed | status | first solve greedy / sampled | steps to 0.8 greedy / sampled | final greedy / sampled (100 layouts) | entropy at jump / final | training reached key / door / box (last 200k steps) |
|---|---|---|---|---|---|---|---|---|
| base-doorkey | env | 1 | finished | never / 270k | never / never | 0% / 1% | - / 1.71 | - |
| base-doorkey | env | 2 | finished | never / 12k | never / never | 0% / 0% | - / 1.68 | - |
| base-doorkey | env | 3 | finished | 381k / 12k | 504k / 373k | 81% / 100% | 1.71 / 0.62 | - |
| base-doorkey | env | 4 | finished | never / 53k | never / never | 0% / 5% | - / 1.70 | - |
| base-doorkey | env | 21 | finished | never / 143k | never / never | 0% / 1% | - / 1.76 | - |
| base-unlock-pickup | rm | 1 | finished | 520k / 233k | 610k / 471k | 97% / 100% | 1.46 / 0.09 | 100% / 100% / 100% |
| base-unlock-pickup | rm | 2 | finished | 451k / 143k | 573k / 393k | 98% / 100% | 1.57 / 0.06 | 100% / 100% / 100% |
| base-unlock-pickup | rm | 3 | finished | 770k / 172k | 893k / 741k | 95% / 100% | 0.83 / 0.08 | 100% / 100% / 100% |
| base-unlock-pickup | rm | 4 | finished | 352k / 12k | 512k / 332k | 98% / 100% | 1.53 / 0.07 | 100% / 100% / 100% |
| base-unlock-pickup | rm | 21 | finished | 512k / 254k | 561k / 451k | 99% / 100% | 1.53 / 0.09 | 100% / 100% / 100% |
| base-unlock-pickup | env | 1 | finished | never / never | never / never | 0% / 0% | - / 1.62 | - |
| base-unlock-pickup | env | 2 | finished | never / 451k | never / never | 0% / 0% | - / 1.59 | - |
| base-unlock-pickup | env | 3 | finished | never / 414k | never / never | 0% / 2% | - / 1.59 | - |
| base-unlock-pickup | env | 4 | finished | never / 311k | never / never | 0% / 3% | - / 1.59 | - |
| base-unlock-pickup | env | 21 | finished | 1262k / 123k | 1331k / 1151k | 84% / 100% | 1.62 / 0.21 | - |
| base-unlock-pickup | rm-tuned | 1 | finished | never / never | never / never | 0% / 0% | - / 1.56 | 28% / 11% / 0% |
| base-unlock-pickup | rm-tuned | 2 | finished | never / 131k | never / never | 0% / 0% | - / 1.57 | 2% / 0% / 0% |
| base-unlock-pickup | rm-tuned | 3 | finished | 1241k / 594k | 1352k / 1192k | 85% / 100% | 1.24 / 0.22 | 100% / 100% / 100% |
| base-unlock-pickup | rm-tuned | 4 | finished | 1171k / 152k | 1303k / 1073k | 91% / 99% | 1.29 / 0.19 | 100% / 100% / 100% |
| base-unlock-pickup | rm-tuned | 21 | finished | never / 193k | never / never | 0% / 0% | - / 1.54 | 6% / 0% / 0% |
| base-unlock-pickup | env-tuned | 1 | finished | never / 610k | never / never | 0% / 0% | - / 1.33 | - |
| base-unlock-pickup | env-tuned | 2 | finished | never / 541k | never / never | 0% / 0% | - / 1.41 | - |
| base-unlock-pickup | env-tuned | 3 | finished | never / never | never / never | 0% / 0% | - / 1.32 | - |
| base-unlock-pickup | env-tuned | 4 | finished | never / 1343k | never / never | 0% / 0% | - / 1.33 | - |
| base-unlock-pickup | env-tuned | 21 | finished | never / 1503k | never / never | 0% / 2% | - / 1.36 | - |
| base-unlock-pickup | rm-epsilon | 1 | finished | 414k / 172k | 553k / 360k | 99% / 100% | 1.51 / 0.09 | 100% / 100% / 100% |
| base-unlock-pickup | rm-epsilon | 2 | finished | never / never | never / never | 0% / 0% | - / 1.67 | 27% / 7% / 0% |
| base-unlock-pickup | rm-epsilon | 3 | finished | 520k / 41k | 643k / 442k | 98% / 100% | 1.50 / 0.07 | 100% / 100% / 100% |
| base-unlock-pickup | rm-epsilon | 4 | finished | never / 111k | never / never | 0% / 0% | - / 1.44 | 52% / 19% / 0% |
| base-unlock-pickup | rm-epsilon | 21 | finished | 532k / 90k | 594k / 483k | 99% / 100% | 1.50 / 0.08 | 100% / 100% / 100% |
| base-unlock-pickup | rm-entropy | 1 | finished | 422k / 164k | 504k / 344k | 96% / 100% | 1.70 / 0.08 | 100% / 100% / 100% |
| base-unlock-pickup | rm-entropy | 2 | finished | 463k / 53k | 573k / 430k | 98% / 100% | 1.65 / 0.11 | 100% / 100% / 100% |
| base-unlock-pickup | rm-entropy | 3 | finished | 414k / 221k | 532k / 373k | 99% / 100% | 1.62 / 0.09 | 100% / 100% / 100% |
| base-unlock-pickup | rm-entropy | 4 | finished | 471k / 12k | 553k / 414k | 97% / 100% | 1.60 / 0.08 | 100% / 100% / 100% |
| base-unlock-pickup | rm-entropy | 21 | finished | never / 180k | never / never | 0% / 0% | - / 1.50 | 69% / 39% / 0% |
| base-unlock-pickup | rm-tuned-epsilon | 1 | finished | never / 193k | never / never | 0% / 0% | - / 1.48 | 5% / 1% / 0% |
| base-unlock-pickup | rm-tuned-epsilon | 2 | finished | never / never | never / never | 0% / 0% | - / 1.46 | 3% / 0% / 0% |
| base-unlock-pickup | rm-tuned-epsilon | 3 | finished | never / 172k | never / never | 0% / 0% | - / 1.58 | 5% / 0% / 0% |
| base-unlock-pickup | rm-tuned-epsilon | 4 | finished | never / 12k | never / never | 0% / 0% | - / 1.57 | 11% / 0% / 0% |
| base-unlock-pickup | rm-tuned-epsilon | 21 | finished | never / 152k | never / never | 0% / 0% | - / 1.53 | 14% / 2% / 0% |
| base-unlock-pickup | rm-tuned-entropy | 1 | finished | never / never | never / never | 0% / 0% | - / 1.54 | 13% / 0% / 0% |
| base-unlock-pickup | rm-tuned-entropy | 2 | finished | 963k / 492k | 1130k / 901k | 93% / 100% | 1.28 / 0.12 | 100% / 100% / 100% |
| base-unlock-pickup | rm-tuned-entropy | 3 | finished | 303k / 82k | 504k / 332k | 98% / 100% | 1.50 / 0.06 | 100% / 100% / 100% |
| base-unlock-pickup | rm-tuned-entropy | 4 | finished | never / never | never / never | 0% / 0% | - / 1.59 | 7% / 1% / 0% |
| base-unlock-pickup | rm-tuned-entropy | 21 | finished | 782k / 504k | 823k / 672k | 98% / 100% | 1.43 / 0.08 | 100% / 100% / 100% |

## Cards

### base-unlock-pickup

**Task:** Acquire the matching key, unlock the door, and pick up the designated box in the other room.

**LTL** (the card's reference clauses, the expected specification; the Reward Machine below is the compiled bundle that trains):
- `Precedence(has_door_key, door_open)` [hard]: `(((~door_open) U has_door_key) | (G (~door_open)))`
- `Precedence(door_open, target_picked_up)` [hard]: `(((~target_picked_up) U door_open) | (G (~target_picked_up)))`
- `Existence(target_picked_up)` [hard]: `(F target_picked_up)`

**Reward Machine** (interactive graph: `rm/base-unlock-pickup.html`):

```
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u1
ACCEPTING_STATES:
DEFAULT_REWARD: 0
HARD_FAILED_REWARD: -1
SOFT_FAILED_REWARD: -0.5
TRANSITION_FUNCTION:
(u0, !door_open&!has_door_key&target_picked_up) -> u1
(u0, !door_open&has_door_key&!target_picked_up) -> u2
(u0, !door_open&has_door_key&target_picked_up) -> u1
(u0, door_open&!has_door_key&!target_picked_up) -> u1
(u0, door_open&!has_door_key&target_picked_up) -> u1
(u0, door_open&has_door_key&!target_picked_up) -> u3
(u0, door_open&has_door_key&target_picked_up) -> u4
(u2, !door_open&target_picked_up) -> u1
(u2, door_open&!target_picked_up) -> u3
(u2, door_open&target_picked_up) -> u4
(u3, target_picked_up) -> u4
REWARD_FUNCTION:
(u0, !door_open&!has_door_key&target_picked_up, u1) -> -4
(u0, !door_open&has_door_key&!target_picked_up, u2) -> 0.1
(u0, !door_open&has_door_key&target_picked_up, u1) -> -4
(u0, door_open&!has_door_key&!target_picked_up, u1) -> -4
(u0, door_open&!has_door_key&target_picked_up, u1) -> -4
(u0, door_open&has_door_key&!target_picked_up, u3) -> 0.2
(u0, door_open&has_door_key&target_picked_up, u4) -> 1.3
(u2, !door_open&target_picked_up, u1) -> -3
(u2, door_open&!target_picked_up, u3) -> 0.1
(u2, door_open&target_picked_up, u4) -> 1.2
(u3, target_picked_up, u4) -> 1.1
PENDING_PROMISES:
u0: hard 3, soft 0
u2: hard 2, soft 0
u3: hard 1, soft 0
```

### base-doorkey

**Task:** Use the key to open the door, then reach the goal.

**LTL** (the card's reference clauses, the expected specification; the Reward Machine below is the compiled bundle that trains):
- `Precedence(has_key, door_open)` [hard]: `(((~door_open) U has_key) | (G (~door_open)))`
- `Precedence(door_open, at_goal)` [hard]: `(((~at_goal) U door_open) | (G (~at_goal)))`
- `Existence(at_goal)` [hard]: `(F at_goal)`

**Reward Machine** (interactive graph: `rm/base-doorkey.html`):

```
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
FINAL_STATES: u4
REJECTING_STATES: u2
ACCEPTING_STATES:
DEFAULT_REWARD: 0
HARD_FAILED_REWARD: -1
SOFT_FAILED_REWARD: -0.5
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
(u0, !at_goal&!door_open&has_key, u1) -> 0.1
(u0, !at_goal&door_open&!has_key, u2) -> -4
(u0, !at_goal&door_open&has_key, u3) -> 0.2
(u0, at_goal&!door_open&!has_key, u2) -> -4
(u0, at_goal&!door_open&has_key, u2) -> -4
(u0, at_goal&door_open&!has_key, u2) -> -4
(u0, at_goal&door_open&has_key, u4) -> 1.3
(u1, !at_goal&door_open, u3) -> 0.1
(u1, at_goal&!door_open, u2) -> -3
(u1, at_goal&door_open, u4) -> 1.2
(u3, at_goal, u4) -> 1.1
PENDING_PROMISES:
u0: hard 3, soft 0
u1: hard 2, soft 0
u3: hard 1, soft 0
```
