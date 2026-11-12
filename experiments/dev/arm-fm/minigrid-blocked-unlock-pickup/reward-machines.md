# Published Reward Machines

## `BUP-RM-1`

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
TRANSITION_FUNCTION:
(u0, has_ball) -> u1
(u0, else) -> u0
(u1, has_key) -> u2
(u1, else) -> u1
(u2, door_unlocked) -> u3
(u2, no_key) -> u1
(u2, else) -> u2
(u3, has_box) -> u4
(u3, else) -> u3
(u4, else) -> u4
REWARD_FUNCTION:
(u0, has_ball, u1) -> 0.2
(u1, has_key, u2) -> 0.2
(u2, door_unlocked, u3) -> 0.2
(u2, no_key, u1) -> -0.3
(u3, has_box, u4) -> 1
```

Source: <https://github.com/roger-creus/llms-rm-rl/blob/main/reward_machines/BlockedUnlockPickup/RM-vFINAL.txt>.
