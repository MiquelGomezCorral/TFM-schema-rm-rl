| From | When | To | Pay | Progress | Break or well | What happens |
|---|---|---|---|---|---|---|
| u0 | else | u0 | 0 | 0 | 0 | nothing |
| u0 | `(!has_door_key & !target_picked_up & key_lost) or (door_open & !target_picked_up & key_lost)` | u0 | -1 | 0 | -1 | a soft rule breaks |
| u0 | `has_door_key & !door_open & !target_picked_up & !key_lost` | u2 | -1 | -1 | 0 | a promise opens |
| u0 | `has_door_key & !door_open & !target_picked_up & key_lost` | u2 | -2 | -1 | -1 | a soft rule breaks and a promise opens |
| u0 | `target_picked_up` | u1 (well) | -100.694 | 0 | -100.694 | hard rule broken: the well |
| u2 | else | u2 | 0 | 0 | 0 | nothing |
| u2 | `!door_open & !target_picked_up & key_lost` | u2 | -1 | 0 | -1 | a soft rule breaks |
| u2 | `door_open & !target_picked_up & !key_lost` | u0 | +1 | +1 | 0 | a promise is kept |
| u2 | `door_open & !target_picked_up & key_lost` | u0 | 0 | +1 | -1 | a soft rule breaks and a promise is kept |
| u2 | `target_picked_up` | u1 (well) | -100.694 | 0 | -100.694 | hard rule broken: the well |
