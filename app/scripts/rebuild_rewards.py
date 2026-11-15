"""Rebuild a compiler bundle's Reward Machine rewards with the current reward layer.

No model call. Use it after a change to how the reward layer prices edges.
"""

from datetime import date

from src.arm_fm import load_bundle
from src.compiler import compile_dfas, serialize_paper_reward_machine
from src.config import Configuration
from src.utils import print_warning

from .ablate_rm import _build, _recorded_switches, _stored_task

REBUILD_RULE = "chain-weighted progress (C1-sum)"


def rebuild_rewards(CONFIG: Configuration) -> bool:
    """Rewrite ``CONFIG.bundle`` in place with today's rewards for its stored clauses.

    The machine is rebuilt from the clauses and the reward switches the bundle records (clause,
    LTLf, MONA, reward layer). Only the ``REWARD_FUNCTION`` lines may differ from the stored
    ``reward_machine.txt``: states, guards and the end judgment must match, so the labeling, state
    descriptions and embeddings stay valid and are not touched. Only ``reward_machine.txt`` and the
    manifest change: the attempts and raw responses keep what the model wrote, and the critic
    verdict stays as given at generation time, with a ``rewards_rebuilt`` note in the manifest.

    Returns:
        True when the bundle is current or was rewritten, False after a one-line message on
        stderr (nothing is written).
    """
    bundle = load_bundle(CONFIG.bundle)
    if bundle.reward_machine is None or not bundle.manifest.generation.get("clauses"):
        print_warning(f"rebuild-rewards: {CONFIG.bundle} has no machine or stores no clauses")
        return False

    environment, proposal = _stored_task(CONFIG, bundle)
    dfas = compile_dfas(proposal, CONFIG)
    result, machine = _build(environment, proposal, dfas, _recorded_switches(bundle))
    old_text = (CONFIG.bundle / "reward_machine.txt").read_text(encoding="utf-8")
    new_text = serialize_paper_reward_machine(machine)

    if _without_rewards(new_text) != _without_rewards(old_text):
        print_warning(
            f"rebuild-rewards: {CONFIG.bundle}: the rebuild changes more than the rewards "
            "(states, guards or end judgment); regenerate the bundle instead"
        )
        return False
    if new_text == old_text:
        print(f"rebuild-rewards: {CONFIG.bundle}: already current")
        return True

    bundle.reward_machine = machine
    bundle.manifest.generation["compiler_text"] = result.text
    bundle.manifest.generation["rewards_rebuilt"] = {
        "date": date.today().isoformat(),
        "rule": REBUILD_RULE,
        "note": "the critic verdict was given on the rewards before this rebuild",
    }
    bundle.save(CONFIG.bundle, overwrite=True)
    print(f"rebuild-rewards: {CONFIG.bundle}: rewards rebuilt")
    return True


def _without_rewards(text: str) -> tuple[str, str]:
    """The machine text before and after its ``REWARD_FUNCTION`` lines."""
    before, _, after = text.partition("REWARD_FUNCTION:\n")
    return before, after.partition("PENDING_PROMISES:")[2]
