# MultiTaxi with Two Passengers: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Official source: <https://github.com/CLAIR-LAB-TECHNION/multi-taxi>, version `0.5.0` (commit `6a3dde1`), PettingZoo parallel API.
- Gym id and configuration the facts assume: `unknown`. The library is configurable; its defaults are 1 taxi and 1 passenger. Number of taxis, map and capacity of the benchmark setup: `unknown`.
- This repository has no MultiTaxi adapter (nothing under `app/` mentions it). The library imports in `RM_RL_env` from a read-only copy of that commit with `PYTHONPATH` set (`pettingzoo` 1.27.0 is already installed; nothing was installed). The traces are real runs of `MultiTaxiEnv(num_passengers=2)` with every other option at the library default, driven by a scripted solver [run: `multitaxi_run.py`, log `multitaxi_run.log`]. That setup is the assumption of `environment.md`, not the benchmark's.
- `[code: file:function]` is the library at that commit (`multi_taxi/env/MultiTaxiEnv.py` unless named). `[run: script]` is `multitaxi_run.py`. `unknown` means no source says.

## Truth conditions in code

No labeling expression exists: there is no MultiTaxi adapter and no labeling API. The library itself emits the events at pickup and delivery transitions. `d1` and `d2` correspond to the library's `FINAL_DROPOFF` outcome. No code location is recorded for the emitted pickup event.

## Evidence

Environment
- Taxis, grid map, passengers with start cell and destination: [code: MultiTaxiEnv docstring].
- Default actions, `standby`, engine control and `refuel` only when configured: [code: utils/types.py:Action, config.py].
- Generic `pickup` and `dropoff` rules: [code: `__generic_pickup`, `__generic_dropoff`].

Objective and episode boundary
- Episode ends when every passenger has arrived (`pickup_only` off, the default): [code: `objective_achieved`].
- Arrived means on the destination and not in a taxi: [code: world/entities.py:Passenger.arrived].
- Passengers never start arrived (default): [code: config.py:DEFAULT_ALLOW_ARRIVED_PASSENGERS_ON_RESET].

Constraints
- `d1` after `p1`, `d2` after `p2`: [code: `__passenger_can_be_dropped_off`; run: `multitaxi_run.py`, 3 episodes].

What the agent can and cannot do
- Pick up and drop rules: [code: `__generic_pickup`, `__generic_dropoff`].
- Both passengers aboard with default unbounded capacity: [code: config.py; run: `multitaxi_run.py`, third episode].
- Drop away from the destination and pick up again, unless `no_intermediate_dropoff` is set: [code: `__generic_dropoff`; run: `multitaxi_run.py`, second episode].
- Cannot pick up a passenger already aboard or arrived, drop one not aboard, pick up with a full taxi: [code: `__passenger_can_be_picked_up`, `__generic_pickup`].
- `d1` at most once, no `p1` after it: [code: `__passenger_can_be_picked_up`].
- No order between passengers: `pickup_order` and `dropoff_order` are empty [code: config.py].
- One action per taxi per step: [code: `__step_from_state`, one action per taxi].
- Nothing follows the last `d`: [code: `objective_achieved`; run: `multitaxi_run.py`, `env_done()` true on that step].
- Passenger numbering: `environment.md` reads "1" and "2" as library ids 0 and 1.
- Map walls, fuel limits, collisions, number of taxis, capacity, `no_intermediate_dropoff`: `unknown` for the benchmark.

Example trace
- Seed 0, library defaults, 2 passengers, scripted solver on shortest paths: [run: `multitaxi_run.py`, log `multitaxi_run.log`].
- Variant, second episode: [run: same].
