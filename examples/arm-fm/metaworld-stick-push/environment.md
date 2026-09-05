# Meta-World Stick-Push

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Metaworld>
- Gymnasium construction: `gym.make("Meta-World/MT1", env_name="stick-push-v3")`.
- Reproduction status: ARM-FM used an unpublished sparse-reward adaptation.

## Environment

A Sawyer robot controls end-effector displacement and gripper opening. The robot must
approach and grasp a stick, then use the stick to push a separate container or box to a
target location. The stick is the manipulated tool; the pushed object determines task
success.

## Objective and episode boundary

Success requires retaining control of the stick while the pushed object reaches the
target threshold. The official MT1 wrapper supplies the episode limit; ARM-FM retains
sparse task success.

## Proposition semantics

These are persistent conditions over the current robot, stick, and pushed-object state.

## Propositions
- `near_stick`: The gripper is within the environment's reach threshold of the stick.
- `stick_grasped`: The gripper has successfully grasped and lifted the stick.
- `pushed_object_near_goal`: The box or container is close to its target but outside the success threshold.
- `push_complete`: The stick remains controlled and the pushed object is within its target threshold.

## Example tasks

- Eventually push the object to its target.
- Grasp the stick before completing the push.
- Move the pushed object near the goal before completing the task.

