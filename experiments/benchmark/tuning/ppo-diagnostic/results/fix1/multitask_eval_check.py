"""Scratch check for fix round 1: sampled evaluation must not move later greedy evaluations.

Production MultiTaskEnvironment, two one-step tasks (one always succeeds, one always fails),
run seed 1, ten episodes per pass, an agent that always picks action 0.
Run from the repo root: PYTHONPATH=app python experiments/benchmark/tuning/ppo-diagnostic/results/fix1/multitask_eval_check.py
"""

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from src.arm_fm.environments import MultiTaskEnvironment, RunEnvironment, terminated_with_reward
from src.arm_fm.ppo import evaluate, evaluate_with_sampled
from src.config import Configuration


class OneStep(gym.Env):
    """One step, then terminated with a fixed reward."""

    observation_space = spaces.Box(0, 1, (1,), dtype=np.float32)
    action_space = spaces.Discrete(2)

    def __init__(self, reward: float) -> None:
        self.reward = reward

    def reset(self, *, seed=None, options=None):  # noqa: ARG002
        super().reset(seed=seed)
        return np.zeros(1, dtype=np.float32), {}

    def step(self, action):  # noqa: ARG002
        return np.zeros(1, dtype=np.float32), self.reward, True, False, {}


class ActionZero:
    def act(self, observation, generator=None, deterministic=False):  # noqa: ARG002
        return 0


def make_run() -> RunEnvironment:
    runs = {
        name: RunEnvironment(OneStep(reward), lambda: None, terminated_with_reward)
        for name, reward in (("wins", 1.0), ("loses", 0.0))
    }
    env = MultiTaskEnvironment(runs, 1)
    return RunEnvironment(env, lambda: None, env.is_success)


CONFIG = Configuration()
CONFIG.seed = 1
CONFIG.eval_greedy = True
CONFIG.layout = "procedural"  # the default is fixed, where greedy resets name their tasks
PASSES = 3
EPISODES = 10

run = make_run()
greedy_only = [evaluate(CONFIG, run, ActionZero(), EPISODES)["exit_rate"] for _ in range(PASSES)]
run = make_run()
with_sampled = []
for _ in range(PASSES):
    row = evaluate_with_sampled(CONFIG, run, ActionZero(), EPISODES)
    with_sampled.append(row["exit_rate"])
print("greedy-only passes:       ", greedy_only)
print("greedy+sampled, greedy:   ", with_sampled)
print("same:", greedy_only == with_sampled)
