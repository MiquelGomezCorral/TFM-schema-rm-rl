# Published Reward Machines

## `KC-RM-1`

```text
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
TRANSITION_FUNCTION:
(u0, on_purple_door_and_not_has_key) -> u1
(u0, else) -> u0
(u1, got_key) -> u2
(u1, else) -> u1
(u2, on_purple_door_and_has_key) -> u3
(u2, opened_red_door) -> u4
(u2, else) -> u2
(u3, opened_red_door) -> u4
(u3, else) -> u3

REWARD_FUNCTION:
(u0, on_purple_door_and_not_has_key, u1) -> 0.1
(u1, got_key, u2) -> 0.2
(u2, on_purple_door_and_has_key, u3) -> 0.25
(u2, opened_red_door, u4) -> 0.5
(u3, opened_red_door, u4) -> 0.5
```

Source: <https://github.com/roger-creus/llms-rm-rl/blob/main/reward_machines/KeyCorridorS6R3/RM-vFINAL.txt>.

The artifact omits `REWARD_MACHINE:` and a final-state self-loop. It also terminates
on opening the red door rather than explicitly detecting target pickup. The block is
preserved exactly for comparison.
