"""Train the native domain policy from one bundle or a task manifest."""

from dataclasses import replace

from src.arm_fm import (
    load_bundle,
    load_task_manifest,
    make_environment,
    paper_training_config,
    train_larm,
    train_manifest,
)
from src.config import Configuration


def train_larm_command(CONFIG: Configuration) -> None:
    """Train the native domain policy from one bundle or a task manifest."""
    if CONFIG.domain is None or CONFIG.checkpoint is None:
        raise ValueError("train-larm requires --domain and --checkpoint")

    training_config = paper_training_config(
        CONFIG.domain, seed=CONFIG.seed, rnd=_explicit_rnd_variant(CONFIG.domain)
    )
    overrides = {}
    if CONFIG.algorithm is not None:
        overrides["algorithm"] = CONFIG.algorithm
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
        bundle = load_bundle(CONFIG.bundle)
        environment = (
            [make_environment(CONFIG.domain) for _ in range(4)]
            if training_config.algorithm == "ppo"
            else make_environment(CONFIG.domain)
        )
        train_larm(
            bundle, environment, None, training_config,
            checkpoint_path=CONFIG.checkpoint,
        )
    else:
        raise ValueError("train-larm requires exactly one of --bundle or --task-manifest")


def _explicit_rnd_variant(domain: str) -> bool:
    value = domain.lower().replace("_", "-")
    return any(part == "rnd" for part in value.split("-"))
