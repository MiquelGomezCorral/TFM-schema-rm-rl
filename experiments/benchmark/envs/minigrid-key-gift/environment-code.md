# MiniGrid KeyGift: code notes

Addition to `environment.md`; read both. Facts live there; this file says where they come from and how code reads them.

## Source and runtime

- Source: `app/src/arm_fm/forcing_envs.py:KeyGiftEnv` and `GiftDoor`, a MiniGrid environment written for this project on the Farama base <https://github.com/Farama-Foundation/Minigrid>. Importing `src.arm_fm.environments` registers it.
- Gymnasium ID: `MiniGrid-KeyGift-v0`. Keyword argument: `max_steps` (int, default 300).
- Runtime: `minigrid==3.1.0`, `gymnasium==1.3.0`, pinned in `requirements.txt`.
- `reset(seed=s)` seeds the whole schedule. Without a seed it draws one from the environment's own random stream. Either way `reset` returns the seed it used as `info["event_seed"]`, beside `info["events"]`.
- The observation is MiniGrid's standard 7 x 7 x 3 partial view.
- `[code: file:function]` is `forcing_envs.py` unless a MiniGrid path is given. `[run: check]` is `experiments/benchmark/scripts/check_forcing.py` on the real environment, reset seeds 1 to 20.

## Truth conditions in code

Both read the state after the step.

| id | expression |
|---|---|
| `has_door_key` | `env.carrying is not None and env.carrying.type == "key"` |
| `door_open` | `any(cell is not None and cell.type == "door" and cell.is_open for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])` |

## Evidence

- Environment, layout: 7 x 7 room, yellow locked door at (3, 0), agent at (3, 3) facing up, hands empty, nothing else in the grid [code: `KEY_GIFT_SIZE`, `DOOR_POS`, `KEY_GIFT_START`, `_gen_grid`; run: check, layout, 20/20].
- Environment, a gift lands only with empty hands and a shut door, never in the last 20 steps [code: `step`, `GIFT_CHANCE`, `GIFT_QUIET_END`; run: check, random walks, 6000/6000 steps; the guard's last gift in 20 episodes came at step 277].
- Environment, `drop` does nothing [code: `step` turns `drop` into `done`; run: check, random walks, a `drop` with the key held never empties the hands, 6000/6000 steps]. `pickup` and `toggle` find nothing to act on without the key [code: `GiftDoor.toggle` returns False without a carried key; MiniGrid `Door.can_pickup` is False].
- Environment, the key is used up and the door opens [code: `answer_gift`, `GiftDoor.toggle`]. It shuts and locks 10 steps after opening, so it is open on 10 steps [code: `RELOCK_AFTER`, `step`; run: check, guard, open on step 9 after the opening and shut and locked on step 10, 20/20 episodes].
- Environment, the doorway is in the outer wall: the agent never stands on it [code: `GiftDoor.can_overlap` is False; run: check, random walks, 6000/6000 steps].
- Environment, a toggle of the open door does nothing [code: `GiftDoor.toggle` returns False when `is_open`].
- Environment, with nothing done the first key stays in the hands and the door never opens [run: check, idle, 20 episodes: 20 gifts, door never open, key held at the end 20/20; the first gifts came at steps 4, 6, 7, 8, 9 and later].
- Environment, the door is at most 10 actions away from any floor cell and facing, inside the 20-step quiet end [run: check, worst walk from the 100 poses, 10 actions including the toggle].
- Objective, step limit 300, no other end [code: `MAX_STEPS`; `step` returns MiniGrid's truncation only]. Reward 1 per answered gift [code: `step`]. `success` is true while every gift was answered [code: `success`; run: check, idle, flag false in 20/20; guard, every gift answered in 20/20 episodes, each within 10 steps].
- Constraints, `door_open` after `has_door_key`: the door opens only through `GiftDoor.toggle` with a carried key [code: `GiftDoor.toggle`; run: check, guard, 20/20]. `has_door_key` and `door_open` never together [code: `answer_gift` empties the hands in the same call that opens the door; `step` gives a key only while the door is shut; run: check, random walks, 6000/6000 steps].
- Same seed and same actions give the same episode [code: `reset`, `_plan_events`].
- Example trace: seed 1, scripted guard `scripted_policy`: 300 steps, 8 gifts at steps 10, 62, 76, 94, 177, 195, 240 and 257, each answered by a `toggle` (step 13, then the next step each time), reward 8 [run: check].

## Labeling API

- `env.carrying`: the carried object, or `None`; it exposes `type` and `color`. The gifted key has `type == "key"`. Carry state comes from it.
- `env.events_this_step`: list of strings for the step that just ended, empty when nothing happened. It can hold `"gift"` (the key landed in the hands) and `"answer"` (the door was opened with the key).
- `env.agent_pos`: the agent position as `(x, y)`.
- `env.agent_dir`: the facing direction as `0` right, `1` down, `2` left, `3` up.
- `env.grid.get(x, y)`: the object at that cell, or `None` when the cell is empty. Grid coordinates use `0 <= x < env.width` and `0 <= y < env.height`.
- Object attributes: `type` (`wall`, `door`, `key`), `color`, and `is_open` and `is_locked` on the door. Door openness and lock state come from them.
- `env.width`, `env.height`: grid size (7 x 7).

Object classes cannot be imported. To scan the grid, guard empty cells with `cell is not None` before reading an attribute. This expression checks whether any cell holds a given object type:

    any(cell is not None and cell.type == "<type>" for x in range(env.width) for y in range(env.height) for cell in [env.grid.get(x, y)])
