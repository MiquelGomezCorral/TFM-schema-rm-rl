# Meta-World Assembly

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Metaworld>
- Gymnasium construction: `gym.make("Meta-World/MT1", env_name="assembly-v3")`.
- Reproduction status: ARM-FM used a sparse-reward adaptation whose wrapper and exact
  configuration are not published in its repository.

## Environment

A Sawyer robot controls end-effector displacement and gripper opening. A nut and peg
are placed within randomized bounds. The task requires approaching and grasping the
nut, aligning it with the peg, and placing it onto the peg.

## Objective and episode boundary

Success occurs when the nut is aligned with and hooked onto the peg. The official MT1
wrapper supplies the episode limit; ARM-FM removes dense task shaping and retains a
sparse success signal for its comparison.

## Proposition semantics

These are persistent conditions over the current robot and object state.

## Propositions
- `near_nut`: The gripper is within the environment's reach threshold of the nut.
- `nut_grasped`: The gripper has successfully grasped and controls the nut.
- `nut_near_peg`: The nut is positioned close to the target peg but assembly is not yet complete.
- `assembly_complete`: The nut is correctly aligned with and hooked onto the peg.

## Example tasks

- Eventually complete the assembly.
- Grasp the nut before completing the assembly.
- Move the nut near the peg before completing the assembly.

