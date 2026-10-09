"""Train one DQN run, with or without a Reward Machine, from a YAML run config.

Usage:
    python app/main.py train-rl --config minigrid-unlock-pickup/smoke-rm-symbolic.yaml --seed 1
"""

from src.arm_fm import train_dqn
from src.config import Configuration


def train_rl(CONFIG: Configuration) -> None:
    """Train the run described by ``CONFIG.yaml_config_name`` and write its run folder."""
    if not CONFIG.yaml_config_name:
        raise ValueError("train-rl requires --config")
    train_dqn(CONFIG)
