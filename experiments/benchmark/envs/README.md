# Benchmark environments

One folder per environment. The task cards in `../base`, `../templates` and `../complex` point
at `<folder>/environment.md` through `env.description`.

Rule: `environment.md` holds facts; implementation is in `environment-code.md`.

| Folder | Gym id | Propositions |
|---|---|---|
| `minigrid-doorkey` | `MiniGrid-DoorKey-8x8-v0` | `has_key`, `door_open`, `at_goal`, `key_lost` |
| `minigrid-unlock-pickup` | `MiniGrid-UnlockPickup-v0` | `has_door_key`, `door_open`, `target_picked_up`, `key_lost` |
| `minigrid-blocked-unlock-pickup` | `MiniGrid-BlockedUnlockPickup-v0` | `blocker_moved`, `has_door_key`, `door_open`, `target_picked_up`, `key_lost` |
| `minigrid-key-corridor` | `MiniGrid-KeyCorridorS6R3-v0` | `key_found`, `has_matching_key`, `target_door_open`, `target_room_entered`, `target_picked_up` |
| `service-room` | `MiniGrid-ServiceRoom-v0` | `siren_ringing`, `switch_toggled`, `holding_box`, `box_fell`, `at_exit` |

- The four MiniGrid folders are verbatim copies of the same-named folders in `examples/arm-fm/`
  at commit `42bc2f0`.
- The `service-room` folder is added by slice S3 (the event room). Until it is merged, the
  service-room cards point at a file that does not exist yet.
