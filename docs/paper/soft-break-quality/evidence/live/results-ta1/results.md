# Suite ta1-cx-goal-one-rule

1 seed(s) per cell, target 3: no verdict, compare behaviour only.

## Runs

Time-limit asymmetry: FARM machines charge open items at any end; ARM-FM machines get 0 at the time limit.

| card | arm | learner | variant | seed | status | judged success, a rule fired | env success | judged success | raw judged success | machine too simple | episodes cannot start | cannot-start flag | non-empty judged success | least activated hard clause | untested rules | hard breaks | soft breaks | separate soft breaks | episodes with a soft break | idle plan soft breaks (soft-only card) | open at end | idle plan open at end (soft-only card) | label changes (soft-only card) | idle plan label changes (soft-only card) | first env success | last-3 eval success | env return | judged env return + | judged env return - | RM return | judged RM return + | judged RM return - | episode length | wall s | peak GB | machine-wrong |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cx-goal-one-rule | arm-fm | ppo |  | 1 | finished | 0 | 0 | 0 | 0 | no | 0 | no | 0 | 0 | Precedence(door_open, target_picked_up) 0.00; Existence(target_picked_up) 0.00 | 0 | 0.84 | 236.53 | 0.84 |  | 1 |  |  |  | n/a | 0 | 0 | 0 | 0 | 25.196 | 23.78 | -0.001 | 576 | 4965.8 | 2.36 |  |
| cx-goal-one-rule | no-rm | ppo |  | 1 | finished (shared no-RM run of bench__closed-templates__tpl-absence-1-goal__no-rm__ppo) | 0 | 0 | 0 | 0 |  | 0 | no | 0 | 0 | Precedence(door_open, target_picked_up) 0.00; Existence(target_picked_up) 0.00 | 0 | 0 | 0 | 0 |  | 1 |  |  |  | n/a | 0 | 0 | 0 | 0 |  |  |  | 576 | 3822.3 | 2.35 |  |

## Per card, across arms

### cx-goal-one-rule

Task: Open the door and then pick up the box in the other room, and try not to drop the key while the door is still closed.

Clauses: Precedence(door_open, target_picked_up) hard; Existence(target_picked_up) hard; Absence(key_lost) soft

Machines: arm-fm: /home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl/experiments/benchmark/complex/bundles/arm-fm/cx-goal-one-rule/reward_machine.txt

Time-limit asymmetry: FARM machines charge open items at any end; ARM-FM machines get 0 at the time limit.

| arm | learner | variant | seeds finished | judged success, a rule fired | env success | judged success | raw judged success | machine too simple | episodes cannot start | cannot-start flag | non-empty judged success | least activated hard clause | untested rules | hard breaks | soft breaks | separate soft breaks | episodes with a soft break | idle plan soft breaks (soft-only card) | open at end | idle plan open at end (soft-only card) | label changes (soft-only card) | idle plan label changes (soft-only card) | first env success | last-3 eval success | env return | judged env return + | judged env return - | RM return | judged RM return + | judged RM return - | episode length | wall s | peak GB | machine-wrong |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arm-fm | ppo |  | 1/1 | 0 | 0 | 0 | 0 | no | 0 | no | 0 | 0 | Precedence(door_open, target_picked_up) 0.00; Existence(target_picked_up) 0.00 | 0 | 0.84 | 236.53 | 0.84 |  | 1 |  |  |  | n/a | 0 | 0 | 0 | 0 | 25.196 | 23.78 | -0.001 | 576 | 4965.8 | 2.36 |  |
| no-rm | ppo |  | 1/1 | 0 | 0 | 0 | 0 |  | 0 | no | 0 | 0 | Precedence(door_open, target_picked_up) 0.00; Existence(target_picked_up) 0.00 | 0 | 0 | 0 | 0 |  | 1 |  |  |  | n/a | 0 | 0 | 0 | 0 |  |  |  | 576 | 3822.3 | 2.35 |  |
