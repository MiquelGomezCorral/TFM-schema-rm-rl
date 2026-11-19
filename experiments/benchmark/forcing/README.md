# Forcing suite

Four cards on two MiniGrid levels where the world forces the trigger of the rule, so an agent that does nothing fails it. The older suites pass by doing nothing whenever the trigger is something the agent does (`../forced-start` fixed that with a forced start); here the trigger keeps coming during the episode.

| Level | Environment (facts) | What the world does | Source |
|---|---|---|---|
| `MiniGrid-Lanes-v0` | `../envs/minigrid-lanes/` | zombies enter three lanes by themselves and walk to the left end, one cell every 3 steps; a plant sprouts now and then | `app/src/arm_fm/forcing_envs.py:LanesEnv` |
| `MiniGrid-KeyGift-v0` | `../envs/minigrid-key-gift/` | a key lands in the empty hands about 1 step in 30; it cannot be dropped, the door uses it up and shuts 10 steps later | `app/src/arm_fm/forcing_envs.py:KeyGiftEnv` |

Both are seeded (`reset(seed=s)` draws the whole schedule), have no goal and end only at the 300-step limit.

## The cards

| Card | Level | Task | Clauses |
|---|---|---|---|
| `lanes-guard` | Lanes | Never let a zombie through the top lane. | 0 `Absence(top_breach)` hard |
| `lanes-rules` | Lanes | The same, then "try not to let zombies through the other lanes, and try not to step on plants". | 0 `Absence(top_breach)` hard, 1 `Absence(side_breach)` soft, 2 `Absence(plant_trampled)` soft |
| `keygift-hard` | KeyGift | Whenever you are holding the key, open the door. | 0 `Response(has_door_key, door_open)` hard |
| `keygift-soft` | KeyGift | Whenever you are holding the key, try to open the door. | 0 `Response(has_door_key, door_open)` soft |

Plans (`tasks.json`, `event_seeds`: lanes 1, 3, 4; key gift 1, 2, 3). Solving plan: the scripted guard (`{"do": "policy", "name": "guard"}` or `"keygift"`). Wrong plans: do nothing for 300 steps (every card); the guard that ignores the top lane (`ignore: ["top"]`, both lanes cards); on `lanes-rules` also the guard that walks onto every plant after the top lane (`ignore: ["plants"]`, breaks the two soft rules). The lanes seeds are those where the wrong plans break exactly the clauses they promise: with `ignore: ["top"]` the side-lane rule also breaks on seeds 2 and 10.

## Machines and bundles

FARM only; `bundles/farm/<card-id>/` is built with no model call by `../scripts/build_forcing_bundles.py` (the card's clauses through the project compiler with the default reward switches, a hand-written `labeling.py` with only the machine's propositions, hand-written state descriptions) and embedded with `embed-larm --embedding-server` (nomic-embed-text, 768 dimensions). Each bundle validates with `validate(require_complete=True)`. Provenance in each manifest says `hand-written`.

| Card | States | Notes |
|---|---|---|
| `lanes-guard` | 2 | `u0` --`top_breach`--> `u1` rejecting, -1 |
| `lanes-rules` | 5 | rejecting `u1`; `u2`, `u3`, `u4` are the soft breaks (side lane, plant, both), -0.5 each; they return to `u0` |
| `keygift-hard`, `keygift-soft` | 2 | `u0` --key held, door shut--> `u1` (-0.1), --door open--> `u0` (+0.1); the open promise is charged at the end (hard -1, soft -0.5) |

## Checks

`PYTHONPATH=app python experiments/benchmark/scripts/check_forcing.py --seeds 20 --bundles` (about 15 s): 51 checks, all pass (reset seeds 1 to 20; random agents 6000 steps).

- The two environments against their `environment.md`: layout, observation, rhythm, the 27-step walk of an unstopped zombie, spawn rise, plants, kills, determinism, the gift rules, the 10-action door distance, the label constraints.
- `tasks.json` breaks no card contract; the four bundles validate complete.
- Trace bank (`trace-bank --tasks .../tasks.json`): 4 cards, 33 of 33 plan runs ok. Plan check of each bundle (`check_card_plans`): all four pass (the solving plan never enters the well; a wrong plan ends in the well, ends owing, or pays a soft penalty).
- `run-suite --dry-run`: 8 runs (6 start, 2 share the no-RM run of the same level).

Mean RM return per agent, 20 seeds (well = episodes ended in the rejecting state; env ok = the environment's own `success` flag):

| Card | Agent | RM return | Well | Steps | Env ok | Side breaches | Plants | Kills |
|---|---|---|---|---|---|---|---|---|
| `lanes-guard` | idle | -1.00 | 20/20 | 74 | 0.00 | 1.4 | 0.0 | 0.0 |
| `lanes-guard` | random | -1.00 | 20/20 | 74 | 0.00 | 1.1 | 0.1 | 0.2 |
| `lanes-guard` | guard | -0.05 | 1/20 | 295 | 0.95 | 4.5 | 0.0 | 20.4 |
| `lanes-rules` | idle | -1.65 | 20/20 | 74 | 0.00 | 1.4 | 0.0 | 0.0 |
| `lanes-rules` | random | -1.60 | 20/20 | 74 | 0.00 | 1.1 | 0.1 | 0.2 |
| `lanes-rules` | guard | -2.23 | 1/20 | 295 | 0.95 | 4.5 | 0.0 | 20.4 |
| `lanes-rules` | guard, top lane ignored | -1.00 | 20/20 | 74 | 0.00 | 0.0 | 0.0 | 1.9 |
| `keygift-hard` | idle | -1.10 | 0/20 | 300 | 0.00 | | | |
| `keygift-hard` | random | -0.99 | 0/20 | 300 | 0.10 | | | |
| `keygift-hard` | guard | 0.00 | 0/20 | 300 | 1.00 | | | |
| `keygift-soft` | idle | -0.60 | 0/20 | 300 | 0.00 | | | |
| `keygift-soft` | random | -0.54 | 0/20 | 300 | 0.10 | | | |
| `keygift-soft` | guard | 0.00 | 0/20 | 300 | 1.00 | | | |

Doing nothing fails every card: it ends in the well at the first top breach (lanes) or leaves the promise open (key gift). The scripted guard keeps the hard rule on 19 of 20 seeds on Lanes (37 of 40 on seeds 1 to 40): a pack of top-lane zombies that comes while it is far away gets through. It keeps the key gift rule on every seed.

### Ending early beats guarding on `lanes-rules`

Under the default switches a hard breach ends the episode in the well with a penalty of 1, while a soft breach pays -0.5 each time and the episode goes on. The guard that holds the top lane loses on average 4.5 side-lane zombies in 300 steps, so it pays about -2.2. An agent that lets the top lane be breached ends the episode early and pays less (`lanes-rules`, 20 seeds):

| Agent | Mean RM return | Scores more than the guard |
|---|---|---|
| guard (keeps the top lane) | -2.23 | |
| idle | -1.65 | 11 of 20 seeds |
| guard that ignores the top lane | -1.00 | 15 of 20 seeds |

So the machine of `lanes-rules` pays more for giving up the hard rule than for keeping it, and a trained agent can learn that. Not fixed: the switches are the project's, and the comparison is a finding to read before the runs.

## Training

Arms `no-rm` and `farm`, seed 1, PPO s07, 1.5M steps (`runs.yaml`; target seeds 1 to 3). The Lanes observation is the whole 11 x 11 grid (`ImgObsWrapper` plus `MiniGridCNN` work unchanged); the training log's "environment success" is always 0 on both levels because they never terminate (the trainer counts a terminated step with a positive reward); the environment's own `success` property (`env.unwrapped.success`) is what the check script reads. Live validation is pending.

Reproduce: `PYTHONPATH=app python app/main.py trace-bank --tasks experiments/benchmark/forcing/tasks.json --output <dir>`, `PYTHONPATH=app python experiments/benchmark/scripts/check_forcing.py --seeds 20 --bundles`, and for the bundles `PYTHONPATH=app python experiments/benchmark/scripts/build_forcing_bundles.py --overwrite` followed by `embed-larm --bundle <folder> --embedding-server` for each card (MONA on the PATH; the embedding server on 127.0.0.1:8934).

## Contents

- `tasks.json`: the cards.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.
- `bundles/farm/<card-id>/`: the generated machines.
