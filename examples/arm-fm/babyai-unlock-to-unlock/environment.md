# BabyAI UnlockToUnlock

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/UnlockToUnlock>
- Gymnasium ID: `BabyAI-UnlockToUnlock-v0`.

## Environment

Three rooms form a chain. The target ball is in the goal-side room. The door into that
room requires one colored key, but that key is itself behind another locked door with
a different matching key. The two colors are sampled by the environment, so task
semantics must use prerequisite/target roles rather than fixed color names.

## Objective and episode boundary

The mission is to pick up the ball by resolving both key-door dependencies. The stock
environment terminates when the ball is picked up and truncates at its step limit.

## Proposition semantics

“Prerequisite” identifies the first key and door that must be handled to gain access to
the key for the target-side door. “Target-side” identifies the second dependency.

## Propositions
- `has_prerequisite_key`: The agent is carrying the key for the prerequisite door.
- `prerequisite_door_open`: The prerequisite door is currently open.
- `has_target_door_key`: The agent is carrying the key for the door guarding the target ball.
- `target_door_open`: The door guarding the target ball is currently open.
- `target_ball_picked_up`: The agent is currently carrying the mission's ball.
- `required_key_lost`: A currently required key was acquired and then lost before its door was opened.

## Example tasks

- Eventually pick up the target ball.
- Open the prerequisite door before acquiring the target-door key.
- Open the target-side door before picking up the ball.

