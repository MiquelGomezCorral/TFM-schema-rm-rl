"""Live check of the forced starts (``app/src/arm_fm/forced_starts.py``).

Usage (from the repository root):
    PYTHONPATH=app python experiments/benchmark/scripts/check_forced_starts.py [--seeds 20] [--table]

For reset seeds 1..N it checks, on ``MiniGrid-BlockedUnlockPickup-Cleared-v0``, that the layout is
the plain level's for the same seed except for the ball (in the start room, off the cell in front
of the door), that the hands are empty and the door locked, that ``blocker_moved`` is true at the
first step and for a whole idle episode and the rule ``Response(blocker_moved, has_door_key)`` then
fails, and that a scripted agent still takes the key, opens the door and takes the box. On
``MiniGrid-UnlockPickup-KeyHeld-v0`` it checks the plain layout without the key on the floor, the
key of the door's color in the hands, ``has_door_key`` true at the first step and for a whole idle
episode with ``RespondedExistence(has_door_key, door_open)`` failing, that ``drop`` on the first
step keeps the key and a later ``drop`` puts it down, and that a scripted agent still opens the
door and takes the box. ``--table`` prints one line per seed. Exits non-zero when a check fails.
"""

import argparse
import sys

from minigrid.core.actions import Actions

from src.arm_fm.environments import make_environment
from src.arm_fm.forced_starts import CLEARED_ID, KEY_HELD_ID
from src.benchmark.declare_judge import judge_trace
from src.benchmark.plans import run_plan

PLAIN = {CLEARED_ID: "MiniGrid-BlockedUnlockPickup-v0", KEY_HELD_ID: "MiniGrid-UnlockPickup-v0"}
IDLE_STEPS = 100
RULES = {
    CLEARED_ID: [("Response", ["blocker_moved", "has_door_key"], "hard")],
    KEY_HELD_ID: [("RespondedExistence", ["has_door_key", "door_open"], "hard")],
}
TRIGGER = {CLEARED_ID: "blocker_moved", KEY_HELD_ID: "has_door_key"}
TAKE_BOX = [{"do": "toggle", "obj": "door"}, {"do": "drop"}, {"do": "pickup", "obj": "box"}]
SOLVE = {CLEARED_ID: [{"do": "pickup", "obj": "key"}, *TAKE_BOX], KEY_HELD_ID: TAKE_BOX}


def layout(gym_id: str, seed: int) -> dict:
    """What a reset seed builds: the agent, the mission and every object by type."""
    env = make_environment(gym_id)
    env.reset(seed=seed)
    base = env.unwrapped
    objects = {}
    for x in range(base.width):
        for y in range(base.height):
            item = base.grid.get(x, y)
            if item is not None and item.type != "wall":
                objects[item.type] = (x, y, item.color)
    carrying = base.carrying
    return {
        "agent": (*map(int, base.agent_pos), int(base.agent_dir)),
        "mission": base.mission,
        "objects": objects,
        "carrying": None if carrying is None else (carrying.type, carrying.color),
        "door_locked": base.grid.get(*objects["door"][:2]).is_locked,
    }


def same_layout(gym_id: str, seed: int, forced: dict) -> bool:
    """The forced layout is the plain one, bar the moved ball or the key in the hands."""
    plain = layout(PLAIN[gym_id], seed)
    left_out = "ball" if gym_id == CLEARED_ID else "key"
    objects = {kind: cell for kind, cell in forced["objects"].items() if kind != left_out}
    plain_objects = {kind: cell for kind, cell in plain["objects"].items() if kind != left_out}
    return (
        forced["agent"] == plain["agent"]
        and forced["mission"] == plain["mission"]
        and objects == plain_objects
    )


def start_is_forced(gym_id: str, forced: dict) -> bool:
    """Check the forced start.

    Cleared: ball off the door's front cell, in the start room, hands empty, door locked.
    KeyHeld: no key on the floor, the door's key in the hands, door locked.
    """
    door_x, door_y, door_color = forced["objects"]["door"]
    if not forced["door_locked"]:
        return False
    if gym_id == KEY_HELD_ID:
        return forced["carrying"] == ("key", door_color) and "key" not in forced["objects"]
    ball_x, ball_y, _ = forced["objects"]["ball"]
    # Manhattan distance to the cell in front of the door
    front_distance = abs(ball_x - (door_x - 1)) + abs(ball_y - door_y)
    return (
        forced["carrying"] is None
        and front_distance >= 2
        and ball_x < door_x
        and forced["objects"]["key"][2] == door_color
    )


def idle_trace(gym_id: str, seed: int):
    """An agent that does nothing for ``IDLE_STEPS`` steps, as a plan rollout."""
    env_spec = {"gym_id": gym_id, "env_kwargs": {}}
    return run_plan(env_spec, [{"do": "wait", "n": IDLE_STEPS}], seed)


def drop_checks(seed: int) -> tuple[bool, bool]:
    """KeyHeld: ``drop`` on the first step keeps the key; a later ``drop`` puts it down."""
    env = make_environment(KEY_HELD_ID)
    env.reset(seed=seed)
    base = env.unwrapped
    env.step(int(Actions.drop))
    kept = base.carrying is not None
    for _ in range(8):  # turn until the cell in front is free, then drop
        env.step(int(Actions.drop))
        if base.carrying is None:
            break
        env.step(int(Actions.right))
    return kept, base.carrying is None


def check_seed(gym_id: str, seed: int) -> dict[str, bool]:
    forced = layout(gym_id, seed)
    idle = idle_trace(gym_id, seed)
    trigger = TRIGGER[gym_id]
    results = {
        "layout": same_layout(gym_id, seed, forced),
        "start": start_is_forced(gym_id, forced),
        "trigger_at_first_step": idle.labels[0][trigger],
        "trigger_all_idle": all(step[trigger] for step in idle.labels),
        "idle_fails_rule": not judge_trace(RULES[gym_id], idle.labels).success,
    }
    solve = run_plan({"gym_id": gym_id, "env_kwargs": {}}, SOLVE[gym_id], seed)
    results["solve_reaches_box"] = solve.terminated and solve.env_rewards[-1] > 0
    if gym_id == KEY_HELD_ID:
        kept, dropped = drop_checks(seed)
        results["first_drop_keeps_key"], results["later_drop_works"] = kept, dropped
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--seeds", type=int, default=20, help="reset seeds 1..N (default 20)")
    parser.add_argument("--table", action="store_true", help="print one line per seed")
    args = parser.parse_args()

    failed = 0
    for gym_id in (CLEARED_ID, KEY_HELD_ID):
        per_seed = {seed: check_seed(gym_id, seed) for seed in range(1, args.seeds + 1)}
        if args.table:
            for seed, results in per_seed.items():
                state = layout(gym_id, seed)
                first = idle_trace(gym_id, seed).labels[0]
                true_now = sorted(name for name, value in first.items() if value)
                print(
                    f"{gym_id} seed {seed}: {state['objects']} agent {state['agent']} "
                    f"true at first step {true_now} {results}"
                )
        for name in next(iter(per_seed.values())):
            passed = sum(results[name] for results in per_seed.values())
            failed += passed != args.seeds
            print(f"{gym_id} {name}: {passed}/{args.seeds}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
