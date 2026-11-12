# Task–RM Pairs

## Source-recovered pair

- Task: `DK-1` in `tasks.md`.
- Reward Machine: `DK-RM-1` in `reward-machines.md`.
- Pair status: exact source association; both occur in the released generation trace.

## Proposition translation

| Published RM event | Local environment proposition |
|---|---|
| `has_key` | `has_key` |
| `is_door_in_env_open` | `door_open` |
| `not_has_key` | `key_lost` |
| `at_goal` | `at_goal` |

The translation preserves meaning but prevents byte-for-byte output comparison unless
the same event names are used.
