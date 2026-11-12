# Task–RM Pairs

## Inferred pair

- Task: `KC-1` in `tasks.md`.
- Reward Machine: `KC-RM-1` in `reward-machines.md`.
- Pair status: inferred from the paper environment description and the published RM.

The repository contains both artifacts for KeyCorridor S6R3, but its generation trace
uses an unrelated DoorKey mission. Therefore, the original task–RM input pair is not
recoverable exactly.

## Proposition translation

| Published RM event | Closest local proposition |
|---|---|
| `got_key` | `has_matching_key` |
| `opened_red_door` | `target_door_open` |
| `on_purple_door_and_not_has_key` | no exact equivalent |
| `on_purple_door_and_has_key` | no exact equivalent |

The published colors and doorway-position events cannot be reconstructed from the
role-based local vocabulary without adding propositions.
