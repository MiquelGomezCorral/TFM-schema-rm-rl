# Meta-World Assembly

## Environment

A Sawyer arm with a two-finger gripper picks up a "nut" and puts it on a vertical peg. The nut is one rigid body: a ring plus a handle 0.13 m long, like a wrench. The agent grasps the handle; the ring goes over the peg.

- Reset: the nut is not randomized. The ring starts at (0, 0.6, 0.02) and the handle end at (0.13, 0.6, 0.02). Only the peg moves: its top, the target, is at x in [-0.1, 0.1], y in [0.75, 0.85], z 0.1. The layout is redrawn until nut and target are at least 0.1 m apart in the x-y plane. The environment pre-draws 50 layouts when built and each reset picks one at random.
- The hand starts near (0.005, 0.601, 0.195) with the fingers open in every reset.
- The agent observes the hand position, how open the fingers are (1.0 open, lower is more closed), the handle end position, the nut orientation, the same values from the previous step, and the target position.
- Action: four numbers in [-1, 1]: hand displacement along x, y, z, then gripper effort. A positive effort closes the fingers, a negative one opens them.

## Objective and episode boundary

- Success: the ring centre is within 0.02 m of the peg top in the x-y plane (aligned) and below the peg top (hooked). The reward is dense and is 10 on success.
- The environment never ends the episode by itself. Success does not end it. The episode is cut off at step 500, and stepping after that is an error.
- The environment reports no values before the first step.

## Proposition semantics

Valuation after each step. Let `d` = distance from the ring centre to the target. The fingertip midpoint is the point halfway between the two fingertips.

| id | kind | true when |
|---|---|---|
| `near_nut` | condition, reading | distance from the fingertip midpoint to the handle end is at most 0.03 m |
| `nut_grasped` | condition | the environment's grasp flag is on, meaning its grasp reward is at least 0.5. That reward averages a finger-caging term and a reach term; it has no contact test and no lift test |
| `nut_near_peg` | condition, reading | `d < 0.05` and `assembly_complete` is false |
| `assembly_complete` | condition | the environment reports success: ring aligned and hooked, as above |

`near_nut` reading: this file uses a distance test with 0.03 m. This task's own threshold is not known.

`nut_near_peg` reading: this file uses `d < 0.05` (the success radius is 0.02 m in x-y). It stays false at reset, and the condition excludes success. The task's own threshold is not known.

After the first step all four are false. It is not known what the four are at reset, before the first step, because the environment reports no values there.

## Constraints

- `nut_near_peg` and `assembly_complete` never hold together: the reading requires `assembly_complete` false.

No other order is guaranteed; see below.

## What the agent can and cannot do

- Can: move the hand inside x in [-0.5, 0.5], y in [0.40, 1.0], z in [0.05, 0.5] (the hand's target is clipped to this box); open and close the fingers; lift, carry, drop and push the nut.
- Cannot: rotate the hand (orientation is fixed). There is no pick or drop action: holding comes from finger contact.
- `assembly_complete` does not need `nut_grasped`: success has no grasp term, so it can stay true for long stretches with `nut_grasped` false.
- `nut_grasped` flickers: it can turn false again after it was true.
- `assembly_complete` has no latch, so it can turn false again.
- It is not known whether the nut can be pushed out of reach for good.

## Example trace

One real episode; first success at step 91, then the episode runs to the 500-step cut-off. Step N is the valuation after the N-th action.

1. steps 1 to 24: the hand moves above the handle, all false
2. step 25: `near_nut` true
3. step 32: `nut_grasped` true
4. steps 49 to 67: `nut_grasped` false, then true again at step 68
5. step 85: `nut_grasped` false
6. step 86: `nut_near_peg` true
7. step 91: `nut_near_peg` false, `assembly_complete` true
8. steps 92 to 500: `assembly_complete` stays true; `nut_grasped` is true again from step 102 to 230

## Propositions
- `near_nut`: The gripper is within the environment's reach threshold of the nut.
- `nut_grasped`: The gripper has successfully grasped and controls the nut.
- `nut_near_peg`: The nut is positioned close to the target peg but assembly is not yet complete.
- `assembly_complete`: The nut is correctly aligned with and hooked onto the peg.

## Example tasks

- Eventually complete the assembly.
- Grasp the nut before completing the assembly.
- Move the nut near the peg before completing the assembly.
