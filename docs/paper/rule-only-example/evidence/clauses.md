| # | Sentence | Template | Priority | LTLf |
|---|---|---|---|---|
| 1 | Never pick up the target box. | `Absence(target_picked_up)` | hard | `¬(F target_picked_up)` |
| 2 | Try not to lose the key before the door is opened. | `Absence(key_lost)` | soft | `¬(F key_lost)` |
| 3 | Whenever the key is held, try to have the door open at that moment or later. | `Response(has_door_key, door_open)` | soft | `G (has_door_key → (F door_open))` |
