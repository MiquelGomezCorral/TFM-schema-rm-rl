"""Machines that end the episode before the agent can act, and episodes that never got to start.

A machine whose start state is final (or reaches a final state from the start layout's labels,
or with no proposition needed) ends every episode after the first action, so every rule "holds"
without anything being tested. The judge reports that machine (``machine_too_simple``) and fails
each test episode the machine ended
in a final state, with the environment not done, within a short share of the card's expected
length (``episode_cannot_start``).
"""

import re
from collections.abc import Callable, Mapping
from itertools import product
from math import ceil
from statistics import median
from typing import Any

from src.arm_fm.runtime import RewardMachineRuntime
from src.compiler.reward_machine import evaluate_boolean_guard, parse_boolean_guard
from src.compiler.rm_format import PaperRewardMachine

from .cards import Card
from .plans import PlanError, run_plan
from .reference_labels import NoReferenceLabelerError

START_SHARE = 0.10  # an episode this short, against the expected length, could not start
START_SHARE_STRICT = 0.05  # reported beside it, so the choice of 10% stays visible
PLAN_SEED = 1  # the trace bank's run seed: the reset seed of a card with neither events nor layout


def machine_too_simple(
    machine: PaperRewardMachine, start_labels: Mapping[int, Mapping[str, bool]] | None = None
) -> str | None:
    """Why the machine ends every episode at once, or None when it does not.

    The start state is final, or a final state is reached from it by walking the machine; a
    rejecting state stops the walk and does not count.

    With ``start_labels`` (the labeling's valuation at reset, by reset seed) the walk holds that
    valuation fixed until no new state shows up, and the machine is flagged when any seed's walk
    reaches a final state; the reason names those seeds. Without it (a static scan of machine
    files) the walk follows only ``else`` transitions and guards that are always true.
    """
    start = machine.initial_state
    if start in machine.final_states:
        return f"the start state {start} is final"
    if start_labels is None:
        path = _walk(machine, lambda state: _free_step(machine, state))
        return None if path is None else f"{' -> '.join(path)} needs no proposition"
    reached: dict[str, list[int]] = {}
    for seed, labels in start_labels.items():
        runtime = RewardMachineRuntime(machine)
        values = {name: bool(labels[name]) for name in machine.propositions}
        path = _walk(
            machine, lambda _state, runtime=runtime, values=values: runtime.step(values).destination
        )
        if path is not None:
            reached.setdefault(" -> ".join(path), []).append(seed)
    if not reached:
        return None
    return "; ".join(
        f"{path} on the labels true at reset, seeds {seeds}" for path, seeds in reached.items()
    )


def _walk(machine: PaperRewardMachine, step: Callable[[str], str]) -> list[str] | None:
    """The states from the start to the first final state ``step`` reaches, else None."""
    path = [machine.initial_state]
    while path[-1] not in machine.rejecting_states:
        destination = step(path[-1])
        if destination in path:
            return None
        path.append(destination)
        if destination in machine.final_states:
            return path
    return None


def _free_step(machine: PaperRewardMachine, state: str) -> str:
    """Where the machine goes from ``state`` with no proposition needed.

    The first always-true guard, else the first ``else``; it stays put when there is neither.
    """
    rows = [row for row in machine.transitions if row.source == state]
    for row in rows:
        if not row.is_else and _always_true(machine, row.condition):
            return row.destination
    return next((row.destination for row in rows if row.is_else), state)


def _always_true(machine: PaperRewardMachine, condition: str) -> bool:
    """Whether the guard holds under every valuation of the propositions it names."""
    guard = parse_boolean_guard(condition, machine.propositions)
    names = [
        name
        for name in machine.propositions
        if name.lower() in re.findall(r"\w+", condition.lower())
    ]
    return all(
        evaluate_boolean_guard(
            guard,
            {**dict.fromkeys(machine.propositions, False), **dict(zip(names, bits, strict=True))},
        )
        for bits in product((False, True), repeat=len(names))
    )


def expected_length(card: Card) -> int | None:
    """The median length of the card's solving plan over its reset seeds, run in the env.

    None when the card has no solving plan or the plan cannot run. The trace bank stores these
    lengths too (``solve-s<seed>.json``); the judge runs the plan itself so it needs no bank.
    """
    if not card.solve:
        return None
    try:
        lengths = [
            len(run_plan(card.env, card.solve, seed).actions)
            for seed in card.reset_seeds(PLAN_SEED)
        ]
    except (PlanError, NoReferenceLabelerError):
        return None
    return int(median(lengths))


def start_limit(expected: int | None, share: float = START_SHARE) -> int:
    """The longest episode, in steps, that counts as "could not start"; 1 step at least."""
    return max(1, ceil(share * (expected or 0)))


def episode_cannot_start(
    length: int, machine_ended_in_final: bool, expected: int | None, share: float = START_SHARE
) -> bool:
    """Whether the machine ended the episode in a final state, within ``start_limit`` steps.

    ``machine_ended_in_final`` is false when the environment ended the episode, or the machine
    ended it in a rejecting state.
    """
    return machine_ended_in_final and length <= start_limit(expected, share)


def length_header(expected: int | None) -> dict[str, Any]:
    """The ``judge.json`` fields of the expected length and the two cannot-start limits."""
    return {
        "expected_length": expected,
        "expected_length_source": "median length of the card's solving plan, run in the env",
        "cannot_start_limit": start_limit(expected),
        "cannot_start_limit_5pct": start_limit(expected, START_SHARE_STRICT),
    }


def machine_header(
    machine: PaperRewardMachine | None, start_labels: Mapping[int, Mapping[str, bool]] | None
) -> dict[str, Any]:
    """The ``judge.json`` fields of the too-simple check: flag, reason, and which form ran."""
    if machine is None:
        return {"machine_too_simple": None, "machine_too_simple_reason": None}
    reason = machine_too_simple(machine, start_labels)
    check = (
        "static (else and always-true guards)"
        if start_labels is None
        else f"start labels of {len(start_labels)} test reset seeds"
    )
    return {
        "machine_too_simple": reason is not None,
        "machine_too_simple_reason": reason,
        "machine_too_simple_check": check,
    }
