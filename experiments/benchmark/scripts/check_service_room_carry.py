"""Live check of the service room's carrying start (``carry=True``).

Usage (from the repository root):
    PYTHONPATH=app python experiments/benchmark/scripts/check_service_room_carry.py [--seeds 50]

For reset seeds 1..N, on the box-only and the siren-and-box setups, it checks that the agent
starts holding the box with none on the floor, that a do-nothing agent meets the first fall at the
step the schedule drew (2 to 8), that the scripted policy still exits with reward above 0, that
the same seed replays the same fall, that an agent trying to drop the box on every step still holds
it until the fall, that a pickup on the very next step works after every fall (also when the agent
faces the wall at the fall), and that ``carry`` leaves every other draw of the schedule as it is
without it. Prints one line per check and exits non-zero when one fails.
"""

import argparse
import sys

from minigrid.core.actions import Actions

from src.arm_fm.environments import make_environment
from src.arm_fm.service_room import (
    CARRY_FALL_FIRST,
    CARRY_FALL_LAST,
    ENV_ID,
    cells_of_type,
    scripted_policy,
)

SETUPS = {
    "box": {"siren": False, "box": True, "carry": True, "require": ["holding_box"]},
    "both": {
        "siren": True,
        "box": True,
        "carry": True,
        "require": ["siren_silent", "holding_box"],
    },
}
WAIT_STEPS = 12  # more than the last first fall


def do_nothing_fall_step(kwargs: dict, seed: int) -> tuple[bool, int | None]:
    """Whether the agent starts holding the box, and the step of the first fall of an idle run."""
    env = make_environment(ENV_ID, **kwargs)
    env.reset(seed=seed)
    base = env.unwrapped
    holding = base.carrying is not None and not cells_of_type(base, "box")
    for _ in range(WAIT_STEPS):
        _, _, _, _, info = env.step(int(Actions.done))
        if "fall" in info["events"]:
            return holding, base.step_count
    return holding, None


def drops_until_fall(kwargs: dict, seed: int) -> bool:
    """An agent that plays ``drop`` on every step holds the box until the first fall."""
    env = make_environment(ENV_ID, **kwargs)
    env.reset(seed=seed)
    base = env.unwrapped
    for _ in range(WAIT_STEPS):
        held = base.carrying is not None
        _, _, _, _, info = env.step(int(Actions.drop))
        if "fall" in info["events"]:
            return held
    return False


def pickups_after_falls(kwargs: dict, seed: int, face_wall: bool) -> tuple[int, int]:
    """Falls met by an idle agent that picks up on the step after each, and the pickups that worked.

    ``face_wall`` first turns the agent to the wall above its start cell.
    """
    env = make_environment(ENV_ID, **kwargs)
    env.reset(seed=seed)
    base = env.unwrapped
    if face_wall:
        env.step(int(Actions.left))
    falls = worked = 0
    fell = False
    for _ in range(WAIT_STEPS * 4):
        _, _, _, _, info = env.step(int(Actions.pickup if fell else Actions.done))
        worked += fell and base.carrying is not None
        fell = "fall" in info["events"]
        falls += fell
    return falls, worked


def scripted_reward(kwargs: dict, seed: int) -> float:
    env = make_environment(ENV_ID, **kwargs)
    env.reset(seed=seed)
    done, reward = False, 0.0
    while not done:
        _, reward, terminated, truncated, _ = env.step(scripted_policy(env))
        done = terminated or truncated
    return reward


def schedule(kwargs: dict, seed: int) -> tuple[list[int], list[int]]:
    env = make_environment(ENV_ID, **kwargs)
    env.reset(seed=seed)
    return env.unwrapped._ring_steps, env.unwrapped._fall_delays


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=50)
    seeds = range(1, parser.parse_args().seeds + 1)
    failed = False

    def report(name: str, passed: int, total: int) -> None:
        nonlocal failed
        failed |= passed != total
        print(f"{'ok  ' if passed == total else 'FAIL'} {name}: {passed}/{total}")

    for setup, kwargs in SETUPS.items():
        idle = [do_nothing_fall_step(kwargs, seed) for seed in seeds]
        report(
            f"{setup}: starts holding the box, none on the floor",
            sum(h for h, _ in idle),
            len(idle),
        )
        in_range = sum(f is not None and CARRY_FALL_FIRST <= f <= CARRY_FALL_LAST for _, f in idle)
        report(
            f"{setup}: do-nothing run falls at step {CARRY_FALL_FIRST}-{CARRY_FALL_LAST}",
            in_range,
            len(idle),
        )
        report(
            f"{setup}: same seed, same fall",
            sum(idle[i] == do_nothing_fall_step(kwargs, s) for i, s in enumerate(seeds)),
            len(idle),
        )
        report(
            f"{setup}: dropping on every step still holds the box until the fall",
            sum(drops_until_fall(kwargs, s) for s in seeds),
            len(idle),
        )
        for face_wall in (False, True):
            results = [pickups_after_falls(kwargs, s, face_wall) for s in seeds]
            report(
                f"{setup}: pickup on the step after each fall works"
                + (", facing the wall" if face_wall else ""),
                sum(falls > 0 and falls == worked for falls, worked in results),
                len(idle),
            )
        report(
            f"{setup}: scripted policy exits with reward",
            sum(scripted_reward(kwargs, s) > 0 for s in seeds),
            len(idle),
        )

        plain = {**kwargs, "carry": False}
        same = 0
        for seed in seeds:
            (rings, delays), (plain_rings, plain_delays) = (
                schedule(kwargs, seed),
                schedule(plain, seed),
            )
            same += rings == plain_rings and delays[1:] == plain_delays[1:]
        report(f"{setup}: rings and second fall as without carry", same, len(idle))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
