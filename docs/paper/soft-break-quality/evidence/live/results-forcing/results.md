# Suite forcing

1 seed(s) per cell, target 3: no verdict, compare behaviour only.

## Runs

Time-limit asymmetry: FARM machines charge open items at any end; ARM-FM machines get 0 at the time limit.

| card | arm | learner | variant | seed | status | judged success, a rule fired | env success | judged success | raw judged success | machine too simple | episodes cannot start | cannot-start flag | non-empty judged success | least activated hard clause | untested rules | hard breaks | soft breaks | separate soft breaks | episodes with a soft break | idle plan soft breaks (soft-only card) | open at end | idle plan open at end (soft-only card) | label changes (soft-only card) | idle plan label changes (soft-only card) | first env success | last-3 eval success | env return | judged env return + | judged env return - | RM return | judged RM return + | judged RM return - | episode length | wall s | peak GB | machine-wrong |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lanes-rules | no-rm | ppo |  | 1 | finished (shared no-RM run of bench__forcing__lanes-guard__no-rm__ppo) |  | 0 | 0.7 | 0.7 |  | 0 | no | 0.7 |  |  | 0.3 | 1.42 | 10.58 | 1 |  | 0 |  |  |  | n/a | 0 | 17.62 | 17.65 | 0 |  |  |  | 300 | 2248.6 | 2.34 |  |
| lanes-rules | farm | ppo |  | 1 | finished |  | 0.03 | 0 | 0 | no | 0 | no | 0 |  |  | 1 | 0.55 | 1.05 | 0.54 |  | 0 |  |  |  | n/a | 0.01 | 1.04 | 1.18 | 0 | -1.6 | 0 | -1.525 | 79.5 | 1762.3 | 2.35 |  |

## Per card, across arms

### lanes-rules

Task: Never let a zombie through the top lane. Try not to let zombies through the other lanes, and try not to step on plants.

Clauses: Absence(top_breach) hard; Absence(side_breach) soft; Absence(plant_trampled) soft

Machines: farm: experiments/benchmark/forcing/bundles/farm/lanes-rules/reward_machine.txt

Time-limit asymmetry: FARM machines charge open items at any end; ARM-FM machines get 0 at the time limit.

| arm | learner | variant | seeds finished | judged success, a rule fired | env success | judged success | raw judged success | machine too simple | episodes cannot start | cannot-start flag | non-empty judged success | least activated hard clause | untested rules | hard breaks | soft breaks | separate soft breaks | episodes with a soft break | idle plan soft breaks (soft-only card) | open at end | idle plan open at end (soft-only card) | label changes (soft-only card) | idle plan label changes (soft-only card) | first env success | last-3 eval success | env return | judged env return + | judged env return - | RM return | judged RM return + | judged RM return - | episode length | wall s | peak GB | machine-wrong |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no-rm | ppo |  | 1/1 |  | 0 | 0.7 | 0.7 |  | 0 | no | 0.7 |  |  | 0.3 | 1.42 | 10.58 | 1 |  | 0 |  |  |  | n/a | 0 | 17.62 | 17.65 | 0 |  |  |  | 300 | 2248.6 | 2.34 |  |
| farm | ppo |  | 1/1 |  | 0.03 | 0 | 0 | no | 0 | no | 0 |  |  | 1 | 0.55 | 1.05 | 0.54 |  | 0 |  |  |  | n/a | 0.01 | 1.04 | 1.18 | 0 | -1.6 | 0 | -1.525 | 79.5 | 1762.3 | 2.35 |  |
