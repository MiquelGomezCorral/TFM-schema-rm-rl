"""Print the order in which a bundle's Reward Machine pays the ways an episode can end.

No model call and nothing written. The walk is ``src.arm_fm.pay_order``.
"""

from collections.abc import Sequence
from pathlib import Path

from src.arm_fm import configured_step_limit, load_bundle
from src.arm_fm.pay_order import pay_order_of
from src.config import Configuration


def check_pay_order(
    CONFIG: Configuration,
    bundles: Sequence[Path],
    gamma: float | None = None,
    soft_breaks_per_step: int | None = None,
) -> list[str]:
    """One line per bundle: its folder, the endings from best to worst pay, ok or the broken pair.

    ``gamma``, the step limit and the soft breaks per step that streams of soft breaks run over
    come from the arguments; else the bundle's manifest records them (a bundle made with the hard
    ceiling does), else gamma and the soft breaks per step are the defaults. With no step limit
    from either, the line says ``not checked: no step limit``: a one-step horizon is not the
    run's, so it gets no verdict. ``gamma`` and ``soft_breaks_per_step`` are None when omitted
    (``CONFIG`` cannot say
    "omitted"). The step limit is ``CONFIG.step_limit``, else the one of the level
    ``CONFIG.gym_id`` and ``CONFIG.env_kwargs`` make (a bundle stores no level, so the caller
    names it).
    """
    step_limit = configured_step_limit(CONFIG)
    lines = []
    for folder in bundles:
        bundle = load_bundle(folder)
        if bundle.reward_machine is None:
            lines.append(f"{folder}: no Reward Machine")
            continue
        recorded = bundle.manifest.effective_settings
        discount = gamma if gamma is not None else recorded.get("gamma", Configuration.gamma)
        limit = step_limit if step_limit is not None else recorded.get("step_limit")
        breaks = (
            soft_breaks_per_step
            if soft_breaks_per_step is not None
            else recorded.get("soft_breaks_per_step", Configuration.soft_breaks_per_step)
        )
        if limit is None:
            lines.append(
                f"{folder}: not checked: no step limit (name it with --gym-id or --step-limit)"
            )
            continue
        order = pay_order_of(bundle, discount, limit, breaks)
        lines.append(
            f"{folder}: {order.summary()} "
            f"(gamma {discount}, step limit {limit}, soft breaks per step {breaks})"
        )
    return lines
