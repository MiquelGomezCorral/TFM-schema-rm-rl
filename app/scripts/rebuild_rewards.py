"""Rebuild a compiler bundle's Reward Machine rewards with the current reward layer.

No model call. Use it after a change to how the reward layer prices edges, or to turn the promise
cost on (to keep the original, copy the bundle folder first).
"""

from dataclasses import replace
from datetime import date

from src.arm_fm import load_bundle
from src.compiler import PaperRewardMachine, compile_dfas, serialize_paper_reward_machine
from src.config import Configuration
from src.utils import print_warning

from .ablate_rm import _build, _recorded_switches, _stored_task

REBUILD_RULE = "chain-weighted progress (C1-sum)"
PROMISE_COST_RULE = "promise cost (-0.01 on every step while a hard promise is open)"


def rebuild_rewards(CONFIG: Configuration) -> bool:
    """Rewrite ``CONFIG.bundle`` in place with today's rewards for its stored clauses.

    The machine is rebuilt from the clauses and the reward switches the bundle records (clause,
    LTLf, MONA, reward layer); ``CONFIG.reward_promise_cost`` turns the promise cost on. Only the
    rewards may differ from the stored machine: the states, guards that move, and the end
    judgment must match, so the labeling, state descriptions and embeddings stay valid and are not
    touched. Only ``reward_machine.txt`` and the manifest change: the attempts and raw responses
    keep what the model wrote, and the critic verdict stays as given at generation time, with a
    ``rewards_rebuilt`` note in the manifest.

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
    recorded = _recorded_switches(bundle)
    switches = replace(
        recorded, reward_promise_cost=recorded.reward_promise_cost or CONFIG.reward_promise_cost
    )
    result, machine = _build(environment, proposal, dfas, switches)
    old_text = (CONFIG.bundle / "reward_machine.txt").read_text(encoding="utf-8")
    new_text = serialize_paper_reward_machine(machine)

    if _frame(machine) != _frame(bundle.reward_machine):
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
        "rule": PROMISE_COST_RULE if switches.reward_promise_cost else REBUILD_RULE,
        "note": "the critic verdict was given on the rewards before this rebuild",
    }
    if switches.reward_promise_cost:
        bundle.manifest.effective_settings["reward_promise_cost"] = True
    bundle.save(CONFIG.bundle, overwrite=True)
    print(f"rebuild-rewards: {CONFIG.bundle}: rewards rebuilt")
    return True


def _frame(machine: PaperRewardMachine) -> tuple:
    """What a reward rebuild keeps: states, finals, end judgment and every transition that moves.

    A loop that stays put is left out: the promise cost makes the idle loops of a state with a
    promise open into priced transitions, and a loop with no reward is the same as none.
    """
    moves = {
        (item.source, item.condition, item.destination)
        for item in machine.transitions
        if item.source != item.destination
    }
    return (
        machine.states,
        machine.initial_state,
        machine.final_states,
        machine.rejecting_states,
        machine.judgment,
        moves,
    )
