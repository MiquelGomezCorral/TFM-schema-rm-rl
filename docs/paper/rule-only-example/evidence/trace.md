| Step | Labels true | State | Pay | Total | What happens |
|---|---|---|---|---|---|
| 1 | none | u0 -> u0 | 0 | 0 | walking, nothing happens |
| 2 | `has_door_key` | u0 -> u2 | -1 | -1 | picks the key up, the door is closed: the promise opens |
| 3 | `key_lost` | u2 -> u2 | -1 | -2 | drops the key, the door is still closed: the soft rule breaks |
| 4 | `has_door_key` | u2 -> u2 | 0 | -2 | picks the key up again: the promise stays open |
| 5 | `has_door_key`, `door_open` | u2 -> u0 | +1 | -1 | opens the door: the promise is kept |
| 6 | `door_open`, `target_picked_up` | u0 -> u1 | -100.694 | -101.694 | picks up the target box: the hard rule breaks, the episode ends |
