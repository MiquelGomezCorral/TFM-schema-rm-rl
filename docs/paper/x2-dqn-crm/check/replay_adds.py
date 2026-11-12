"""Replay-buffer adds per environment step, with and without counterfactual experience.

Run from the worktree root:  PYTHONPATH=app python <this file> <run-config.yaml> [<run-config.yaml> ...]
Each config is a finished run's own run-config.yaml (one per task). For every config the script drives
8 environments with random actions through the real step_transitions + store_transitions path, past one
time-limit cut, and prints stored transitions / env steps for counterfactual off and on.
"""

import sys

import torch

from src.arm_fm import make_run_environment
from src.arm_fm.dqn import create_replay_buffer, step_transitions, store_transitions
from src.config import Configuration

ENVS = 8
VECTOR_STEPS = (
    700  # DoorKey-8x8 and UnlockPickup time limits are below 700 steps for the base cards
)


def adds_per_env_step(config_file: str, counterfactual: bool) -> tuple[float, int]:
    CONFIG = Configuration(yaml_config_name=config_file, seed=1)
    CONFIG.dqn_num_envs = ENVS
    CONFIG.counterfactual = counterfactual
    CONFIG.total_timesteps = (
        ENVS * VECTOR_STEPS * 20
    )  # the replay holds min(buffer_size, total_timesteps)
    CONFIG.buffer_size = ENVS * VECTOR_STEPS * 20  # big enough that nothing wraps
    runs = [make_run_environment(CONFIG) for _ in range(ENVS)]
    envs = [run.env for run in runs]
    buffer = create_replay_buffer(CONFIG, envs[0], torch.device("cpu"))
    observations = [env.reset(seed=1 + index)[0] for index, env in enumerate(envs)]
    episodes_ended = 0
    for _ in range(VECTOR_STEPS):
        actions = [env.action_space.sample() for env in envs]
        steps = [env.step(action) for env, action in zip(envs, actions, strict=True)]
        transitions = [
            step_transitions(CONFIG, env, observation, step)
            for env, observation, step in zip(envs, observations, steps, strict=True)
        ]
        store_transitions(buffer, actions, transitions)
        observations = [step[0] for step in steps]
        for index, step in enumerate(steps):
            if step[2] or step[3]:
                episodes_ended += 1
                observations[index] = envs[index].reset()[0]
    stored = buffer.pos * ENVS
    return stored / (ENVS * VECTOR_STEPS), episodes_ended


def main(config_files: list[str]) -> None:
    for config_file in config_files:
        for counterfactual in (False, True):
            ratio, ended = adds_per_env_step(config_file, counterfactual)
            print(
                f"{config_file.split('/')[-2]}: counterfactual={counterfactual} "
                f"adds per env step {ratio:.3f} ({ENVS} envs x {VECTOR_STEPS} steps, {ended} episodes ended)"
            )


if __name__ == "__main__":
    main(sys.argv[1:])
