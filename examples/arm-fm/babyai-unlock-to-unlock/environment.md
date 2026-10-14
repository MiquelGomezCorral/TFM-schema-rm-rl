# BabyAI UnlockToUnlock

## Source and runtime

- Official source: <https://github.com/Farama-Foundation/Minigrid>
- ARM-FM artifacts: <https://github.com/roger-creus/llms-rm-rl/tree/main/reward_machines/UnlockToUnlock>
- Gymnasium ID: `BabyAI-UnlockToUnlock-v0`.
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- Evidence tags: `[code: file:function]` is MiniGrid 3.1.0 source (`minigrid/...`); `[run]` is a scripted run or check on the real environment with `minigrid_family.py unlocktounlock`, `layout_checks.py`, `mechanics_check.py` ; `unknown` means no source says.

## Environment

Three rooms form a chain. The target ball is in the goal-side room. The door into that
room requires one colored key, but that key is itself behind another locked door with
a different matching key. The two colors are sampled by the environment, so task
semantics must use prerequisite/target roles rather than fixed color names.

Layout [code: babyai/unlock.py:UnlockToUnlock.gen_mission; run: `layout_checks.py`, 300 seeds]: three 6x6 rooms in a row (grid 16x6). The agent starts in the middle room. The ball lies in the left room. Door A, between left and middle, is locked and has its key A in the right room. Door B, between middle and right, is locked and has its key B in the middle room, with the agent. The two colors differ. The mission is exactly `pick up the ball`. Names in the propositions: the prerequisite door is door B and its key is key B; the target door is door A and its key is key A. Actions are seven discrete keys: `left`, `right`, `forward`, `pickup`, `drop`, `toggle`, `done`; `done` does nothing [code: minigrid_env.py:step].

## Objective and episode boundary

The mission is to pick up the ball by resolving both key-door dependencies. The stock
environment terminates when the ball is picked up and truncates at its step limit.

Step limit `30 * 6**2 = 1080` [code: UnlockToUnlock.__init__]. Picking up the ball ends the episode [run: `minigrid_family.py unlocktounlock`, terminated at the pickup].

## Proposition semantics

“Prerequisite” identifies the first key and door that must be handled to gain access to
the key for the target-side door. “Target-side” identifies the second dependency.

| id | kind | true when |
|---|---|---|
| `has_prerequisite_key` | condition | `env.carrying` is a key of door B's color |
| `prerequisite_door_open` | condition | door B's `is_open` is true; false again if toggled shut |
| `has_target_door_key` | condition | `env.carrying` is a key of door A's color |
| `target_door_open` | condition | door A's `is_open` is true; false again if toggled shut |
| `target_ball_picked_up` | condition, final step only | `env.carrying` is the ball |
| `required_key_lost` | event, reading | key B was carried at the previous step, is not carried now, and door B is not open now; or the same for key A and door A; false on every other step |

`required_key_lost` reading: the description does not say whether it is an event or lingers. The table makes it an event, per key: the labeling code reads one step of memory (`previous_valuation`) and the project's labeling prompt treats `key_lost` as an event. A lingering "true until picked up again" form needs to know which key was lost, and one step of memory cannot say. The published RM maps `lost_y_key` to it "in the prerequisite stage" and `lost_r_key` "in the target-door stage" [`task-rm-pairs.md:17,20`]. Fired in 135 of 300 random episodes [run: `minigrid_family.py unlocktounlock explore`].

## Constraints

- `prerequisite_door_open` cannot become true before `has_prerequisite_key`: only `toggle` with the matching key unlocks a door [code: world_object.py:Door.toggle; run: `minigrid_family.py unlocktounlock explore`, 0 of 300 random episodes, 186 reached it].
- `target_door_open` cannot become true before `has_target_door_key`: same rule for door A [code: Door.toggle; run: same, 0 of 300, 38 reached it].
- `has_target_door_key` cannot become true before `prerequisite_door_open`: key A lies in the right room, behind door B [code: unlock.py:gen_mission; run: `layout_checks.py`, key A unreachable before door B opens in 300/300 seeds].
- `target_ball_picked_up` cannot become true before `target_door_open`: the ball lies in the left room, behind door A [code: unlock.py:gen_mission; run: `layout_checks.py`, 300/300 seeds].
- `has_prerequisite_key` and `has_target_door_key` never hold together: the agent holds one object. Key B must be dropped before key A is picked up [code: minigrid_env.py:step; run: `mechanics_check.py`, 0 of 300 random episodes].
- `has_prerequisite_key` and `target_ball_picked_up` never hold together: same rule [code: minigrid_env.py:step; run: same].
- `has_target_door_key` and `target_ball_picked_up` never hold together: key A must be dropped before the ball is picked up [code: minigrid_env.py:step; run: same].
- `required_key_lost` and `has_prerequisite_key` never hold together: the step a key leaves the hands is a `drop`, and the hands are empty after it [code: minigrid_env.py:step; run: `unlocktounlock_explore_stats.json`, 0 of 300].
- `required_key_lost` and `has_target_door_key` never hold together: same reason [code: minigrid_env.py:step; run: same].
- `required_key_lost` and `target_ball_picked_up` never hold together: same reason [code: minigrid_env.py:step; run: same].

## What the agent can and cannot do

- Can: turn; `forward` onto an empty cell or an open door; `pickup` a key or the ball with empty hands; `drop` onto an empty cell in front; `toggle` the door in front [code: minigrid_env.py:step].
- Cannot: open a door without its own key in hand; carry two objects; reach key A before door B is open or the ball before door A is open; drop onto an occupied cell [run: `mechanics_check.py`, `layout_checks.py`].
- A dropped key can block a doorway. It can be picked up again, so the task stays solvable [run: seen while writing `minigrid_family.py`].
- Dropping a key after its own door is open does not fire `required_key_lost`: key B must go before key A is picked up, key A before the ball, and the solver does both after the door is open.
- Dropping key B while door B is closed fires `required_key_lost` (135 of 300 random episodes had a firing [run: `unlocktounlock_explore_stats.json`]). The key can be picked up again.
- Doors can be toggled shut again and are never relocked [code: Door.toggle].

## Example trace

`BabyAI-UnlockToUnlock-v0`, seed 0, scripted solver [run: `minigrid_family.py unlocktounlock 0`, log `unlocktounlock_trace_seed0.jsonl`]. 39 steps, reward 0.968.

1. 4 turns and moves, no proposition changes
2. `pickup` (step 5): `has_prerequisite_key` true
3. 5 turns and moves, no proposition changes
4. `toggle` (step 11): `prerequisite_door_open` true
5. 1 turn or move, no proposition changes
6. `drop` (step 13): `has_prerequisite_key` false
7. 4 turns and moves, no proposition changes
8. `pickup` (step 18): `has_target_door_key` true
9. 9 turns and moves, no proposition changes
10. `toggle` (step 28): `target_door_open` true
11. 1 turn or move, no proposition changes
12. `drop` (step 30): `has_target_door_key` false
13. 8 turns and moves, no proposition changes
14. `pickup` (step 39): `target_ball_picked_up` true [episode terminated]

## Labeling API

- `env.mission`: the mission string, for example `pick up the grey box`. Mission targets
  come from it: do not assume a fixed color or object, match the designated one.
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid
  coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- Object attributes: `type` (for example `key`, `door`, `box`, `ball`, `wall`, `goal`),
  `color`, and `is_open` and `is_locked` on doors. Door openness and lock state come from
  them.
- `env.carrying`: the carried object, or `None`; it exposes `type` and `color`. Carry state
  comes from it.
- `env.width`, `env.height`: grid size.

Object classes cannot be imported. To scan the grid, guard empty cells with
`cell is not None` before reading an attribute. This expression checks whether any cell holds
a given object type:

    any(cell is not None and cell.type == "<type>" for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])

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
