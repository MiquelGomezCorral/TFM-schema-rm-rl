# Meta-World Pick-Place

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Metaworld>
- Gymnasium construction: `gym.make("Meta-World/MT1", env_name="pick-place-v3")`.
- Reproduction status: ARM-FM used an unpublished sparse-reward adaptation.

## Environment

A Sawyer robot controls end-effector displacement and gripper opening. A puck-like
object begins on the table and a 3D target position is sampled separately. The robot
must approach, grasp, lift, transport, and release or hold the object at the target.

## Objective and episode boundary

Success occurs when the object is within the environment's target-distance threshold.
The official MT1 wrapper supplies the episode limit; ARM-FM retains sparse success for
its comparison.

## Proposition semantics

These are persistent conditions over the current robot and object state.

## Propositions
- `near_object`: The gripper is within the environment's reach threshold of the object.
- `object_grasped`: The gripper has successfully grasped and lifted the object.
- `object_near_goal`: The object is close to the target position but outside the success threshold.
- `object_at_goal`: The object is within the environment's success threshold of the target position.

## Example tasks

- Eventually place the object at its goal.
- Grasp the object before placing it at the goal.
- Move the object near the goal before completing placement.

