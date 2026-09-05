# Published Reward Machines

## `UTU-RM-1`

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4, u5
INITIAL_STATE: u0

TRANSITION_FUNCTION:
(u0, got_y_key) -> u1
(u0, else) -> u0
(u1, door_y_opened) -> u2
(u1, lost_y_key) -> u0
(u1, else) -> u1
(u2, got_r_key) -> u3
(u2, else) -> u2
(u3, door_r_opened) -> u4
(u3, lost_r_key) -> u2
(u3, else) -> u3
(u4, entered_goal_room) -> u5
(u4, got_ball) -> u5
(u4, else) -> u4
(u5, else) -> u5

REWARD_FUNCTION:
(u0, got_y_key, u1) -> 0.1
(u1, door_y_opened, u2) -> 0.2
(u1, lost_y_key, u0) -> -0.1
(u2, got_r_key, u3) -> 0.1
(u3, door_r_opened, u4) -> 0.2
(u3, lost_r_key, u2) -> -0.1
(u4, entered_goal_room, u5) -> 0.3
(u4, got_ball, u5) -> 1
```

Source: <https://github.com/roger-creus/llms-rm-rl/blob/main/reward_machines/UnlockToUnlock/RM-vFINAL.txt>.
