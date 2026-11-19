"""Rebuild a compiler bundle's Reward Machine rewards with the current reward layer.

No model call. Use it after a change to how the reward layer prices edges, to try a soft-break
cost, or to turn the promise cost on. The result goes to a new bundle folder; the source is never
written.
"""

from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

from src.arm_fm import load_bundle
from src.compiler import PaperRewardMachine, compile_dfas
from src.config import Configuration
from src.utils import preflight_paths, print_warning

from .ablate_rm import _build, _recorded_switches, _stored_task

REBUILD_RULE = "whole-unit pay, owed-stage charge, soft break without refund"
PROMISE_COST_RULE = "promise cost (-0.1 on every step while a hard promise is open)"


def rebuild_rewards(CONFIG: Configuration, destination: Path) -> bool:
    """Write ``destination``: ``CONFIG.bundle`` with today's rewards for its stored clauses.

    The machine is rebuilt from the clauses and the reward switches the bundle records (clause,
    LTLf, MONA, reward layer); ``CONFIG.reward_promise_cost`` turns the promise cost on, and
    ``CONFIG.soft_break_cost`` always sets the soft-break cost. Only the rewards (and the numbers
    of the end judgment) may differ from the stored machine: the states, guards that move, and
    the states the end judgment covers must match, so the labeling, state descriptions and
    embeddings stay valid and are copied as they are. In the copy only ``reward_machine.txt`` and
    the manifest change: the attempts and raw responses keep what the model wrote, and the critic
    verdict stays as given at generation time, with a ``rewards_rebuilt`` note in the manifest.

    Returns:
        True when the bundle was written, False after a one-line message on stderr (nothing is
        written).
    """
    bundle = load_bundle(CONFIG.bundle)
    if bundle.reward_machine is None or not bundle.manifest.generation.get("clauses"):
        print_warning(f"rebuild-rewards: {CONFIG.bundle} has no machine or stores no clauses")
        return False
    if destination.resolve() == CONFIG.bundle.resolve():
        print_warning(f"rebuild-rewards: --output is the source bundle {CONFIG.bundle}")
        return False
    try:
        preflight_paths([destination], overwrite=CONFIG.overwrite, kind="Bundle folder")
    except ValueError as error:
        print_warning(f"rebuild-rewards: {error}")
        return False

    environment, proposal = _stored_task(CONFIG, bundle)
    dfas = compile_dfas(proposal, CONFIG)
    recorded = _recorded_switches(bundle)
    switches = replace(
        recorded,
        reward_promise_cost=recorded.reward_promise_cost or CONFIG.reward_promise_cost,
        soft_break_cost=CONFIG.soft_break_cost,
    )
    result, machine = _build(environment, proposal, dfas, switches)

    if _frame(machine) != _frame(bundle.reward_machine):
        print_warning(
            f"rebuild-rewards: {CONFIG.bundle}: the rebuild changes more than the rewards "
            "(states, guards or end judgment); regenerate the bundle instead"
        )
        return False

    bundle.reward_machine = machine
    bundle.manifest.generation["compiler_text"] = result.text
    bundle.manifest.generation["rewards_rebuilt"] = {
        "date": date.today().isoformat(),
        "rule": PROMISE_COST_RULE if switches.reward_promise_cost else REBUILD_RULE,
        "note": "the critic verdict was given on the rewards before this rebuild",
    }
    bundle.manifest.effective_settings.update(asdict(switches))
    bundle.save(destination, overwrite=CONFIG.overwrite)
    print(f"rebuild-rewards: {destination}: rewards rebuilt from {CONFIG.bundle}")
    return True


def _frame(machine: PaperRewardMachine) -> tuple:
    """What a reward rebuild keeps: states, finals, end judgment and every transition that moves.

    A loop that stays put is left out: the promise cost makes the idle loops of a state with a
    promise open into priced transitions, and a loop with no reward is the same as none. The end
    judgment is kept as the states it covers: its counts and failed rewards are pay.
    """
    moves = {
        (item.source, item.condition, item.destination)
        for item in machine.transitions
        if item.source != item.destination
    }
    judgment = machine.judgment
    judged = (
        None
        if judgment is None
        else (judgment.accepting, tuple(state for state, _, _ in judgment.pending))
    )
    return (
        machine.states,
        machine.initial_state,
        machine.final_states,
        machine.rejecting_states,
        judged,
        moves,
    )
