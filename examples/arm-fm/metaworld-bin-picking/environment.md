# Meta-World Bin-Picking

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Metaworld>
- Gymnasium construction: `gym.make("Meta-World/MT1", env_name="bin-picking-v3")`.
- Reproduction status: ARM-FM used an unpublished sparse-reward adaptation.

## Environment

A Sawyer robot controls end-effector displacement and gripper opening. An object starts
in one bin and must be lifted and placed in the target bin. Object and hand positions
vary within bounded reset regions.

## Objective and episode boundary

Success occurs when the object is within the target-bin threshold. The official MT1
wrapper supplies the episode limit; ARM-FM's comparison keeps only sparse task success.

## Proposition semantics

These are persistent conditions over the current robot and object state.

## Propositions
- `near_object`: The gripper is within the environment's reach threshold of the object.
- `object_grasped`: The gripper has successfully grasped and lifted the object.
- `object_near_target_bin`: The object is close to the target bin but success is not yet achieved.
- `object_in_target_bin`: The object is within the environment's success threshold for the target bin.

## Example tasks

- Eventually place the object in the target bin.
- Grasp the object before placing it in the target bin.
- Move the object near the target bin before completing placement.

