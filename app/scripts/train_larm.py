"""Train the native policy from one bundle or a task manifest."""

from dataclasses import replace

from src.arm_fm import (
    load_bundle,
    load_task_manifest,
    make_environment,
    paper_training_config,
    train_manifest,
)
from src.arm_fm import train_larm as train_bundle
from src.config import Configuration


def train_larm(CONFIG: Configuration) -> None:
    """Train the native policy from one bundle or a task manifest."""
    if CONFIG.checkpoint is None:
        raise ValueError("train-larm requires --checkpoint")

    training_config = paper_training_config(CONFIG.algorithm, seed=CONFIG.seed, rnd=CONFIG.rnd)
    overrides = {}
    if CONFIG.total_timesteps is not None:
        overrides["total_timesteps"] = CONFIG.total_timesteps
    if CONFIG.learning_rate is not None:
        overrides["learning_rate"] = CONFIG.learning_rate
    training_config = replace(training_config, **overrides)

    if CONFIG.task_manifest is not None:
        entries = load_task_manifest(CONFIG.task_manifest)
        environments = {entry.task_id: make_environment(entry.environment_id) for entry in entries}
        train_manifest(entries, environments, training_config, checkpoint_path=CONFIG.checkpoint)
    elif CONFIG.bundle is not None:
        if CONFIG.domain is None:
            raise ValueError("train-larm --bundle requires --domain")
        bundle = load_bundle(CONFIG.bundle)
        # PPO collects from four independent lanes; the other algorithms use one.
        lanes = 4 if training_config.algorithm == "ppo" else 1
        environments = [make_environment(CONFIG.domain) for _ in range(lanes)]
        train_bundle(
            bundle,
            environments if lanes > 1 else environments[0],
            training_config,
            checkpoint_path=CONFIG.checkpoint,
        )
    else:
        raise ValueError("train-larm requires exactly one of --bundle or --task-manifest")
