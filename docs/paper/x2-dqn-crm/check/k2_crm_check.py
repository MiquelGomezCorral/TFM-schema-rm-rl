"""K2: counterfactual (CRM) transitions on scripted DoorKey episodes with the pilot FARM machine.

Run from the worktree root:  PYTHONPATH=app python <this file>
Checks, on every scripted step:
  1. the counterfactual tuple of the real source state equals the real transition that is stored;
  2. a step adds one transition per non-final, non-rejecting state (u0, u1, u3 of this machine);
  3. the buffer row count grows by exactly that number.
Episodes: a success path (key, door, goal), a time-limit cut in u1 (end charge), and a rejecting step.
"""

from pathlib import Path
from typing import NamedTuple

import numpy as np
import torch
from minigrid.core.world_object import Key

from src.arm_fm import make_run_environment
from src.arm_fm.dqn import create_replay_buffer, step_transitions, store_transitions
from src.config import Configuration

CONFIG_FILE = str(Path(__file__).with_name("k1-defaults.yaml"))  # copied beside this script
SOURCES = ("u0", "u1", "u3")  # the machine's non-final, non-rejecting states


def same(left, right) -> bool:
    obs_equal = all(np.array_equal(left[i][key], right[i][key]) for i in (0, 1) for key in left[i])
    return obs_equal and left[2] == right[2] and left[3] == right[3]


def state_of(embeddings, observation) -> str:
    return next(s for s, v in embeddings.items() if np.array_equal(v, observation["rm_embedding"]))


class Setup(NamedTuple):
    """What every scripted step shares: the configuration, the run, the replay buffer and the action."""

    config: Configuration
    run: object
    buffer: object
    action: int


def check_step(label, setup, observation, step_fn):
    env = setup.run.env
    buffer = setup.buffer
    step = step_fn()
    info = step[4]
    real = info["rm_source"]
    rows = step_transitions(setup.config, env, observation, step)
    again = env.counterfactual_transition(real, observation, step)
    assert same(rows[0], again), (
        f"{label}: counterfactual of {real} differs from the real transition"
    )
    before = buffer.pos if not buffer.full else None
    store_transitions(buffer, [setup.action], [rows])
    added = buffer.pos - before
    assert len(rows) == len(SOURCES) and added == len(SOURCES), (
        f"{label}: {len(rows)} rows, {added} added"
    )
    print(
        f"{label}: real source {real} -> {info['rm_state']}, reward {step[1]}, terminated {step[2]},"
        f" truncated {step[3]}; transitions added {added}"
    )
    embeddings = env.embeddings
    sources = [real] + [s for s in SOURCES if s != real]
    for source, row in zip(sources, rows, strict=True):
        origin, target = state_of(embeddings, row[0]), state_of(embeddings, row[1])
        tag = "real" if source == real else "counterfactual"
        print(f"    {tag:15s} {origin} -> {target}  reward {row[2]:+.2f}  terminated {row[3]}")
        assert origin == source
    return step


def main() -> None:
    CONFIG = Configuration(yaml_config_name=CONFIG_FILE, seed=1)
    CONFIG.counterfactual = True
    run = make_run_environment(CONFIG)
    env, grid_env = run.env, run.env.unwrapped
    buffer = create_replay_buffer(CONFIG, env, torch.device("cpu"))
    done = int(grid_env.actions.done)
    setup = Setup(CONFIG, run, buffer, done)

    def first(kind):
        return next(c for c in grid_env.grid.grid if c is not None and c.type == kind)

    print("== success path: key, door, goal ==")
    observation, _ = env.reset(seed=1)
    door, goal = first("door"), first("goal")
    time_limit = grid_env.max_steps
    grid_env.carrying = Key(door.color)
    step = check_step("key", setup, observation, lambda: env.step(done))
    observation = step[0]
    door.is_locked, door.is_open = False, True
    step = check_step("door", setup, observation, lambda: env.step(done))
    observation = step[0]
    grid_env.agent_pos = goal.cur_pos
    check_step("goal", setup, observation, lambda: env.step(done))

    print("== time limit in u1: the end charge applies to every source state ==")
    observation, _ = env.reset(seed=1)
    grid_env.carrying = Key(first("door").color)
    grid_env.max_steps = grid_env.step_count + 1
    check_step("limit", setup, observation, lambda: env.step(done))

    print("== door open without the key: u0 enters the rejecting state u2 ==")
    grid_env.max_steps = time_limit
    observation, _ = env.reset(seed=1)
    door = first("door")
    door.is_locked, door.is_open = False, True
    check_step("reject", setup, observation, lambda: env.step(done))
    print(f"K2 ok: 5 scripted steps, {buffer.pos} buffer rows = 5 x {len(SOURCES)}")


if __name__ == "__main__":
    main()
