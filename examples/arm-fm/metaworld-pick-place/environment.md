# Meta-World Pick-Place

## Environment

A Sawyer arm with a two-finger gripper moves a red cylinder (radius 0.02 m, height 0.04 m) to a target point in the air.

- Reset: the cylinder starts on the table at x in [-0.1, 0.1], y in [0.6, 0.7], z 0.02. The target is a point at x in [-0.1, 0.1], y in [0.8, 0.9], z in [0.05, 0.3]. The layout is redrawn until object and target are at least 0.15 m apart in the x-y plane. The environment pre-draws 50 layouts when built and each reset picks one at random.
- The hand starts near (0.005, 0.601, 0.195) with the fingers open in every reset.
- The agent observes the hand position, how open the fingers are (1.0 open, lower is more closed), the object position and orientation, the same values from the previous step, and the target position.
- Action: four numbers in [-1, 1]: hand displacement along x, y, z, then gripper effort. A positive effort closes the fingers, a negative one opens them.

## Objective and episode boundary

- Success is a distance test: the object centre is within 0.07 m of the target. The reward is dense and saturates at 10 only when the distance is below 0.05 m.
- The environment never ends the episode by itself. Success does not end it. The episode is cut off at step 500, and stepping after that is an error.
- The environment reports no values before the first step.

## Proposition semantics

Valuation after each step. Let `d` = distance from the object centre to the target. The fingertip midpoint is the point halfway between the two fingertips.

| id | kind | true when |
|---|---|---|
| `near_object` | condition | the environment's near-object flag is on: the distance from the fingertip midpoint to the object centre is at most 0.03 m |
| `object_grasped` | condition | the environment's grasp flag is on: both finger pads press on the object with positive contact force, the finger opening is above 0, and the object centre is more than 0.02 m above its start height, so z above 0.04 |
| `object_near_goal` | condition, reading | `0.07 < d <= 0.105` |
| `object_at_goal` | condition | the environment reports success: `d <= 0.07` |

`object_near_goal` reading: this file uses a band of 1.5 times the success radius. It stays false at reset and excludes success. The task's own threshold is not known.

After the first step all four are false. It is not known what the four are at reset, before the first step, because the environment reports no values there.

## Constraints

- `object_near_goal` and `object_at_goal` never hold together: the first needs `d > 0.07`, the second `d <= 0.07`.

No order between `object_grasped` and `object_at_goal` is guaranteed; see below.

## What the agent can and cannot do

- Can: move the hand inside x in [-0.5, 0.5], y in [0.40, 1.0], z in [0.05, 0.5] (the hand's target is clipped to this box); open and close the fingers; push, lift, carry and drop the object.
- Cannot: rotate the hand (orientation is fixed). There is no pick or drop action: holding comes from finger contact.
- `object_at_goal` does not need `object_grasped`: success has no grasp term. With the target z at most 0.09 a cylinder resting at z 0.02 is already within 0.07 m of it.
- `object_grasped` is a contact flag and can flicker: it can turn false again.
- `object_at_goal` has no latch, so it can turn false again.
- It is not known whether the object can be pushed out of reach for good.

## Example trace

One real episode; first success at step 59, then the episode runs to the 500-step cut-off. Step N is the valuation after the N-th action.

1. steps 1 to 22: the hand moves above the object, all false
2. step 23: `near_object` true
3. step 38: `object_grasped` true
4. step 54: `object_near_goal` true
5. step 59: `object_near_goal` false, `object_at_goal` true
6. steps 60 to 500: no change; the episode ends by truncation

## Propositions
- `near_object`: The gripper is within the environment's reach threshold of the object.
- `object_grasped`: The gripper has successfully grasped and lifted the object.
- `object_near_goal`: The object is close to the target position but outside the success threshold.
- `object_at_goal`: The object is within the environment's success threshold of the target position.

## Example tasks

- Eventually place the object at its goal.
- Grasp the object before placing it at the goal.
- Move the object near the goal before completing placement.
