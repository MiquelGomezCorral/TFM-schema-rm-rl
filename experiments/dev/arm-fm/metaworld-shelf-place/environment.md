# Meta-World Shelf-Place

## Environment

A Sawyer arm with a two-finger gripper moves a blue cube (side 0.04 m) from the table to a target point on a shelf.

- Reset: the cube starts on the table at x in [-0.1, 0.1], y in [0.5, 0.6], z 0.02. The shelf is moved so its target point sits at x in [-0.1, 0.1], y in [0.8, 0.9], z 0.3 (z in [0.299, 0.301]). The layout is redrawn until cube and target are at least 0.1 m apart in the x-y plane. The environment pre-draws 50 layouts when built and each reset picks one at random.
- The hand starts near (0.005, 0.601, 0.195) with the fingers open in every reset.
- The agent observes the hand position, how open the fingers are (1.0 open, lower is more closed), the cube position and orientation, the same values from the previous step, and the target position.
- Action: four numbers in [-1, 1]: hand displacement along x, y, z, then gripper effort. A positive effort closes the fingers, a negative one opens them.

## Objective and episode boundary

- Success is a distance test: the cube centre is within 0.07 m of the target point. It does not test that the cube rests on a shelf board. The reward is dense and saturates at 10 only when the distance is below 0.05 m.
- The environment never ends the episode by itself. Success does not end it. The episode is cut off at step 500, and stepping after that is an error.
- The environment reports no values before the first step.

## Proposition semantics

Valuation after each step. Let `d` = distance from the cube centre to the target. The fingertip midpoint is the point halfway between the two fingertips.

| id | kind | true when |
|---|---|---|
| `near_object` | condition | the environment's near-object flag is on: the distance from the fingertip midpoint to the cube centre is at most 0.03 m |
| `object_grasped` | condition | the environment's grasp flag is on: both finger pads press on the cube with positive contact force, the finger opening is above 0, and the cube centre is more than 0.02 m above its start height, so z above 0.04 |
| `object_near_shelf_goal` | condition, reading | `0.07 < d <= 0.105` |
| `object_on_shelf` | condition | the environment reports success: `d <= 0.07` |

`object_near_shelf_goal` reading: this file uses a band of 1.5 times the success radius. It stays false at reset and excludes success. The task's own threshold is not known.

After the first step all four are false. It is not known what the four are at reset, before the first step, because the environment reports no values there.

## Constraints

- `object_near_shelf_goal` and `object_on_shelf` never hold together: the first needs `d > 0.07`, the second `d <= 0.07`.

No other order is guaranteed; see below.

## What the agent can and cannot do

- Can: move the hand inside x in [-0.5, 0.5], y in [0.40, 1.0], z in [0.05, 0.5] (the hand's target is clipped to this box); open and close the fingers; push, lift, carry and drop the cube.
- Cannot: rotate the hand (orientation is fixed). There is no pick or drop action: holding comes from finger contact.
- `object_on_shelf` needs the cube centre at z of at least 0.229, because the target z is about 0.3 and `d <= 0.07`. So the cube must leave the table. It is not known whether it can get there without `object_grasped` ever firing.
- `object_grasped` is a contact flag and can flicker: it can turn false again. It can hold while `near_object` is false.
- `object_on_shelf` has no latch, so it can turn false again.
- It is not known whether the cube can be pushed out of reach for good.

## Example trace

One real episode; first success at step 98, then the episode runs to the 500-step cut-off. Step N is the valuation after the N-th action.

1. steps 1 to 31: the hand moves above the cube, all false
2. step 32: `near_object` true
3. step 42: `object_grasped` true
4. step 93: `object_near_shelf_goal` true
5. step 98: `object_near_shelf_goal` false, `object_on_shelf` true
6. steps 99 to 500: the hand keeps pushing; `object_grasped` flickers, `near_object` is false from step 120 to 160, and `object_on_shelf` is false from step 353 to 393 (with `object_near_shelf_goal` true) and true again after

## Propositions
- `near_object`: The gripper is within the environment's reach threshold of the object.
- `object_grasped`: The gripper has successfully grasped and lifted the object.
- `object_near_shelf_goal`: The object is close to the shelf target but outside the success threshold.
- `object_on_shelf`: The object is within the environment's success threshold of the shelf target.

## Example tasks

- Eventually place the object on the shelf.
- Grasp the object before placing it on the shelf.
- Move the object near the shelf target before completing placement.
