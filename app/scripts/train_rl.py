"""Train one DQN or PPO run, with or without a Reward Machine, from a YAML run config.

Usage:
    python app/main.py train-rl --config minigrid-unlock-pickup/smoke-rm-symbolic.yaml --seed 1

The config's ``algorithm`` (``dqn`` by default, or ``ppo``) picks the learner.
"""

from src.arm_fm import train_dqn, train_ppo
from src.config import Configuration


def train_rl(CONFIG: Configuration) -> None:
    """Train the run described by ``CONFIG.yaml_config_name`` and write its run folder."""
    if not CONFIG.yaml_config_name:
        raise ValueError("train-rl requires --config")
    if CONFIG.algorithm == "ppo":
        train_ppo(CONFIG)
    else:
        train_dqn(CONFIG)
