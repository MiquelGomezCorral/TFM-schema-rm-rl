"""Rebuild a compiler bundle's Reward Machine rewards with the current reward layer.

No model call. Use it after a change to how the reward layer prices edges, to try a soft-break
cost, or to turn the promise cost on. The result goes to a new bundle folder; the source is never
written.
"""

from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

from src.arm_fm import gym_step_limit, load_bundle
from src.arm_fm.pay_order import pay_order_of
from src.compiler import PaperRewardMachine, compile_dfas
from src.config import Configuration
from src.utils import preflight_paths, print_warning

from .ablate_rm import _build, _recorded_switches, _stored_task

REBUILD_RULE = "whole-unit pay, owed-stage charge, soft break without refund"
PROMISE_COST_RULE = "promise cost (-0.1 on every step while a hard promise is open)"


def rebuild_rewards(
    CONFIG: Configuration,
    destination: Path,
    gamma: float | None = None,
    soft_breaks_per_step: int | None = None,
) -> bool:
    """Write ``destination``: ``CONFIG.bundle`` with today's rewards for its stored clauses.

    The machine is rebuilt from the clauses and the reward switches the bundle records (clause,
    LTLf, MONA, reward layer); ``CONFIG.reward_promise_cost`` turns the promise cost on,
    ``CONFIG.recurrent_soft_penalty`` False charges each soft rule once, and
    ``CONFIG.hard_ceiling`` prices the hard break above the discounted soft ceiling (see
    ``hard_break_charge``) for ``gamma`` and the level's step limit: ``CONFIG.step_limit``,
    else the limit of the level ``CONFIG.gym_id`` and ``CONFIG.env_kwargs`` make, else the
    bundle's recorded one. Only a ceiling bundle records a step limit, and only it builds the
    level. ``gamma`` None keeps the bundle's recorded discount (``CONFIG.gamma`` cannot say
    "omitted"), and so does ``soft_breaks_per_step`` None (the soft breaks per step the ceiling
    assumes; a bundle that records none has the ``Configuration`` default).
    ``CONFIG.soft_break_cost`` always sets the soft-break cost. ``fold_soft_absence`` stays as
    the bundle records it (a bundle that records none counts as on, and is refused when a soft
    Absence would now fold). The manifest records every setting. Only the rewards (and the numbers
    of the end judgment) may differ from the stored machine: the states, guards that move, and
    the states the end judgment covers must match, so the labeling, state descriptions and
    embeddings stay valid and are copied as they are, unless the soft rules are charged once:
    that moves the way out of a broken-rule state, so the copy drops them (see below). In the
    copy only ``reward_machine.txt`` and
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
    ceiling = recorded.hard_ceiling or CONFIG.hard_ceiling
    step_limit = recorded.step_limit
    if ceiling and CONFIG.step_limit is not None:
        step_limit = CONFIG.step_limit
    elif ceiling and CONFIG.gym_id:
        step_limit = gym_step_limit(CONFIG.gym_id, **CONFIG.env_kwargs)
    switches = replace(
        recorded,
        reward_promise_cost=recorded.reward_promise_cost or CONFIG.reward_promise_cost,
        recurrent_soft_penalty=recorded.recurrent_soft_penalty and CONFIG.recurrent_soft_penalty,
        soft_break_cost=CONFIG.soft_break_cost,
        soft_breaks_per_step=(
            recorded.soft_breaks_per_step if soft_breaks_per_step is None else soft_breaks_per_step
        ),
        hard_ceiling=ceiling,
        gamma=recorded.gamma if gamma is None else gamma,
        step_limit=step_limit,
    )
    if switches.hard_ceiling and switches.step_limit is None:
        print_warning(
            "rebuild-rewards: the hard ceiling needs the level's step limit; "
            "pass --gym-id or --step-limit"
        )
        return False
    result, machine = _build(environment, proposal, dfas, switches)

    # Charging each soft rule once ends the way back out of a broken-rule state, so it may change
    # where moves lead; the states, and so the labeling, stay unless the bundle folds a soft Absence
    # (the fold needs the recurrent penalty, so charging once brings the broken state back).
    moved = switches.recurrent_soft_penalty != recorded.recurrent_soft_penalty
    if _frame(machine, moves=not moved) != _frame(bundle.reward_machine, moves=not moved):
        reason = (
            "charge-once needs a bundle built with --no-fold-soft-absence"
            if moved
            else "the rebuild changes more than the rewards (states, guards or end judgment; a "
            "soft Absence bundle made before fold_soft_absence folds its broken state now); "
            "rebuild the bundle (generate it again) instead"
        )
        print_warning(f"rebuild-rewards: {CONFIG.bundle}: {reason}")
        return False

    rebuilt = {
        "date": date.today().isoformat(),
        "rule": PROMISE_COST_RULE if switches.reward_promise_cost else REBUILD_RULE,
        "note": "the critic verdict was given on the rewards before this rebuild",
    }
    if moved:
        # The descriptions and embeddings were written for the old moves; a run that reads them
        # is refused (see ``_reward_machine_inputs``), a one-hot run does not need them.
        rebuilt["dropped"] = ["state_descriptions", "embeddings"]
        rebuilt["note"] += (
            "; the soft rules are now charged once, so the broken-rule states lead nowhere: "
            "the state descriptions and embeddings, written for the old moves, are dropped "
            "and the bundle trains one-hot only"
        )
        bundle.state_descriptions, bundle.embeddings = {}, {}
        bundle.manifest.stage_status.update(descriptions="pending", embeddings="pending")
        print_warning(
            "rebuild-rewards: the soft rules are now charged once: the state descriptions and "
            "embeddings are dropped from the copy; train it with rm_state_encoding: one_hot"
        )
    bundle.reward_machine = machine
    bundle.manifest.generation["compiler_text"] = result.text
    bundle.manifest.generation["rewards_rebuilt"] = rebuilt
    bundle.manifest.effective_settings.update(asdict(switches))
    bundle.save(destination, overwrite=CONFIG.overwrite)
    print(f"rebuild-rewards: {destination}: rewards rebuilt from {CONFIG.bundle}")
    limit = switches.step_limit if switches.hard_ceiling else CONFIG.step_limit
    order = pay_order_of(bundle, switches.gamma, limit, switches.soft_breaks_per_step)
    print(
        f"rebuild-rewards: pay order: {order.summary()} (gamma {switches.gamma}, "
        f"step limit {limit}, soft breaks per step {switches.soft_breaks_per_step})"
    )
    return True


def _frame(machine: PaperRewardMachine, moves: bool = True) -> tuple:
    """What a reward rebuild keeps: states, finals, end judgment and every transition that moves.

    A loop that stays put is left out: the promise cost makes the idle loops of a state with a
    promise open into priced transitions, and a loop with no reward is the same as none. The end
    judgment is kept as the states it covers: its counts and failed rewards are pay. Without
    ``moves`` the transitions are left out too.
    """
    kept = {
        (item.source, item.condition, item.destination)
        for item in machine.transitions
        if moves and item.source != item.destination
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
        kept,
    )
