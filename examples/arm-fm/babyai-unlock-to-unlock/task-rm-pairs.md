# Task–RM Pairs

## Source-recovered pair

- Task: `UTU-1` in `tasks.md`.
- Reward Machine: `UTU-RM-1` in `reward-machines.md`.
- Pair status: exact source association; the mission and RM occur together in the
  released trace. The task text in `tasks.md` normalizes the trace's wording and uses
  role names because the environment randomizes colors.

## Proposition translation

| Published RM event | Local environment proposition |
|---|---|
| `got_y_key` | `has_prerequisite_key` |
| `door_y_opened` | `prerequisite_door_open` |
| `lost_y_key` | `required_key_lost` in the prerequisite stage |
| `got_r_key` | `has_target_door_key` |
| `door_r_opened` | `target_door_open` |
| `lost_r_key` | `required_key_lost` in the target-door stage |
| `got_ball` | `target_ball_picked_up` |

The published `entered_goal_room` event has no equivalent local proposition. Exact
reproduction requires adding it or intentionally omitting that shaping transition.
