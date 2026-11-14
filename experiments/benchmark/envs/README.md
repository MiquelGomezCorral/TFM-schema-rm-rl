# Benchmark environments

One folder per environment. The task cards in `../base`, `../templates` and `../complex` point
at `<folder>/environment.md` through `env.description`.

Rule: `environment.md` holds facts; implementation is in `environment-code.md`.

| Folder | Gym id | Propositions |
|---|---|---|
| `minigrid-doorkey` | `MiniGrid-DoorKey-8x8-v0` | |
| `minigrid-unlock-pickup` | `MiniGrid-UnlockPickup-v0` | |
| `minigrid-blocked-unlock-pickup` | `MiniGrid-BlockedUnlockPickup-v0` | |
| `minigrid-key-corridor` | `MiniGrid-KeyCorridorS6R3-v0` | |
| `service-room` | `MiniGrid-ServiceRoom-v0` | `siren_ringing`, `switch_toggled`, `holding_box`, `box_fell`, `at_exit` |
| `service-room-carry` | `MiniGrid-ServiceRoom-v0` with `carry=True` | the same five; the agent starts holding the box (cards in `../box-carry`) |
| `shop` | `MiniGrid-Shop-v0` | `siren_ringing`, `holding_food`, `switch_toggled`, `client_arrived`, `order_taken`, `food_prepared`, `order_served`, `food_fell`, `served_while_ringing`; no goal, always busy (cards in `../shop`) |
| `shop-pot` | `MiniGrid-Shop-Pot-v0` | the nine of `shop` plus `pot_boiling`, `stove_fixed` (cards in `../shop`) |
| `minigrid-blocked-unlock-pickup-cleared` | `MiniGrid-BlockedUnlockPickup-Cleared-v0` | the same five as the plain level; the ball starts away from the door (cards in `../forced-start`) |
| `minigrid-unlock-pickup-key-held` | `MiniGrid-UnlockPickup-KeyHeld-v0` | the same four as the plain level; the agent starts holding the key (cards in `../forced-start`) |

Propositions of the four MiniGrid envs live in each env's `environment.md`, section `## Propositions`; the service-room row lists them here because its folder is added by S3.

- The four MiniGrid folders are verbatim copies of the same-named folders in `examples/arm-fm/`
  at commit `42bc2f0`.
- The `service-room` folder is added by slice S3 (the event room). Until it is merged, the
  service-room cards point at a file that does not exist yet. Their plans are unverified until
  slice S3 merges and the trace bank runs.
