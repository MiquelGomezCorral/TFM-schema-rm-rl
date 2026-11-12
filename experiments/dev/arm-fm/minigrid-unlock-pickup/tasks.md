# Tasks

## Reported task

`UP-1` — Acquire the matching key, unlock the door, and pick up the designated box in
the other room.

UnlockPickup appears in the paper's human-intervention analysis. The paper says the RM
was corrected to handle dropping the key after pickup, but it does not publish the
complete RM.

## Atomic pipeline probes

- `UP-A`: Eventually acquire the matching key.
- `UP-B`: Open the door only after acquiring the matching key.
- `UP-C`: Pick up the target box only after opening the door.

## Evidence

- Paper Appendix A.4 and A.5: `docs/ARM-FM/ARM-FM.md`.
- Official environment:
  <https://minigrid.farama.org/environments/minigrid/UnlockPickupEnv/>.
