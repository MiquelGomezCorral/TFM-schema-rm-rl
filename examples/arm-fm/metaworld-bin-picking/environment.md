# Meta-World Bin-Picking

## Environment

A Sawyer arm with a two-finger gripper lifts a green cube (side 0.04 m) out of one bin and drops it in a second bin.

- Layout: the start bin is centred at (-0.12, 0.7), the target bin at (0.12, 0.7). The target is the centre of the target bin, (0.12, 0.7, 0.0), in every reset.
- Reset: only the cube moves. It starts at x in [-0.21, -0.03], y in [0.65, 0.75], z 0.03. The bounds were chosen so the cube starts inside the start bin. The bin wall geometry is not known. The environment pre-draws 50 layouts when built and each reset picks one at random.
- The hand starts near (0.005, 0.601, 0.195) with the fingers open in every reset.
- The agent observes the hand position, how open the fingers are (1.0 open, lower is more closed), the cube position and orientation, the same values from the previous step, and the target position.
- Action: four numbers in [-1, 1]: hand displacement along x, y, z, then gripper effort. A positive effort closes the fingers, a negative one opens them.

## Objective and episode boundary

- Success is a distance test: the cube centre is within 0.05 m of the target bin centre. It does not test that the cube is inside the bin. The reward is dense and saturates at 10 when the distance is below 0.05 m.
- The environment never ends the episode by itself. Success does not end it. The episode is cut off at step 500, and stepping after that is an error.
- The environment reports no values before the first step.

## Proposition semantics

Valuation after each step. Let `d` = distance from the cube centre to the target bin centre.

| id | kind | true when |
|---|---|---|
| `near_object` | condition | the environment's near-object flag is on: the distance from the hand body (not the fingertip midpoint) to the cube centre is below 0.04 m |
| `object_grasped` | condition | the environment's grasp flag is on: `near_object` holds, the cube centre is more than 0.02 m above its start height, and the finger opening is at least 0.43 (fingers not pinched shut on nothing) |
| `object_near_target_bin` | condition, reading | `0.05 < d <= 0.075` |
| `object_in_target_bin` | condition | the environment reports success: `d <= 0.05` |

`object_near_target_bin` reading: this file uses a band of 1.5 times the success radius. It stays false at reset and excludes success. The task's own threshold is not known.

After the first step all four are false. It is not known what the four are at reset, before the first step, because the environment reports no values there.

## Constraints

- `object_grasped` cannot become true before `near_object`: the grasp flag requires `near_object`, a lifted cube and fingers not pinched.
- `object_near_target_bin` and `object_in_target_bin` never hold together: the first needs `d > 0.05`, the second `d <= 0.05`.

## What the agent can and cannot do

- Can: move the hand inside x in [-0.5, 0.5], y in [0.40, 1.0], z in [0.07, 0.5] (the hand's target is clipped to this box); open and close the fingers; push, lift, carry and drop the cube.
- Cannot: rotate the hand (orientation is fixed). There is no pick or drop action: holding comes from finger contact.
- `near_object` can turn false while the cube is held: a held cube sits about 0.04 m from the hand body, right at the threshold. `object_grasped` flickers with it.
- `object_in_target_bin` has no latch, so it can turn false again.
- Success has no grasp term. It is not known whether the cube can reach the target without `object_grasped` ever firing.
- It is not known whether the cube can be pushed out of reach for good.

## Example trace

One real episode; first success at step 120, then the episode runs to the 500-step cut-off. Step N is the valuation after the N-th action.

1. steps 1 to 43: the hand moves above the cube, all false
2. step 44: `near_object` true
3. step 46: `near_object` false
4. step 63: `near_object` true
5. step 69: `object_grasped` true
6. step 117: `object_near_target_bin` true
7. step 120: `object_grasped` false, `object_near_target_bin` false, `object_in_target_bin` true
8. steps 121 to 500: no change; the episode ends by truncation

## Propositions
- `near_object`: The gripper is within the environment's reach threshold of the object.
- `object_grasped`: The gripper has successfully grasped and lifted the object.
- `object_near_target_bin`: The object is close to the target bin but success is not yet achieved.
- `object_in_target_bin`: The object is within the environment's success threshold for the target bin.

## Example tasks

- Eventually place the object in the target bin.
- Grasp the object before placing it in the target bin.
- Move the object near the target bin before completing placement.
