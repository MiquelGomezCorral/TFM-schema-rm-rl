# Service Room

## Environment

The agent works in one small room. Things happen to it on a schedule it does not control: a siren starts ringing and a carried box slips out of its hands. The agent has seven actions: turn left, turn right, move forward, pick up, drop, toggle, and done. Done does nothing.

Layout: a square room of 8 x 8 cells with an outer wall, so 6 x 6 cells of floor. The layout never changes between episodes. The agent starts in the top-left floor corner, facing right. The green exit is in the bottom-right floor corner. A purple box lies on the floor in the upper part of the room. A switch is a panel set into the left wall, low on the wall. It is blue and turns red while the siren rings. The agent can toggle it only from the floor cell next to it, facing it.

A setup can leave out the siren, the box, or both. A missing siren has no switch and `siren_ringing` is never true. A missing box makes `holding_box` and `box_fell` never true. What changes between episodes is only when the events happen. Nothing else is random.

The siren and the box fall follow a schedule fixed at the start of the episode:

- The siren starts at step 1, 2, 3 or 4. Half of the episodes also have a second start, 8 to 30 steps after the first one.
- The box falls from the agent's hands 2 to 6 steps after the agent first picks it up. Half of the episodes also have a second fall, 2 to 6 steps after the second pickup.

## Objective and episode boundary

The task is to reach the exit. The environment ends the episode on reaching the exit and cuts it at the step limit, 200 steps in the standard setup.

At the exit the environment pays 1 minus 0.9 times the fraction of the step limit used, but only if the setup's conditions hold at that moment. A setup can require the siren to be silent, the box to be in the agent's hands, or both. If a condition fails, the episode still ends at the exit and pays 0.

The siren cannot start, and the box cannot fall, on the step that ends the episode: the step onto the exit or the step at the step limit. The agent's own action on that step still applies, so a toggle of the switch on the step at the step limit still counts and `switch_toggled` is true then.

## Proposition semantics

| id | kind | true when |
|---|---|---|
| `siren_ringing` | condition | the siren is on; it starts by itself and stays on until the agent toggles the switch |
| `switch_toggled` | event | the agent toggled the switch at this step; false on every other step |
| `holding_box` | condition | the agent carries the box |
| `box_fell` | event | the box slipped out of the agent's hands at this step; false on every other step |
| `at_exit` | condition, last step only | the agent stands on the exit cell |

`switch_toggled` reading: it is true on every toggle of the switch, also when the siren is silent. Toggling a silent siren changes nothing else.

## Constraints

- `box_fell` cannot become true before `holding_box`: only a carried box can fall.
- `box_fell` and `holding_box` never hold together: the fall empties the hands at that step.
- `box_fell` and `at_exit` never hold together: the box cannot fall on the step that ends the episode.
- `switch_toggled` and `at_exit` never hold together: toggling does not move the agent.

## What the agent can and cannot do

- Can: turn; move forward onto an empty floor cell or the exit; pick up the box with empty hands; drop the box onto an empty cell in front; toggle the switch when facing it.
- Cannot: walk through walls, the switch panel or the box; pick up the switch, walls or the exit; carry anything but the box.
- The siren stops only when the agent toggles the switch. It does not stop by itself.
- If the siren is already ringing when a second start is due, the second start is skipped. The siren just keeps ringing.
- The siren can start again after the agent silenced it, when the episode has a second start.
- The box falls only if the agent still carries it when the fall is due. A box put down before the fall is due does not fall. Picking it up again on the due step counts as carrying (the action applies first, then the events), so it falls on that step.
- A fallen box lands on the first empty cell among: in front of the agent, to its right, behind it, to its left. If none is empty, the box stays in the hands and nothing falls.
- After a fall the agent can pick the box up again. Falls follow pickups: the first pickup of the episode starts the first fall, the second pickup (after a fall or after putting the box down) starts the second fall in the episodes that have one, and later pickups cause no fall. A fall due while the hands are empty is skipped and does not come back, so an agent that drops the box and keeps it down until the due step avoids that fall.
- Toggling the box does nothing. The box never disappears.
- The siren and the box are independent: each can happen while the other is going on, including on the same step.

## Example trace

A real episode in a setup with siren and box, both required at the exit.

1. step 1, a move: no proposition changes
2. step 2, a move: `siren_ringing` true, the siren starts by itself
3. steps 3 to 10, turns and moves toward the switch: no changes
4. `toggle` (step 11): `switch_toggled` true, `siren_ringing` false
5. step 12, a turn: `switch_toggled` false
6. steps 13 to 18, turns and moves toward the box: no changes
7. `pickup` (step 19): `holding_box` true
8. step 20, a move: no changes
9. step 21, a move: `box_fell` true, `holding_box` false, the box slips out of the hands
10. `pickup` (step 22): `holding_box` true, `box_fell` false
11. steps 23 to 27, turns and moves toward the exit: no changes
12. `forward` (step 28): `at_exit` true [episode terminated]

Variant, a second real episode: the siren starts at step 4 and is silenced by `toggle` at step 15. It starts again at step 18 and is silenced by `toggle` at step 24.

## Propositions
- `siren_ringing`: The siren is currently ringing and has not been silenced since it started.
- `switch_toggled`: The agent toggled the wall switch at this step.
- `holding_box`: The agent is currently carrying the box.
- `box_fell`: The box slipped out of the agent's hands at this step.
- `at_exit`: The agent is currently on the exit cell.

## Example tasks

- Whenever the siren rings, turn it off.
- Pick up the box and keep it until you reach the exit.
- If the box falls, pick it up again.
- Reach the exit with the siren silent and the box in your hands.
