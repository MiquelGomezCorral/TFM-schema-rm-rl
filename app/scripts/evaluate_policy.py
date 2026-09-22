"""Evaluate a frozen built-in ARM-FM policy."""

import json

from src.arm_fm import (
    RewardMachineEnvironment,
    RewardMachineRuntime,
    TrainingCheckpoint,
    frozen_evaluate,
    load_builtin_policy,
    load_bundle,
    make_environment,
)
from src.config import Configuration


def evaluate_policy_command(CONFIG: Configuration, *, runner=None) -> None:
    """Load a built-in checkpoint and evaluate it without updating learning state."""
    if CONFIG.bundle is None or CONFIG.checkpoint is None or CONFIG.domain is None:
        raise ValueError("evaluate-policy requires --bundle and --checkpoint")

    bundle = load_bundle(CONFIG.bundle)
    environment = make_environment(CONFIG.domain)
    checkpoint = TrainingCheckpoint.load(CONFIG.checkpoint)
    policy = load_builtin_policy(checkpoint, environment, bundle)
    runner = runner or (lambda policy, current_bundle: _run_frozen_episode(
        policy, current_bundle, environment
    ))

    results = frozen_evaluate(policy, [bundle], runner=runner)
    print(json.dumps(results, indent=2, sort_keys=True))


def _run_frozen_episode(policy, bundle, environment=None):
    """Run one evaluation episode through the shared RM environment wrapper."""
    if environment is None:
        raise ValueError("Frozen evaluation requires an explicit runtime environment")

    wrapped = RewardMachineEnvironment(
        environment, RewardMachineRuntime(bundle.reward_machine), bundle.labeling_source,
    )
    reset = wrapped.reset()
    observation = reset[0] if isinstance(reset, tuple) else reset
    runtime = wrapped.runtime
    episode_return = 0.0
    steps = 0
    terminated = truncated = False
    final_info = {}

    for _ in range(10_000):
        action = policy.act(observation, bundle.embeddings[runtime.state], explore=False)
        result = wrapped.step(action)
        if len(result) == 5:
            observation, reward, terminated, truncated, info = result
        else:
            observation, reward, terminated, info = result
            truncated = False
        episode_return += float(reward)
        steps += 1
        final_info = _scalar_info(dict(info or {}))
        if terminated or truncated:
            break

    return {
        "episode_return": episode_return,
        "step_count": steps,
        "final_rm_state": runtime.state,
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "final_info": final_info,
    }


def _scalar_info(info: dict) -> dict[str, float]:
    values = {}
    for key, value in info.items():
        if isinstance(value, bool):
            continue
        try:
            value = value.item()
        except AttributeError:
            pass
        if isinstance(value, (int, float)):
            values[key] = float(value)
    return values
