# MultiTaxi with Two Passengers

## Source and runtime

- Official source: <https://github.com/CLAIR-LAB-TECHNION/multi-taxi>, version `0.5.0` (commit `6a3dde1`), PettingZoo parallel API.
- Gym id and configuration this file assumes: `unknown`. The library is configurable; its defaults are 1 taxi and 1 passenger. Number of taxis, map and capacity of the benchmark setup: `unknown`.
- This repository has no MultiTaxi adapter (nothing under `app/` mentions it). The library imports in `RM_RL_env` from a read-only copy of that commit with `PYTHONPATH` set (`pettingzoo` 1.27.0 is already installed; nothing was installed). The traces below are real runs of `MultiTaxiEnv(num_passengers=2)` with every other option at the library default, driven by a scripted solver [run: `multitaxi_run.py`, log `multitaxi_run.log`]. That setup is this file's assumption, not the benchmark's.
- Evidence tags: `[code: file:function]` is the library at that commit (`multi_taxi/env/MultiTaxiEnv.py` unless named); `[run: script]` is `multitaxi_run.py`; `unknown` means no source says.

## Environment

Taxis move on a grid map and carry passengers; each passenger has a start cell and a destination [code: MultiTaxiEnv docstring]. Per taxi, the default actions are `north`, `south`, `east`, `west`, `pickup`, `dropoff`; `standby`, engine control and `refuel` exist only when configured [code: utils/types.py:Action, config.py]. A generic `pickup` takes the lowest-id passenger on the taxi's cell. A generic `dropoff` drops a passenger whose destination is the taxi's cell, else the lowest-id passenger on board [code: `__generic_pickup`, `__generic_dropoff`].

## Objective and episode boundary

The episode ends when every passenger has arrived (`pickup_only` off, the default) [code: `objective_achieved`]. A passenger has arrived when it stands on its destination and is not in a taxi [code: world/entities.py:Passenger.arrived]. Passengers never start arrived (default) [code: config.py:DEFAULT_ALLOW_ARRIVED_PASSENGERS_ON_RESET].

## Proposition semantics

The environment emits propositions only on pickup and delivery state transitions.
Pickup proposition `p1` or `p2` is emitted when that passenger enters the taxi.
Delivery proposition `d1` or `d2` is emitted when that passenger leaves the taxi at
their destination.

| id | kind | true when |
|---|---|---|
| `p1`, `p2` | event | on the step passenger 1 or 2 is picked up |
| `d1`, `d2` | event | on the step passenger 1 or 2 is dropped on its own destination (`FINAL_DROPOFF`) |

## Constraints

- `d1` cannot become true before `p1`: a passenger must be in a taxi to be dropped [code: `__passenger_can_be_dropped_off`; run: `multitaxi_run.py`, 3 episodes].
- `d2` cannot become true before `p2`: same reason [code: `__passenger_can_be_dropped_off`; run: same].

## What the agent can and cannot do

- Can: pick up a passenger on the taxi's cell; drop a passenger anywhere, with `d` only on the passenger's destination [code: `__generic_pickup`, `__generic_dropoff`].
- Can: have both passengers aboard at once with the default unbounded capacity (`p1`, `p2`, then `d1`, `d2`) [code: config.py; run: `multitaxi_run.py`, third episode]. Whether the benchmark sets a capacity: `unknown`.
- Can: drop a passenger away from its destination and pick it up again, so `p1` can happen twice, unless `no_intermediate_dropoff` is set [code: `__generic_dropoff`; run: `multitaxi_run.py`, second episode]. Whether the benchmark sets it: `unknown`.
- Cannot: pick up a passenger already aboard or arrived; drop a passenger who is not aboard; pick up with a full taxi [code: `__passenger_can_be_picked_up`, `__generic_pickup`].
- `d1` happens at most once, and after it `p1` does not happen again: an arrived passenger cannot be picked up [code: `__passenger_can_be_picked_up`]. Same for passenger 2.
- No order between the passengers by default: `pickup_order` and `dropoff_order` are empty [code: config.py].
- One taxi performs one action per step, so with one taxi no two of `p1`, `p2`, `d1`, `d2` are true on the same step. With more taxis two events can share a step. Number of taxis: `unknown` [code: `__step_from_state`, one action per taxi].
- Nothing follows the last `d`: the episode ends when all passengers have arrived [code: `objective_achieved`; run: `multitaxi_run.py`, `env_done()` true on that step].
- Unknown: map walls, fuel limits and collisions of the setup used. Which passenger is "1" and which "2": this file reads them as library ids 0 and 1, `unknown` for the benchmark.

## Example trace

Library defaults with 2 passengers, seed 0: the taxi starts at row 5, column 11; passenger 1 at (3, 6) going to (0, 3); passenger 2 at (4, 4) going to (2, 1). Scripted solver, shortest paths [run: `multitaxi_run.py`, log `multitaxi_run.log`]. 27 steps, 23 of them moves.

1. 7 moves, no proposition changes
2. `pickup` (step 8): `p1` true
3. 6 moves, no proposition changes
4. `dropoff` (step 15): `d1` true; passenger 1 has arrived
5. 5 moves, no proposition changes
6. `pickup` (step 21): `p2` true
7. 5 moves, no proposition changes
8. `dropoff` (step 27): `d2` true; the episode is done

Variant, same seed [run: same, second episode]: `pickup` (step 8): `p1` true. `dropoff` one move away (step 10): no proposition, passenger 1 is on the map again. `pickup` (step 11): `p1` true a second time. `dropoff` at its destination (step 19): `d1` true. Then `p2` (step 25) and `d2` (step 31), 31 steps.

## Propositions
- `p1`: Passenger 1 entered the taxi.
- `p2`: Passenger 2 entered the taxi.
- `d1`: Passenger 1 was delivered at the destination.
- `d2`: Passenger 2 was delivered at the destination.
