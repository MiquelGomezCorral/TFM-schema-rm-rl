# Shop

## Environment

The agent runs a small shop. Things keep happening on a schedule it does not control: a siren rings, clients walk in, and the food it carries slips out of its hands. The agent has seven actions: turn left, turn right, move forward, pick up, drop, toggle, and done. Done does nothing. The siren, the clients and the food slips are there in every episode; only the rules a task states differ.

Layout: a square room of 10 x 10 cells with an outer wall, so 8 x 8 cells of floor. The layout never changes between episodes. The agent starts in the fourth floor column from the left and the fourth row from the top, facing right.

- Counter: a yellow wall of three cells in the leftmost floor column, in rows three to five from the top. The middle cell is the client spot, where a client stands.
- Pantry: a yellow shelf of three cells in the rightmost floor column, in rows three to five from the top. The middle cell always holds one portion of food; taking it puts a new portion there at once.
- Stove: a purple panel set into the top wall, above the agent's starting column.
- Siren switch: a blue panel set into the bottom wall, one column to the right of the agent's starting column. It turns red while the siren rings.
- Siren cue: while the siren rings, every plain wall and counter cell of the room turns red too, so the siren is seen from every position and facing. They turn back when it stops.

The agent uses a panel, the pantry or the client only from the floor cell next to it, facing it:

- Take an order: face the client and toggle.
- Fetch food: face the pantry and pick up. The portion is raw food (yellow).
- Prepare food: carry raw food, face the stove and toggle, while a client who has ordered waits. The food turns green.
- Serve: carry prepared food, face a client who has ordered, and toggle. The client leaves with the food.
- Turn the siren off: face the siren switch and toggle.

Schedule, drawn when the episode starts; the same start gives the same episode:

- The siren first rings at step 3 to 30 and rings until the agent toggles the switch. The next ring starts 25 to 69 steps after that toggle.
- The first client arrives at step 3 to 25, at most one at a time, and waits until served. The next one arrives 10 to 39 steps after the previous one left.
- Each time the agent picks up food, a slip is planned 2 to 7 steps later, with chance one half, and it replaces any slip still pending. The first pickup of the episode always slips. Only the first 60 pickups of an episode can slip; later ones never do.
- Quiet end: no ring starts after step 555, no client after step 489, no slip after step 597.

## Objective and episode boundary

There is no goal. The environment never ends the episode early; it cuts it at the step limit, 600 steps. The agent's work is to react to what happens.

The environment's own reward is +1 for each order served, and -0.5 each time a waiting client has heard one ring for more than 30 steps, and again for every further 30 steps of it (counting steps with a client waiting and the siren ringing; the count starts again at each ring). Food slips cost nothing.

## Proposition semantics

| id | kind | true when |
|---|---|---|
| `siren_ringing` | condition | the siren is on; it starts by itself and stays on until the agent toggles the switch |
| `holding_food` | condition | the agent carries a portion of food, raw or prepared |
| `switch_toggled` | event | the agent toggled the siren switch at this step; false on every other step |
| `client_arrived` | event | a client appeared at the counter at this step |
| `order_taken` | event | the agent took the waiting client's order at this step |
| `food_prepared` | event | the agent prepared the food it carries at this step |
| `order_served` | event | the agent handed prepared food to the client at this step |
| `food_fell` | event | the food slipped out of the agent's hands at this step |
| `served_while_ringing` | event | an order was served at this step and the siren was already ringing when the step began |

Readings: `switch_toggled` is true on every toggle of the switch, also when the siren is silent (nothing else changes then). For `served_while_ringing` the siren counts as ringing if it was on after the previous step; a siren that starts on the very step of the serve does not count.

## Constraints

- `order_taken` needs a client who arrived earlier: it never holds on the step of `client_arrived`.
- `order_served` needs `holding_food` at the previous step and ends it. `served_while_ringing` implies `order_served`.
- `food_prepared` needs `holding_food` at the previous step and a client whose order is taken and not yet served. The hands stay full unless the food slips on that same step.
- `food_fell` and `holding_food` never hold together: the slip empties the hands. Only carried food slips.
- One client at a time: `client_arrived` is never true again before the client was served.
- At most one of `switch_toggled`, `order_taken`, `food_prepared`, `order_served` is true at a step: one toggle has one target.

## What the agent can and cannot do

- Can: turn; move forward onto an empty floor cell; pick up food with empty hands; drop food onto an empty cell in front; toggle the siren switch, the client or the stove when facing them.
- Cannot: walk through walls, the counter, the pantry, the panels or the client; carry more than one portion; pick up the client.
- Toggling the client takes the order if it is not taken yet; with prepared food, after the order, it serves; in any other case it does nothing.
- Toggling the stove prepares raw food only while a client whose order is taken waits. In any other case it does nothing: food cannot be prepared ahead. Food is never prepared twice.
- Taking food from the pantry removes any other portion lying on the floor: at most one portion exists outside the pantry.
- A slip lands the food on the first empty cell among: in front of the agent, to its right, behind it, to its left. It turns the agent to face the food, so the very next move can pick it up. If no cell is empty, the food stays in the hands and nothing slips.
- Food put down before a planned slip is due does not slip, and picking food up again plans a new slip in place of the old one. A slip due while the hands are empty is skipped and does not come back. Picking food up on the due step counts as carrying: it slips on that step.
- The siren stops only when the agent toggles the switch, and a ring starts only while it is silent.
- A client who is served is gone. The first ring and the first client always come within the first 30 steps, so every episode has at least one of each, with time to handle them.

## Example trace

An example episode.

1. step 7, done: `client_arrived` true
2. step 12, toggle at the client: `order_taken` true
3. step 20, pickup at the pantry: `holding_food` true
4. step 24, forward: `food_fell` true, `holding_food` false; the food lies in front of the agent
5. step 25, pickup: `holding_food` true
6. step 26, forward: `siren_ringing` true; the food falls again at steps 28 and 32, each time picked up on the next step
7. step 37, toggle at the switch: `switch_toggled` true, `siren_ringing` false
8. step 48, toggle at the stove: `food_prepared` true
9. step 57, toggle at the client: `order_served` true, `holding_food` false, reward +1

## Propositions
- `siren_ringing`: The siren is currently ringing and has not been silenced since it started.
- `holding_food`: The agent is currently carrying food.
- `switch_toggled`: The agent toggled the siren switch at this step.
- `client_arrived`: A client arrived at the counter at this step.
- `order_taken`: The agent took the client's order at this step.
- `food_prepared`: The agent prepared its food at the stove at this step.
- `order_served`: The agent gave the prepared food to the client at this step.
- `food_fell`: The food slipped out of the agent's hands at this step.
- `served_while_ringing`: An order was served at this step while the siren was already ringing.

## Example tasks

- Whenever the siren rings, turn it off.
- For every client: take the order, prepare food at the stove and serve it.
- If the food falls, pick it up on the very next move.
