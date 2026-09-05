# Meta-World Shelf-Place

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Metaworld>
- Gymnasium construction: `gym.make("Meta-World/MT1", env_name="shelf-place-v3")`.
- Reproduction status: ARM-FM used an unpublished sparse-reward adaptation.

## Environment

A Sawyer robot controls end-effector displacement and gripper opening. An object begins
on the table and must be grasped, lifted, transported, and placed at a target location
on a shelf. Object and shelf positions vary within bounded reset regions.

## Objective and episode boundary

Success occurs when the object is within the shelf target's distance threshold. The
official MT1 wrapper supplies the episode limit; ARM-FM retains sparse task success.

## Proposition semantics

These are persistent conditions over the current robot and object state.

## Propositions
- `near_object`: The gripper is within the environment's reach threshold of the object.
- `object_grasped`: The gripper has successfully grasped and lifted the object.
- `object_near_shelf_goal`: The object is close to the shelf target but outside the success threshold.
- `object_on_shelf`: The object is within the environment's success threshold of the shelf target.

## Example tasks

- Eventually place the object on the shelf.
- Grasp the object before placing it on the shelf.
- Move the object near the shelf target before completing placement.

