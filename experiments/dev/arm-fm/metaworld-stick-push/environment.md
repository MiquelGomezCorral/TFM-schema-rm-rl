# Meta-World Stick-Push

## Environment

A Sawyer arm with a two-finger gripper holds a stick (a box 0.1 x 0.04 x 0.04 m) and pushes a thermos to a target point on the table. The stick is the manipulated tool; the thermos is the pushed object.

- Reset: the stick starts on the table at x in [-0.08, -0.03], y in [0.58, 0.62], z 0.02. The thermos always starts at the same place, (0.2, 0.6, 0.132). The target is at x in [0.399, 0.401], y in [0.55, 0.6], z 0.132. The thermos starts 0.199 to 0.207 m from the target. The environment pre-draws 50 layouts when built and each reset picks one at random.
- The hand starts near (0.005, 0.601, 0.195) with the fingers open in every reset.
- The agent observes the hand position, how open the fingers are (1.0 open, lower is more closed), the stick position and orientation, the thermos position, the same values from the previous step, and the target position.
- Action: four numbers in [-1, 1]: hand displacement along x, y, z, then gripper effort. A positive effort closes the fingers, a negative one opens them.

## Objective and episode boundary

- Success needs two things in the same step: the stick is held and the thermos is within 0.12 m of the target. The reward is dense and is 10 only for the same pair.
- The environment never ends the episode by itself. Success does not end it. The episode is cut off at step 500, and stepping after that is an error.
- The environment reports no values before the first step.

## Proposition semantics

Valuation after each step. Let `d` = distance from the thermos to the target. The fingertip midpoint is the point halfway between the two fingertips.

| id | kind | true when |
|---|---|---|
| `near_stick` | condition | the environment's near-object flag is on: the distance from the fingertip midpoint to the point 0.015 m in the +x direction from the stick centre is at most 0.03 m |
| `stick_grasped` | condition | the environment's grasp flag is on: both finger pads press on the stick with positive contact force, the finger opening is above 0, and the stick centre is more than 0.01 m above its start height, so z above 0.03 |
| `pushed_object_near_goal` | condition, reading | `0.12 < d <= 0.18` |
| `push_complete` | condition | the environment reports success: `stick_grasped` holds and `d <= 0.12` |

`pushed_object_near_goal` reading: this file uses a band of 1.5 times the success radius. It stays false at reset and excludes the success distance. The task's own threshold is not known.

After the first step all four are false. It is not known what the four are at reset, before the first step, because the environment reports no values there.

## Constraints

- `push_complete` cannot become true before `stick_grasped`: success is the stick held and `d <= 0.12`.
- `pushed_object_near_goal` and `push_complete` never hold together: the first needs `d > 0.12`, the second `d <= 0.12`.

## What the agent can and cannot do

- Can: move the hand inside x in [-0.5, 0.5], y in [0.40, 1.0], z in [0.05, 0.5] (the hand's target is clipped to this box); open and close the fingers; lift, carry and drop the stick; push the thermos.
- Cannot: rotate the hand (orientation is fixed). There is no pick or drop action: holding comes from finger contact.
- The environment does not check that the stick touches the thermos. It checks the thermos position and that the stick is held. It is not known whether the thermos can be moved without the stick.
- `push_complete` has no latch and turns false as soon as the stick is released or dropped, even with the thermos at the target.
- `pushed_object_near_goal` is false once the thermos is inside 0.12 m, whether or not the stick is held. So a thermos at the target with the stick not held makes both `pushed_object_near_goal` and `push_complete` false.
- `near_stick` can hold with the stick not lifted or not held (a hand beside it).

## Example trace

One real episode; first success at step 77, then the episode runs to the 500-step cut-off. Step N is the valuation after the N-th action.

1. steps 1 to 21: the hand moves above the stick, all false
2. step 22: `near_stick` true
3. step 34: `stick_grasped` true
4. step 72: `pushed_object_near_goal` true
5. step 77: `pushed_object_near_goal` false, `push_complete` true
6. step 151: `stick_grasped` false, `push_complete` false (the gripper opens)
7. step 155: `near_stick` false; step 216: `near_stick` true; steps 217 to 500: no change, with the thermos still 0.057 m from the target

## Propositions
- `near_stick`: The gripper is within the environment's reach threshold of the stick.
- `stick_grasped`: The gripper has successfully grasped and lifted the stick.
- `pushed_object_near_goal`: The box or container is close to its target but outside the success threshold.
- `push_complete`: The stick remains controlled and the pushed object is within its target threshold.

## Example tasks

- Eventually push the object to its target.
- Grasp the stick before completing the push.
- Move the pushed object near the goal before completing the task.
