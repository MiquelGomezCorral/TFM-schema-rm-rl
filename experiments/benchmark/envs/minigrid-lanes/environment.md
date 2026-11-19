# MiniGrid Lanes

## Environment

Zombies walk by themselves down three lanes of a field and the agent must stop them. The agent has seven actions: turn left, turn right, move forward, pick up, drop, toggle, and done. Only turning and moving forward do anything; pick up, drop, toggle and done do nothing, because there is nothing to hold or toggle.

Layout: a field of 9 x 9 cells inside an outer wall (an 11 x 11 grid). Three lanes run left to right along field rows 0, 4 and 8, from the top. The top lane (row 0) is the protected one; the other two are the side lanes. The agent starts in the middle of the field, on the middle lane, facing left. The agent sees the whole grid, not a partial view. Nothing else is fixed: the layout is the same in every episode and only the events change.

Zombies (red balls) enter at the right end of a random lane at random times and step one cell left every 3 steps, counted from the step they entered. The agent moves one cell per step, so it is faster. A zombie that steps past the left end gets through and disappears. A zombie does not enter while another one stands on the entry cell of its lane. The chance that a zombie enters at a step rises over the episode, from 4% at the first step to 17% at the last, so later in the episode more zombies come than the agent can stop.

Plants (green balls) sprout now and then (one try every 20 to 60 steps) on a random free cell of the field that is not on a lane, and at most 3 are alive at once. A plant stays until the agent steps on it.

The agent kills a zombie by moving onto its cell. A zombie that steps onto the agent's cell is not killed and keeps walking. All draws are made at the start of the episode from the reset seed.

## Objective and episode boundary

The task is to keep zombies from getting through the top lane. The environment never ends the episode on its own: it cuts it at the step limit, 300 steps.

The environment pays 1 for every zombie killed, nothing else. The episode counts as a success when no zombie got through the top lane. The environment's reward does not depend on the rules of any task.

## Proposition semantics

All four are events: each is true only on the step it happens, false on every other step. Several events can be true on one step.

| id | kind | true when |
|---|---|---|
| `top_breach` | event | a zombie stepped past the left end of the top lane at this step |
| `side_breach` | event | a zombie stepped past the left end of the middle or the bottom lane at this step |
| `plant_trampled` | event | the agent moved onto a plant at this step, and the plant died |
| `zombie_killed` | event | the agent moved onto a zombie at this step, and the zombie died |

## Constraints

- `top_breach` and `side_breach` cannot become true before step 28: a zombie needs 9 moves of 3 steps from its entry to get through.
- `plant_trampled` and `zombie_killed` never hold together: the agent lands on one cell per step, and a cell holds a plant or a zombie, never both, because plants are off the lanes.

## What the agent can and cannot do

- Can: turn; move forward onto an empty cell, a plant or a zombie; walk along or across any lane.
- Cannot: walk through the outer wall; hold, drop or toggle anything.
- The agent never gets hurt. Standing in a lane stops no zombie: it walks through the agent's cell.
- A zombie killed by the agent does not breach anything. A zombie nobody touches always gets through, 27 steps after it entered.
- More than one zombie can walk the same lane, and zombies on different lanes can get through on the same step, so `top_breach` and `side_breach` can hold together.
- A plant can lie on the shortest walk between two lanes; the agent can walk around it.
- A plant cannot sprout on the agent's cell. Plants sprout only until 3 are alive; killed plants free a place for the next try.
- How many zombies enter in an episode depends on the seed and on how often the entry cells are free: 18 to 37 in 40 episodes of an idle agent.

## Example trace

A real episode: 300 steps, 21 zombies killed, reward 21, no zombie through the top lane.

1. steps 1 to 9, the agent waits: no changes
2. step 10, a zombie enters the middle lane: no proposition changes
3. steps 11 to 14, turns and moves right along the middle lane: no changes
4. `forward` (step 15): `zombie_killed` true
5. step 16, a turn: `zombie_killed` false
6. step 37, a zombie enters the top lane; steps 38 to 45, the agent walks up to the top lane: no changes
7. `forward` (step 46): `zombie_killed` true
8. steps 47 to 237, the agent keeps killing zombies of the top and middle lanes: eleven more `zombie_killed` steps, no breach
9. `forward` (step 238): `side_breach` true, a zombie got through a side lane while the agent was busy elsewhere
10. steps 239 to 300: more kills, three more `side_breach` steps; `top_breach` never true [episode cut at the step limit]

The episode shows that a guard that holds the top lane can keep it for the whole episode, while it loses some side-lane zombies in the busy end of the episode.

## Propositions
- `top_breach`: A zombie got through the top lane of the field.
- `side_breach`: A zombie got through one of the other two lanes of the field.
- `plant_trampled`: The agent stepped on a plant and killed it.
- `zombie_killed`: The agent killed a zombie by moving onto it.

## Example tasks

- Never let a zombie through the top lane.
- Try not to let zombies through the other lanes.
- Try not to step on plants.
