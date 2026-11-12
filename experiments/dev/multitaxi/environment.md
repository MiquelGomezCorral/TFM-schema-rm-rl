# MultiTaxi with Two Passengers

## Environment

Taxis move on a grid map and carry passengers; each passenger has a start cell and a destination.
Per taxi, the default actions are `north`, `south`, `east`, `west`, `pickup`, `dropoff`;
`standby`, engine control and `refuel` exist only when configured. A generic `pickup` takes the
lowest-id passenger on the taxi's cell. A generic `dropoff` drops a passenger whose destination
is the taxi's cell, else the lowest-id passenger on board.

The library is configurable; its defaults are 1 taxi and 1 passenger. It is not known which
map, how many taxis, what capacity or which options the intended setup uses. The facts below
hold for the library defaults with two passengers.

## Objective and episode boundary

The episode ends when every passenger has arrived (the default). A passenger has arrived when it
stands on its destination and is not in a taxi. Passengers never start arrived (the default).

## Proposition semantics

The environment emits propositions only on pickup and delivery state transitions.
Pickup proposition `p1` or `p2` is emitted when that passenger enters the taxi.
Delivery proposition `d1` or `d2` is emitted when that passenger leaves the taxi at
their destination.

Reading of the passenger numbers: passenger 1 and passenger 2 are the library's first and
second passenger. It is not known whether the intended setup numbers them the same way.

| id | kind | true when |
|---|---|---|
| `p1`, `p2` | event | on the step passenger 1 or 2 is picked up |
| `d1`, `d2` | event | on the step passenger 1 or 2 is dropped on its own destination |

## Constraints

- `d1` cannot become true before `p1`: a passenger must be in a taxi to be dropped.
- `d2` cannot become true before `p2`: same reason.

## What the agent can and cannot do

- Can: pick up a passenger on the taxi's cell; drop a passenger anywhere, with `d` only on the passenger's destination.
- Can: have both passengers aboard at once with the default unbounded capacity (`p1`, `p2`, then `d1`, `d2`). It is not known whether the intended setup sets a capacity.
- Can: drop a passenger away from its destination and pick it up again, so `p1` can happen twice, unless the setup forbids intermediate dropoffs. It is not known whether the intended setup forbids them.
- Cannot: pick up a passenger already aboard or arrived; drop a passenger who is not aboard; pick up with a full taxi.
- `d1` happens at most once, and after it `p1` does not happen again: an arrived passenger cannot be picked up. Same for passenger 2.
- No order between the passengers by default: no pickup or dropoff order is set.
- One taxi performs one action per step, so with one taxi no two of `p1`, `p2`, `d1`, `d2` are true on the same step. With more taxis two events can share a step. It is not known how many taxis the intended setup has.
- Nothing follows the last `d`: the episode ends when all passengers have arrived.
- It is not known what map walls, fuel limits and collisions the intended setup has.

## Example trace

Library defaults with 2 passengers: the taxi starts at row 5, column 11; passenger 1 at (3, 6) going to (0, 3); passenger 2 at (4, 4) going to (2, 1). A real episode. 27 steps, 23 of them moves.

1. 7 moves, no proposition changes
2. `pickup` (step 8): `p1` true
3. 6 moves, no proposition changes
4. `dropoff` (step 15): `d1` true; passenger 1 has arrived
5. 5 moves, no proposition changes
6. `pickup` (step 21): `p2` true
7. 5 moves, no proposition changes
8. `dropoff` (step 27): `d2` true; the episode is done

Variant, same start, also a real episode: `pickup` (step 8): `p1` true. `dropoff` one move away (step 10): no proposition, passenger 1 is on the map again. `pickup` (step 11): `p1` true a second time. `dropoff` at its destination (step 19): `d1` true. Then `p2` (step 25) and `d2` (step 31), 31 steps.

## Propositions
- `p1`: Passenger 1 entered the taxi.
- `p2`: Passenger 2 entered the taxi.
- `d1`: Passenger 1 was delivered at the destination.
- `d2`: Passenger 2 was delivered at the destination.

## Example tasks

- Eventually deliver passengers 1 and 2.
- Eventually pick up passenger 1.
- Pick up passenger 1 before picking up passenger 2.
- Deliver passenger 1 before delivering passenger 2.
