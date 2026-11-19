"""Rebuild a compiler bundle's Reward Machine rewards with the current reward layer.

No model call. Use it after a change to how the reward layer prices edges, to try a soft-break
cost, or to turn the promise cost on. The result goes to a new bundle folder; the source is never
written.
"""

from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

from src.arm_fm import ArtifactBundle, configured_step_limit, load_bundle
from src.arm_fm.pay_order import record_pay_order
from src.compiler import PaperRewardMachine, RewardSwitches, compile_dfas
from src.config import Configuration
from src.utils import preflight_paths, print_warning

from .ablate_rm import _build, _recorded_switches, _stored_task

REBUILD_RULE = "whole-unit pay, owed-stage charge, soft break without refund"
PROMISE_COST_RULE = "promise cost (-0.1 on every step while a hard promise is open)"
# What prices the hard break: each is the command's when given, else the bundle's.
PRICING = ("soft_break_cost", "hard_ceiling", "gamma", "soft_breaks_per_step")


def rebuild_switches(
    CONFIG: Configuration, bundle: ArtifactBundle, given: Mapping[str, object]
) -> tuple[RewardSwitches, dict[str, str]]:
    """The switches of a rebuild, and where each pricing value (and the step limit) came from.

    The pricing values of ``PRICING`` are the command's when ``given`` has one (None means the
    option was omitted: ``CONFIG`` cannot say so), else the ones the bundle records. A value the
    bundle records none of is today's default, except the hard ceiling: a bundle that records none
    was made before it existed and paid the flat hard break. The step limit is the one
    ``CONFIG`` names, else the bundle's.
    """
    recorded = _recorded_switches(bundle)
    settings = bundle.manifest.effective_settings
    pricing, origin = {}, {}
    for name in PRICING:
        if given.get(name) is not None:
            pricing[name], origin[name] = given[name], "command"
        else:
            pricing[name] = getattr(recorded, name)
            if name in settings:
                origin[name] = "bundle"
            elif name == "hard_ceiling":
                origin[name] = "bundle: made before the ceiling, so flat"
            else:
                origin[name] = "default: the bundle records none"
    step_limit = configured_step_limit(CONFIG)
    if step_limit is not None:
        origin["step_limit"] = "command"
    elif recorded.step_limit is not None:
        origin["step_limit"] = "bundle"
    else:
        origin["step_limit"] = "none: not recorded, not given"
    switches = replace(
        recorded,
        reward_promise_cost=recorded.reward_promise_cost or CONFIG.reward_promise_cost,
        recurrent_soft_penalty=recorded.recurrent_soft_penalty and CONFIG.recurrent_soft_penalty,
        step_limit=recorded.step_limit if step_limit is None else step_limit,
        **pricing,
    )
    return switches, origin


def rebuild_rewards(
    CONFIG: Configuration, destination: Path, given: Mapping[str, object] | None = None
) -> bool:
    """Write ``destination``: ``CONFIG.bundle`` with today's rewards for its stored clauses.

    The machine is rebuilt from the clauses and the reward switches the bundle records (clause,
    LTLf, MONA, reward layer); ``CONFIG.reward_promise_cost`` turns the promise cost on and
    ``CONFIG.recurrent_soft_penalty`` False charges each soft rule once. The pricing keeps what
    the bundle records unless ``given`` has another (``rebuild_switches``): ``gamma``,
    ``soft_breaks_per_step`` (the soft breaks per step the ceiling assumes), ``soft_break_cost``
    and ``hard_ceiling``, which prices the hard break above the discounted soft ceiling (see
    ``hard_break_charge``) over the level's step limit: ``CONFIG.step_limit``, else the limit of
    the level ``CONFIG.gym_id`` and ``CONFIG.env_kwargs`` make, else the bundle's recorded one.
    An omitted option is None or absent in ``given`` (``CONFIG`` cannot say "omitted"). To rebuild
    a bundle made with the old defaults to today's, give ``--soft-break-cost`` and
    ``--hard-ceiling`` with the level; the log names where each value came from.
    ``fold_soft_absence`` stays as
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
    switches, origin = rebuild_switches(CONFIG, bundle, given or {})
    print(
        "rebuild-rewards: pricing: "
        + ", ".join(
            f"{name} {getattr(switches, name)} ({origin[name]})"
            for name in (*PRICING, "step_limit")
        )
    )
    if switches.hard_ceiling and switches.step_limit is None:
        print_warning(
            "rebuild-rewards: the hard ceiling needs the level's step limit; "
            "pass --gym-id or --step-limit, or --no-hard-ceiling"
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
    pay = record_pay_order(bundle)
    bundle.save(destination, overwrite=CONFIG.overwrite)
    print(f"rebuild-rewards: {destination}: rewards rebuilt from {CONFIG.bundle}")
    print(f"rebuild-rewards: pay order: {pay['summary']}")
    if pay["ok"] is not True:
        print_warning(f"rebuild-rewards: {destination}: pay order: {pay['summary']}")
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
