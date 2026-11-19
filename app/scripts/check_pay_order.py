"""Print the order in which a bundle's Reward Machine pays the ways an episode can end.

No model call and nothing written. The walk is ``src.arm_fm.pay_order``.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.arm_fm import gym_step_limit, load_bundle
from src.arm_fm.pay_order import pay_order_of
from src.config import Configuration


def check_pay_order(
    bundles: Sequence[Path],
    gamma: float | None = None,
    step_limit: int | None = Configuration.step_limit,
    gym_id: str | None = Configuration.gym_id,
    env_kwargs: Mapping[str, Any] | None = None,
) -> list[str]:
    """One line per bundle: its folder, the endings from best to worst pay, ok or the broken pair.

    ``gamma`` and the step limit that streams of soft breaks run over come from the arguments;
    else the bundle's manifest records them (a bundle made with the hard ceiling does), else
    gamma is the default and the step limit is one step. ``gym_id`` and ``env_kwargs`` read the
    step limit from the level they make (a bundle stores no level, so the caller names it).
    """
    if step_limit is None and gym_id:
        step_limit = gym_step_limit(gym_id, **(env_kwargs or {}))
    lines = []
    for folder in bundles:
        bundle = load_bundle(folder)
        if bundle.reward_machine is None:
            lines.append(f"{folder}: no Reward Machine")
            continue
        recorded = bundle.manifest.effective_settings
        discount = gamma if gamma is not None else recorded.get("gamma", Configuration.gamma)
        limit = step_limit if step_limit is not None else recorded.get("step_limit")
        order = pay_order_of(bundle, discount, limit)
        lines.append(f"{folder}: {order.summary()} (gamma {discount}, step limit {limit})")
    return lines
