# MultiTaxi with Two Passengers

The environment emits propositions only on pickup and delivery state transitions.
Pickup proposition `p1` or `p2` is emitted when that passenger enters the taxi.
Delivery proposition `d1` or `d2` is emitted when that passenger leaves the taxi at
their destination.

## Propositions
- `p1`: Passenger 1 entered the taxi.
- `p2`: Passenger 2 entered the taxi.
- `d1`: Passenger 1 was delivered at the destination.
- `d2`: Passenger 2 was delivered at the destination.
