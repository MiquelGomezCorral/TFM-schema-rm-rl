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

The stored bundles predate the hard ceiling and the default pays of 2026-11-19, and are rebuilt at
the freeze. Under today's default switches (300-step limit, gamma 0.99) the same script compiles
these machines (built in memory with no files written, 2026-11-20):

| Card | States | Notes |
|---|---|---|
| `lanes-guard` | 2 | `u0` --`top_breach`--> `u1` rejecting, -10 |
| `lanes-rules` | 2 | `u0` --`top_breach`--> `u1` rejecting, -96.0959: the hard ceiling prices the hard break above the most a 300-step episode can lose to soft breaks, discounted. A side breach or a trampled plant pays -1 on a loop back to `u0`, both on one step -2 |
| `keygift-hard`, `keygift-soft` | 2 | `u0` --key held, door shut--> `u1` (-1), --door open--> `u0` (+1). No end charge (the end judgment is off by default), so the two machines are the same; hard and soft differ only in how the run is judged |

## Checks

`PYTHONPATH=app python experiments/benchmark/scripts/check_forcing.py --seeds 20 --bundles` (about 15 s): 51 checks, all pass (reset seeds 1 to 20; random agents 6000 steps).

- The two environments against their `environment.md`: layout, observation, rhythm, the 27-step walk of an unstopped zombie, spawn rise, plants, kills, determinism, the gift rules, the 10-action door distance, the label constraints.
- `tasks.json` breaks no card contract; the four bundles validate complete.
- Trace bank (`trace-bank --tasks .../tasks.json`): 4 cards, 33 of 33 plan runs ok. Plan check of each bundle (`check_card_plans`): all four pass (the solving plan never enters the well; a wrong plan ends in the well, ends owing, or pays a soft penalty).
- `run-suite --dry-run`: 8 runs (6 start, 2 share the no-RM run of the same level).

Mean RM return per agent, 20 seeds, with the machines of today's default switches above and the
runs' `time_limit_penalty` of 0 (`RM_TIME_LIMIT_PENALTY` in `app/scripts/run_suite.py`, which
`check_forcing.py` also uses; these machines have no end judgment, so the Configuration default of
-5 would land on every cut episode). Well = episodes ended in the rejecting state; env ok = the
environment's own `success` flag:

| Card | Agent | RM return | Well | Steps | Env ok | Side breaches | Plants | Kills |
|---|---|---|---|---|---|---|---|---|
| `lanes-guard` | idle | -10.00 | 20/20 | 74 | 0.00 | 1.4 | 0.0 | 0.0 |
| `lanes-guard` | random | -10.00 | 20/20 | 74 | 0.00 | 1.1 | 0.1 | 0.2 |
| `lanes-guard` | guard | -0.50 | 1/20 | 295 | 0.95 | 4.5 | 0.0 | 20.4 |
| `lanes-rules` | idle | -97.45 | 20/20 | 74 | 0.00 | 1.4 | 0.0 | 0.0 |
| `lanes-rules` | random | -97.30 | 20/20 | 74 | 0.00 | 1.1 | 0.1 | 0.2 |
| `lanes-rules` | guard | -9.35 | 1/20 | 295 | 0.95 | 4.5 | 0.0 | 20.4 |
| `lanes-rules` | guard, top lane ignored | -96.10 | 20/20 | 74 | 0.00 | 0.0 | 0.0 | 1.9 |
| `keygift-hard` | idle | -1.00 | 0/20 | 300 | 0.00 | | | |
| `keygift-hard` | random | -0.90 | 0/20 | 300 | 0.10 | | | |
| `keygift-hard` | guard | 0.00 | 0/20 | 300 | 1.00 | | | |
| `keygift-soft` | idle | -1.00 | 0/20 | 300 | 0.00 | | | |
| `keygift-soft` | random | -0.90 | 0/20 | 300 | 0.10 | | | |
| `keygift-soft` | guard | 0.00 | 0/20 | 300 | 1.00 | | | |

How these were measured (card fixes 2026-11-20): `build_forcing_bundles.py`'s compile path run in
memory, then `check_forcing.py`'s `check_bundles` agents on those machines. The stored bundles still
give the old numbers; once they are rebuilt (`build_forcing_bundles.py --overwrite`, then
`embed-larm`), `check_forcing.py --seeds 20 --bundles` prints this table.

Doing nothing fails every card: it ends in the well at the first top breach (lanes) or leaves the promise open (key gift). The scripted guard keeps the hard rule on 19 of 20 seeds on Lanes (37 of 40 on seeds 1 to 40): a pack of top-lane zombies that comes while it is far away gets through. It keeps the key gift rule on every seed.

### Guarding beats ending early on `lanes-rules`

With the old flat pays (hard breach -1, soft breach -0.5) an agent that let the top lane be breached ended the episode early and paid less than the guard (-1.00 against -2.23, 15 of 20 seeds). The hard ceiling (default since 2026-11-19) removed that: the hard breach now costs 96.0959, more than a soft break on every one of 300 steps would cost discounted at gamma 0.99, and each soft breach costs 1. The guard that holds the top lane loses on average 4.5 side-lane zombies in 300 steps (`lanes-rules`, 20 seeds, the machines above):

| Agent | Mean RM return | Scores more than the guard |
|---|---|---|
| guard (keeps the top lane) | -9.35 | |
| idle | -97.45 | 0 of 20 seeds |
| guard that ignores the top lane | -96.10 | 1 of 20 seeds (the guard itself falls in the well on 1 of 20) |

On seeds 1 to 40: idle 2 of 40, the guard that ignores the top lane 3 of 40 (the guard falls in the well on 3 of 40). Keeping the hard rule now pays more than giving it up.

## Training

Arms `no-rm` and `farm`, seeds 1 to 3, PPO s07, 1.5M steps (`runs.yaml`). The Lanes observation is the whole 11 x 11 grid (`ImgObsWrapper` plus `MiniGridCNN` work unchanged); the training log's "environment success" is always 0 on both levels because they never terminate (the trainer counts a terminated step with a positive reward); the environment's own `success` property (`env.unwrapped.success`) is what the check script reads. Live validation is pending.

Reproduce: `PYTHONPATH=app python app/main.py trace-bank --tasks experiments/benchmark/forcing/tasks.json --output <dir>`, `PYTHONPATH=app python experiments/benchmark/scripts/check_forcing.py --seeds 20 --bundles`, and for the bundles `PYTHONPATH=app python experiments/benchmark/scripts/build_forcing_bundles.py --overwrite` followed by `embed-larm --bundle <folder> --embedding-server` for each card (MONA on the PATH; the embedding server on 127.0.0.1:8934).

## Contents

- `tasks.json`: the cards.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.
- `bundles/farm/<card-id>/`: the generated machines.
