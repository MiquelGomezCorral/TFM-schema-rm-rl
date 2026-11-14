# Cards behind the generation table

## base: 4 bundles per arm

Machine of a row: `experiments/benchmark/base/bundles/{arm-fm,farm}/<bundle>/reward_machine.txt`.

| bundle | NL task | expected LTLf |
|---|---|---|
| `base-doorkey` | Use the key to open the door, then reach the goal. | (((~door_open) U has_key) | (G (~door_open))); (((~at_goal) U door_open) | (G (~at_goal))); (F at_goal) |
| `base-unlock-pickup` | Acquire the matching key, unlock the door, and pick up the designated box in the other room. | (((~door_open) U has_door_key) | (G (~door_open))); (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up) |
| `base-blocked-unlock-pickup` | Pick up the blocking ball and the key, in either order, unlock the door, and then pick up the box in the other room. | (((~door_open) U blocker_moved) | (G (~door_open))); (((~door_open) U has_door_key) | (G (~door_open))); (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up) |
| `base-key-corridor` | Explore the side rooms, find and acquire the key matching the locked target room, return to the corridor, open the target door, and pick up the designated object. | (((~target_door_open) U has_matching_key) | (G (~target_door_open))); (((~target_picked_up) U target_door_open) | (G (~target_picked_up))); (F target_picked_up) |

## complex: 24 bundles per arm

Machine of a row: `experiments/benchmark/complex/bundles/{arm-fm,farm}/<bundle>/reward_machine.txt`.

| bundle | NL task | expected LTLf |
|---|---|---|
| `cx-sequence` | Find the key, pick it up, open the locked door, go into the room, and then pick up the ball. | (((~has_matching_key) U key_found) | (G (~has_matching_key))); (((~target_door_open) U has_matching_key) | (G (~target_door_open))); (((~target_room_entered) U target_door_open) | (G (~target_room_entered))); (((~target_picked_up) U target_room_entered) | (G (~target_picked_up))); (F target_picked_up) |
| `cx-sequence~p1` | First find the key and pick it up. Then open the locked door, enter the room, and pick up the ball. | (((~has_matching_key) U key_found) | (G (~has_matching_key))); (((~target_door_open) U has_matching_key) | (G (~target_door_open))); (((~target_room_entered) U target_door_open) | (G (~target_room_entered))); (((~target_picked_up) U target_room_entered) | (G (~target_picked_up))); (F target_picked_up) |
| `cx-sequence~p2` | Locate the key and take it, unlock and open the door, step into the room, and finish by picking up the ball. | (((~has_matching_key) U key_found) | (G (~has_matching_key))); (((~target_door_open) U has_matching_key) | (G (~target_door_open))); (((~target_room_entered) U target_door_open) | (G (~target_room_entered))); (((~target_picked_up) U target_room_entered) | (G (~target_picked_up))); (F target_picked_up) |
| `cx-sequence~p3` | Find the key, take it, open the locked door, walk into the room behind it, and pick up the ball. | (((~has_matching_key) U key_found) | (G (~has_matching_key))); (((~target_door_open) U has_matching_key) | (G (~target_door_open))); (((~target_room_entered) U target_door_open) | (G (~target_room_entered))); (((~target_picked_up) U target_room_entered) | (G (~target_picked_up))); (F target_picked_up) |
| `cx-rules-only` | Do not pick up the box in the other room. Try not to drop the key while the door is still closed. Whenever you are holding the key, try to have the door open at that moment or open it afterwards. | (~(F target_picked_up)); (~(F key_lost)); (G (has_door_key -> (F door_open))) |
| `cx-rules-only~p1` | Never pick up the box in the other room. Try not to drop the key while the door is still closed, and whenever you hold the key, try to have the door open then or open it later. | (~(F target_picked_up)); (~(F key_lost)); (G (has_door_key -> (F door_open))) |
| `cx-rules-only~p2` | Leave the box alone. Whenever you are holding the key, try to have the door open at that moment or open it afterwards, and try not to drop the key while the door is still closed. | (~(F target_picked_up)); (~(F key_lost)); (G (has_door_key -> (F door_open))) |
| `cx-rules-only~p3` | Do not take the box from the other room. At any moment you hold the key, try to have the door open then or open it afterwards, and try not to drop the key while the door is still closed. | (~(F target_picked_up)); (~(F key_lost)); (G (has_door_key -> (F door_open))) |
| `cx-goal-one-rule` | Open the door and then pick up the box in the other room, and try not to drop the key while the door is still closed. | (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up); (~(F key_lost)) |
| `cx-goal-one-rule~p1` | Pick up the box in the other room after opening the door, and try not to drop the key while the door is still closed. | (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up); (~(F key_lost)) |
| `cx-goal-one-rule~p2` | Try not to drop the key while the door is still closed. Open the door, then pick up the box in the other room. | (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up); (~(F key_lost)) |
| `cx-goal-one-rule~p3` | Open the door, then take the box from the other room; try not to drop the key while the door is still closed. | (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up); (~(F key_lost)) |
| `cx-goal-many-rules` | Move the ball away from the door before you take the key. Try not to drop the key while the door is still closed. Whenever you are holding the key, try to have the door open at that moment or open it afterwards. Then pick up the box in the other room. | (((~has_door_key) U blocker_moved) | (G (~has_door_key))); (~(F key_lost)); (G (has_door_key -> (F door_open))); (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up) |
| `cx-goal-many-rules~p1` | Before taking the key, move the ball away from the door. Try not to drop the key while the door is still closed, and whenever you are holding the key, try to have the door open at that moment or open it afterwards. Finally, pick up the box in the other room. | (((~has_door_key) U blocker_moved) | (G (~has_door_key))); (~(F key_lost)); (G (has_door_key -> (F door_open))); (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up) |
| `cx-goal-many-rules~p2` | Take the key only after the ball is out of the way. Try not to drop the key while the door is still closed. At any moment you are holding the key, try to have the door open then or open it later. Then get the box from the other room. | (((~has_door_key) U blocker_moved) | (G (~has_door_key))); (~(F key_lost)); (G (has_door_key -> (F door_open))); (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up) |
| `cx-goal-many-rules~p3` | First clear the ball from the door and only then take the key. Try not to drop the key while the door is still closed, and whenever you hold the key, try to have the door open at that moment or open it afterwards. After that, pick up the box in the other room. | (((~has_door_key) U blocker_moved) | (G (~has_door_key))); (~(F key_lost)); (G (has_door_key -> (F door_open))); (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up) |
| `cx-siren` | Go to the exit, and whenever the siren rings, turn it off. | (G (siren_ringing -> (F switch_toggled))); (F at_exit) |
| `cx-siren~p1` | Reach the exit. Each time the siren rings, switch it off. | (G (siren_ringing -> (F switch_toggled))); (F at_exit) |
| `cx-siren~p2` | Every time the siren rings, turn it off with the switch, and get to the exit. | (G (siren_ringing -> (F switch_toggled))); (F at_exit) |
| `cx-siren~p3` | Make your way to the exit, and silence the siren every time it rings. | (G (siren_ringing -> (F switch_toggled))); (F at_exit) |
| `cx-box` | Carry the box to the exit, and whenever the box falls, pick it up again. | (G (box_fell -> (F holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `cx-box~p1` | Take the box to the exit. Each time the box falls, pick it up again. | (G (box_fell -> (F holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `cx-box~p2` | Every time the box falls, pick it up again, and reach the exit with the box in your hands. | (G (box_fell -> (F holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `cx-box~p3` | Make your way to the exit carrying the box, and pick the box up again every time it falls. | (G (box_fell -> (F holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |

## templates: 96 bundles per arm

Machine of a row: `experiments/benchmark/templates/bundles/{arm-fm,farm}/<bundle>/reward_machine.txt`.

| bundle | NL task | expected LTLf |
|---|---|---|
| `tpl-existence-1-goal` | Pick up the key, then reach the goal. | (F has_key); (F at_goal) |
| `tpl-existence-1-goal~p1` | Take the key and then get to the goal. | (F has_key); (F at_goal) |
| `tpl-existence-1-goal~p2` | Grab the key first, then make your way to the goal. | (F has_key); (F at_goal) |
| `tpl-existence-1-goal~p3` | After you have picked up the key, reach the goal. | (F has_key); (F at_goal) |
| `tpl-existence-1-nogoal` | Flip the switch on the wall. | (F switch_toggled) |
| `tpl-existence-1-nogoal~p1` | Toggle the wall switch. | (F switch_toggled) |
| `tpl-existence-1-nogoal~p2` | Operate the switch fixed to the wall. | (F switch_toggled) |
| `tpl-existence-1-nogoal~p3` | At some point, flip the wall switch. | (F switch_toggled) |
| `tpl-existence-2-goal` | Open the door and pick up the box in the other room. | (F door_open); (F target_picked_up) |
| `tpl-existence-2-nogoal` | Pick up the ball that blocks the door. | (F blocker_moved) |
| `tpl-existence-3-goal` | Get into the locked room and pick up the ball. | (F target_room_entered); (F target_picked_up) |
| `tpl-existence-3-nogoal` | Open the door. | (F door_open) |
| `tpl-existence-two-1-goal` | Be holding the key on at least two different moves, then pick up the box in the other room. | (F (has_door_key & (X (F has_door_key)))); (F target_picked_up) |
| `tpl-existence-two-1-goal~p1` | First have the key in your hands on at least two separate moves; afterwards pick up the box in the other room. | (F (has_door_key & (X (F has_door_key)))); (F target_picked_up) |
| `tpl-existence-two-1-goal~p2` | Pick up the box in the other room, after you were holding the key on at least two different moves. | (F (has_door_key & (X (F has_door_key)))); (F target_picked_up) |
| `tpl-existence-two-1-goal~p3` | Hold the key on two or more different moves, and then take the box from the other room. | (F (has_door_key & (X (F has_door_key)))); (F target_picked_up) |
| `tpl-existence-two-1-nogoal` | Be holding the key on at least two different moves. | (F (has_key & (X (F has_key)))) |
| `tpl-existence-two-1-nogoal~p1` | Hold the key on two or more different moves. | (F (has_key & (X (F has_key)))) |
| `tpl-existence-two-1-nogoal~p2` | Carry the key on at least two different moves. | (F (has_key & (X (F has_key)))) |
| `tpl-existence-two-1-nogoal~p3` | Have the key in your hands on at least two separate moves. | (F (has_key & (X (F has_key)))) |
| `tpl-existence-two-2-goal` | Be holding the key on at least two different moves, then pick up the box in the other room. | (F (has_door_key & (X (F has_door_key)))); (F target_picked_up) |
| `tpl-existence-two-2-nogoal` | Be holding the matching key on at least two different moves. | (F (has_matching_key & (X (F has_matching_key)))) |
| `tpl-existence-two-3-goal` | Be holding the key on at least two different moves, open the door and reach the goal. | (F (has_key & (X (F has_key)))); (F at_goal) |
| `tpl-existence-two-3-nogoal` | Be holding the key on at least two different moves. | (F (has_door_key & (X (F has_door_key)))) |
| `tpl-absence-1-goal` | Pick up the box in the other room, and never drop the key while the door is still closed. | (~(F key_lost)); (F target_picked_up) |
| `tpl-absence-1-goal~p1` | Never drop the key while the door is still closed, and pick up the box in the other room. | (~(F key_lost)); (F target_picked_up) |
| `tpl-absence-1-goal~p2` | Get the box from the other room, and do not drop the key while the door is closed. | (~(F key_lost)); (F target_picked_up) |
| `tpl-absence-1-goal~p3` | While the door is still closed, you must not drop the key. Pick up the box in the other room. | (~(F key_lost)); (F target_picked_up) |
| `tpl-absence-1-nogoal` | Never open the locked door. | (~(F target_door_open)) |
| `tpl-absence-1-nogoal~p1` | Do not open the locked door. | (~(F target_door_open)) |
| `tpl-absence-1-nogoal~p2` | Keep the locked door shut. | (~(F target_door_open)) |
| `tpl-absence-1-nogoal~p3` | The locked door must never be opened. | (~(F target_door_open)) |
| `tpl-absence-2-goal` | Reach the goal, and never drop the key while the door is still closed. | (~(F key_lost)); (F at_goal) |
| `tpl-absence-2-nogoal` | Don't drop the key while the door is still closed. | (~(F key_lost)) |
| `tpl-absence-3-goal` | Pick up the box in the other room, and never drop the key while the door is still closed. | (~(F key_lost)); (F target_picked_up) |
| `tpl-absence-3-nogoal` | Never flip the wall switch. | (~(F switch_toggled)) |
| `tpl-response-1-goal` | Once you have found the key, the locked door must be open on the last step of the episode. Open it, then pick up the ball. | (G (key_found -> (F target_door_open))); (F target_picked_up) |
| `tpl-response-1-goal~p1` | After you find the key, make sure the locked door is open when the episode ends. Open it and then take the ball. | (G (key_found -> (F target_door_open))); (F target_picked_up) |
| `tpl-response-1-goal~p2` | From the moment you find the key, the locked door has to be open on the final step. Open it, and then pick up the ball. | (G (key_found -> (F target_door_open))); (F target_picked_up) |
| `tpl-response-1-goal~p3` | When you find the key, the locked door must be open at the end of the episode; open it. Finally, pick up the ball. | (G (key_found -> (F target_door_open))); (F target_picked_up) |
| `tpl-response-1-nogoal` | Whenever the ball is out of the way of the door, you must be holding the key at that moment or pick it up afterwards. | (G (blocker_moved -> (F has_door_key))) |
| `tpl-response-1-nogoal~p1` | At every moment the ball is out of the way of the door, you have to be carrying the key then, or pick it up later. | (G (blocker_moved -> (F has_door_key))) |
| `tpl-response-1-nogoal~p2` | If the ball has been moved away from the door, you must be holding the key at that point or at some later point. | (G (blocker_moved -> (F has_door_key))) |
| `tpl-response-1-nogoal~p3` | Any time the ball is away from the door, the key must be in your hands at that moment or afterwards. | (G (blocker_moved -> (F has_door_key))) |
| `tpl-response-2-goal` | Whenever you are holding the key, the door must be open at that moment or opened afterwards. Then reach the goal. | (G (has_key -> (F door_open))); (F at_goal) |
| `tpl-response-2-nogoal` | Whenever you are holding the key, the door must be open at that moment or opened afterwards. | (G (has_door_key -> (F door_open))) |
| `tpl-response-3-goal` | Whenever you are holding the key, the door must be open at that moment or opened afterwards. Then pick up the box in the other room. | (G (has_door_key -> (F door_open))); (F target_picked_up) |
| `tpl-response-3-nogoal` | Once you have found the key, the locked door must be open on the last step of the episode. | (G (key_found -> (F target_door_open))) |
| `tpl-precedence-1-goal` | Move the ball away from the door before you take the key, then open the door and pick up the box. | (((~has_door_key) U blocker_moved) | (G (~has_door_key))); (F target_picked_up) |
| `tpl-precedence-1-goal~p1` | Before taking the key, move the ball away from the door. Then open the door and pick up the box. | (((~has_door_key) U blocker_moved) | (G (~has_door_key))); (F target_picked_up) |
| `tpl-precedence-1-goal~p2` | Take the key only after the ball is out of the way, then open the door and pick up the box. | (((~has_door_key) U blocker_moved) | (G (~has_door_key))); (F target_picked_up) |
| `tpl-precedence-1-goal~p3` | First move the ball off the door, then take the key, open the door and pick up the box. | (((~has_door_key) U blocker_moved) | (G (~has_door_key))); (F target_picked_up) |
| `tpl-precedence-1-nogoal` | If you reach the exit, you must have flipped the switch first. | (((~at_exit) U switch_toggled) | (G (~at_exit))) |
| `tpl-precedence-1-nogoal~p1` | You may only reach the exit after you have flipped the switch. | (((~at_exit) U switch_toggled) | (G (~at_exit))) |
| `tpl-precedence-1-nogoal~p2` | Do not reach the exit until you have flipped the switch. | (((~at_exit) U switch_toggled) | (G (~at_exit))) |
| `tpl-precedence-1-nogoal~p3` | Reaching the exit is allowed only once the switch has been flipped. | (((~at_exit) U switch_toggled) | (G (~at_exit))) |
| `tpl-precedence-2-goal` | Do not drop the key while the door is closed until the door has been opened once. Reach the goal. | (((~key_lost) U door_open) | (G (~key_lost))); (F at_goal) |
| `tpl-precedence-2-nogoal` | Don't drop the key while the door is closed until the door has been opened once. | (((~key_lost) U door_open) | (G (~key_lost))) |
| `tpl-precedence-3-goal` | Pick up the box in the other room, but do not drop the key while the door is closed until the door has been opened once. | (((~key_lost) U door_open) | (G (~key_lost))); (F target_picked_up) |
| `tpl-precedence-3-nogoal` | Do not take the key until you have moved the ball away from the door. | (((~has_door_key) U blocker_moved) | (G (~has_door_key))) |
| `tpl-chain-response-1-goal` | Carry the box to the exit. Whenever the box falls, pick it up again on your very next move. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-goal~p1` | Take the box to the exit. Each time the box falls, pick it up on your very next move. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-goal~p2` | Reach the exit with the box in your hands, and if the box falls, pick it up again on the very next move. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-goal~p3` | Get to the exit carrying the box; every time the box falls, your very next move must pick it up again. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-nogoal` | Whenever the box falls, pick it up again on your very next move. If you reach the exit, you must be carrying the box. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-nogoal~p1` | Should the box fall, make your very next move the one that picks it back up. If you get to the exit, you must have the box in your hands. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-nogoal~p2` | Every time the box falls, your very next move must pick it up again; and if you reach the exit, you must be carrying the box. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-nogoal~p3` | After the box falls, the move right after it has to pick it up again. Do not reach the exit without the box in your hands. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-2-goal` | Carry the box to the exit. Each time the box falls, your very next move must pick it up again. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-2-nogoal` | Each time the box falls, pick it up again on your very next move. If you reach the exit, you must be carrying the box. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-3-goal` | Carry the box to the exit. If the box falls, pick it up again on your very next move. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-3-nogoal` | If the box falls, the very next move must pick it up again. If you reach the exit, you must be carrying the box. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-responded-existence-1-goal` | If you find the key, you must also open the locked door. Then pick up the ball. | ((F key_found) -> (F target_door_open)); (F target_picked_up) |
| `tpl-responded-existence-1-goal~p1` | Should you find the key, you are also required to open the locked door. After that, get the ball. | ((F key_found) -> (F target_door_open)); (F target_picked_up) |
| `tpl-responded-existence-1-goal~p2` | Finding the key means you must open the locked door too; finally, pick up the ball. | ((F key_found) -> (F target_door_open)); (F target_picked_up) |
| `tpl-responded-existence-1-goal~p3` | Pick up the ball. If you find the key, you need to open the locked door as well. | ((F key_found) -> (F target_door_open)); (F target_picked_up) |
| `tpl-responded-existence-1-nogoal` | If you pick up the key, you must also open the door. | ((F has_door_key) -> (F door_open)) |
| `tpl-responded-existence-1-nogoal~p1` | If you take the key, you also have to open the door. | ((F has_door_key) -> (F door_open)) |
| `tpl-responded-existence-1-nogoal~p2` | Taking the key means you must open the door too. | ((F has_door_key) -> (F door_open)) |
| `tpl-responded-existence-1-nogoal~p3` | You must open the door if you pick up the key. | ((F has_door_key) -> (F door_open)) |
| `tpl-responded-existence-2-goal` | If you move the ball, you must also take the key. Then pick up the box in the other room. | ((F blocker_moved) -> (F has_door_key)); (F target_picked_up) |
| `tpl-responded-existence-2-nogoal` | If the siren rings at any point in the run, you must flip the switch at least once somewhere in the run, before or after the ring. | ((F siren_ringing) -> (F switch_toggled)) |
| `tpl-responded-existence-3-goal` | If you take the key, you must also open the door. Then pick up the box in the other room. | ((F has_door_key) -> (F door_open)); (F target_picked_up) |
| `tpl-responded-existence-3-nogoal` | If you pick up the key, you must also open the door. | ((F has_key) -> (F door_open)) |
| `tpl-not-co-existence-1-goal` | Pick up the box in the other room, but never both drop the key while the door is still closed and open the door. | ((F key_lost) -> (~(F door_open))); (F target_picked_up) |
| `tpl-not-co-existence-1-goal~p1` | Get the box from the other room, while never letting both of these happen: you drop the key while the door is still closed, you open the door. | ((F key_lost) -> (~(F door_open))); (F target_picked_up) |
| `tpl-not-co-existence-1-goal~p2` | Pick up the box in the other room. You must not drop the key while the door is still closed and open the door in the same run. | ((F key_lost) -> (~(F door_open))); (F target_picked_up) |
| `tpl-not-co-existence-1-goal~p3` | Take the box from the other room; dropping the key while the door is still closed and opening the door must never both happen. | ((F key_lost) -> (~(F door_open))); (F target_picked_up) |
| `tpl-not-co-existence-1-nogoal` | Never both take the key and move the ball away from the door. | ((F blocker_moved) -> (~(F has_door_key))) |
| `tpl-not-co-existence-1-nogoal~p1` | Taking the key and moving the ball away from the door must never both happen. | ((F blocker_moved) -> (~(F has_door_key))) |
| `tpl-not-co-existence-1-nogoal~p2` | Do not both pick up the key and move the ball away from the door. | ((F blocker_moved) -> (~(F has_door_key))) |
| `tpl-not-co-existence-1-nogoal~p3` | Make sure you never do both: pick up the key and clear the ball from the door. | ((F blocker_moved) -> (~(F has_door_key))) |
| `tpl-not-co-existence-2-goal` | Pick up the box in the other room, but never both drop the key while the door is still closed and open the door. | ((F key_lost) -> (~(F door_open))); (F target_picked_up) |
| `tpl-not-co-existence-2-nogoal` | Never both drop the key while the door is still closed and open the door. | ((F key_lost) -> (~(F door_open))) |
| `tpl-not-co-existence-3-goal` | Reach the goal, but never both drop the key while the door is still closed and open the door. | ((F key_lost) -> (~(F door_open))); (F at_goal) |
| `tpl-not-co-existence-3-nogoal` | Never both take the matching key and get into the locked room. | ((F has_matching_key) -> (~(F target_room_entered))) |

## box-carry: 16 bundles per arm

Machine of a row: `experiments/benchmark/box-carry/bundles/{arm-fm,farm}/<bundle>/reward_machine.txt`.

| bundle | NL task | expected LTLf |
|---|---|---|
| `tpl-chain-response-1-goal-carry` | Carry the box to the exit. Whenever the box falls, pick it up again on your very next move. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-goal-carry~p1` | Take the box to the exit. Each time the box falls, pick it up on your very next move. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-goal-carry~p2` | Reach the exit with the box in your hands, and if the box falls, pick it up again on the very next move. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-goal-carry~p3` | Get to the exit carrying the box; every time the box falls, your very next move must pick it up again. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-nogoal-carry` | Whenever the box falls, pick it up again on your very next move. If you reach the exit, you must be carrying the box. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-nogoal-carry~p1` | Should the box fall, make your very next move the one that picks it back up. If you get to the exit, you must have the box in your hands. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-nogoal-carry~p2` | Every time the box falls, your very next move must pick it up again; and if you reach the exit, you must be carrying the box. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-1-nogoal-carry~p3` | After the box falls, the move right after it has to pick it up again. Do not reach the exit without the box in your hands. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-2-goal-carry` | Carry the box to the exit. Each time the box falls, your very next move must pick it up again. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-2-nogoal-carry` | Each time the box falls, pick it up again on your very next move. If you reach the exit, you must be carrying the box. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-3-goal-carry` | Carry the box to the exit. If the box falls, pick it up again on your very next move. | (G (box_fell -> (X holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `tpl-chain-response-3-nogoal-carry` | If the box falls, the very next move must pick it up again. If you reach the exit, you must be carrying the box. | (G (box_fell -> (X holding_box))); (G (at_exit -> (F holding_box))) |
| `cx-box-carry` | Carry the box to the exit, and whenever the box falls, pick it up again. | (G (box_fell -> (F holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `cx-box-carry~p1` | Take the box to the exit. Each time the box falls, pick it up again. | (G (box_fell -> (F holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `cx-box-carry~p2` | Every time the box falls, pick it up again, and reach the exit with the box in your hands. | (G (box_fell -> (F holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |
| `cx-box-carry~p3` | Make your way to the exit carrying the box, and pick the box up again every time it falls. | (G (box_fell -> (F holding_box))); (F at_exit); (G (at_exit -> (F holding_box))) |

## forced-start: 8 bundles per arm

Machine of a row: `experiments/benchmark/forced-start/bundles/{arm-fm,farm}/<bundle>/reward_machine.txt`.

| bundle | NL task | expected LTLf |
|---|---|---|
| `tpl-response-1-nogoal-forced` | Whenever the ball is out of the way of the door, you must be holding the key at that moment or pick it up afterwards. | (G (blocker_moved -> (F has_door_key))) |
| `tpl-response-1-nogoal-forced~p1` | At every moment the ball is out of the way of the door, you have to be carrying the key then, or pick it up later. | (G (blocker_moved -> (F has_door_key))) |
| `tpl-response-1-nogoal-forced~p2` | If the ball has been moved away from the door, you must be holding the key at that point or at some later point. | (G (blocker_moved -> (F has_door_key))) |
| `tpl-response-1-nogoal-forced~p3` | Any time the ball is away from the door, the key must be in your hands at that moment or afterwards. | (G (blocker_moved -> (F has_door_key))) |
| `tpl-responded-existence-1-nogoal-forced` | If you pick up the key, you must also open the door. | ((F has_door_key) -> (F door_open)) |
| `tpl-responded-existence-1-nogoal-forced~p1` | If you take the key, you also have to open the door. | ((F has_door_key) -> (F door_open)) |
| `tpl-responded-existence-1-nogoal-forced~p2` | Taking the key means you must open the door too. | ((F has_door_key) -> (F door_open)) |
| `tpl-responded-existence-1-nogoal-forced~p3` | You must open the door if you pick up the key. | ((F has_door_key) -> (F door_open)) |

## pilot: 2 bundles (FARM only)

Machine of a row: `experiments/benchmark/pilot/bundles/farm/<bundle>/reward_machine.txt`.

| bundle | NL task | expected LTLf |
|---|---|---|
| `base-doorkey` | Use the key to open the door, then reach the goal. | (((~door_open) U has_key) | (G (~door_open))); (((~at_goal) U door_open) | (G (~at_goal))); (F at_goal) |
| `base-unlock-pickup` | Acquire the matching key, unlock the door, and pick up the designated box in the other room. | (((~door_open) U has_door_key) | (G (~door_open))); (((~target_picked_up) U door_open) | (G (~target_picked_up))); (F target_picked_up) |

Total: 150 bundle names.
