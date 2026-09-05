# Task–RM Pairs

## Source-recovered pair

- Task: `BUP-1` in `tasks.md`.
- Reward Machine: `BUP-RM-1` in `reward-machines.md`.
- Pair status: exact source association; both occur in the released generation trace.
  The task text in `tasks.md` normalizes the trace's wording without changing its
  staged logic.

## Proposition translation

| Published RM event | Local environment proposition |
|---|---|
| `has_ball` | `blocker_moved` |
| `has_key` | `has_door_key` |
| `door_unlocked` | `door_open` |
| `no_key` | `key_lost` |
| `has_box` | `target_picked_up` |

`has_ball` is stricter than `blocker_moved`; exact reproduction requires the original
carrying-the-ball predicate rather than the broader local proposition.
