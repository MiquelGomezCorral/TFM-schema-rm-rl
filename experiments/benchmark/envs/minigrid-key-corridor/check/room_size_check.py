"""Check KeyCorridor labelings on every room size against the reference labeler and MiniGrid's rooms.

For each room size and 300 layouts (reset seeds 0 to 299), two episodes per layout:
  random  random actions (forward-biased, with pickup, drop and toggle) until the episode ends
  unlock  the card plan's first two steps (pick up the key, open the locked door), then random
          actions until the episode ends or 300 steps pass
Each step, every labeling runs through the runtime sandbox (`RewardMachineRuntime.evaluate_labeling`)
and each proposition it defines is compared with the reference labeler. `target_room_entered` is also
compared with MiniGrid's own room test: the latched `Room.pos_inside` of the ball's room (its wall
ring, so the doorway too). The reference labeler gets the same room test.

Per size, labeling and proposition it prints the episodes that differ, the episodes where the
reference turns the proposition true (so a zero means something), and for `target_room_entered` the
episodes where the labeling turns true outside the room before the locked door opened.

usage (repository root):
  PYTHONPATH=app python experiments/benchmark/envs/minigrid-key-corridor/check/room_size_check.py \
      [BUNDLE ...] [--sizes 4 5 6]
A BUNDLE is a bundle folder (its `labeling.py` and `reward_machine.txt`); with none, only the
reference labeler is checked.
"""

import argparse
import random
from collections import Counter
from pathlib import Path

from src.arm_fm.artifacts import ArtifactBundle
from src.arm_fm.environments import make_environment
from src.arm_fm.runtime import RewardMachineRuntime, load_labeling_functions
from src.benchmark.plans import run_plan
from src.benchmark.reference_labels import labeler_for

SEEDS = range(300)
ACTIONS = [0, 1, 2, 2, 2, 2, 3, 4, 5]  # left, right, forward x4, pickup, drop, toggle
UNLOCK = [{"do": "pickup", "obj": "key"}, {"do": "toggle", "obj": "door:locked"}]
UNLOCK_TAIL = 300
ROOM = "target_room_entered"


def episode_actions(gym_id: str, kind: str, seed: int, limit: int) -> list[int]:
    """The actions of one episode; random ones past the episode end are cut by the caller."""
    rng = random.Random(seed)
    if kind == "random":
        return [rng.choice(ACTIONS) for _ in range(limit)]
    prefix = run_plan({"gym_id": gym_id}, UNLOCK, seed).actions
    return [*prefix, *(rng.choice(ACTIONS) for _ in range(UNLOCK_TAIL))]


def check_episode(gym_id: str, actions: list[int], seed: int, labelings: dict) -> dict:
    """Replay ``actions``; per labeling, the propositions that ever differ and the early room entries."""
    env = make_environment(gym_id)
    env.reset(seed=seed)
    u = env.unwrapped
    reference = labeler_for(gym_id, env)
    target_room = u.room_from_pos(*u.obj.init_pos)
    runtimes = {name: RewardMachineRuntime(machine) for name, (machine, _) in labelings.items()}
    differ = {name: set() for name in ["reference", *labelings]}
    early = set()
    fired: set[str] = set()
    errors: dict[str, str] = {}
    in_room = door_opened = False
    for action in actions:
        _, _, terminated, truncated, _ = env.step(action)
        expected = reference.labels(u)
        in_room = in_room or target_room.pos_inside(*u.agent_pos)
        fired |= {name for name, value in expected.items() if value}
        if expected[ROOM] != in_room:
            differ["reference"].add(ROOM)
        for name, (_, functions) in labelings.items():
            if name in errors:
                continue
            try:
                actual = runtimes[name].evaluate_labeling(env, functions)
            except Exception as error:  # a labeling that crashes is a result
                errors[name] = f"{type(error).__name__}: {error}"
                continue
            differ[name] |= {prop for prop, value in actual.items() if value != expected[prop]}
            if ROOM in actual and actual[ROOM] != in_room:
                differ[name].add(ROOM)
                if actual[ROOM] and not in_room and not door_opened:
                    early.add(name)
        door_opened = door_opened or expected["target_door_open"]
        if terminated or truncated:
            break
    env.close()
    return {"differ": differ, "early": early, "fired": fired, "errors": errors}


def load(folder: Path) -> tuple:
    bundle = ArtifactBundle.load(folder)
    functions = load_labeling_functions(bundle.labeling_source, bundle.labeling_propositions)
    return bundle.reward_machine, functions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bundles", nargs="*", type=Path)
    parser.add_argument("--sizes", nargs="+", type=int, default=[4, 5, 6])
    args = parser.parse_args()
    labelings = {str(folder): load(folder) for folder in args.bundles}
    for size in args.sizes:
        gym_id = f"MiniGrid-KeyCorridorS{size}R3-v0"
        limit = 30 * size**2
        for kind in ("random", "unlock"):
            differ, early, fired, errors = Counter(), Counter(), Counter(), Counter()
            first_error: dict[str, str] = {}
            for seed in SEEDS:
                actions = episode_actions(gym_id, kind, seed, limit)
                result = check_episode(gym_id, actions, seed, labelings)
                fired.update(result["fired"])
                early.update(result["early"])
                errors.update(result["errors"].keys())
                first_error = {**result["errors"], **first_error}
                for name, props in result["differ"].items():
                    differ.update((name, prop) for prop in props)
            print(f"== {gym_id}, {kind}: {len(SEEDS)} episodes; reference fires {dict(fired)}")
            print(f"   reference {ROOM} vs MiniGrid's room: {differ['reference', ROOM]} differ")
            for name, (_, functions) in labelings.items():
                counts = {prop: differ[name, prop] for prop in functions}
                print(
                    f"   {name}: differ {counts}; {ROOM} true outside before the door opened "
                    f"{early[name]}; crashed {errors[name]} {first_error.get(name, '')}"
                )


if __name__ == "__main__":
    main()
