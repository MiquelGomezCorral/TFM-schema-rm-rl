"""Plan check: what a generated machine does with its card's own plans.

Each plan is judged the way training plays it: the episode stops at the first final or rejecting
state of the machine (the runtime's ``terminate_on_rm``), whatever the card's ``goal``, and
nothing after that counts. The solving plan must stop in a final state without entering the well
first; a machine with no final state must end it with nothing owed. A wrong plan that breaks a
hard rule must not stop in a final state; with no final it ends owing or in the well. A wrong plan
that breaks only soft rules still reaches the goal, so it must pay a negative reward (the trace
bank's R43 rule). A machine that stops before the agent acts fails every plan. The plans run in
the card's real env on the layouts of the trace bank, through the bundle's own labeling and Reward
Machine. No model call. The record of one bundle sits beside its folder, like the labeling check's.
"""

from pathlib import Path
from typing import Any

from src.arm_fm.artifacts import ArtifactBundle

from .cards import Card
from .declare_judge import HARD
from .plans import PlanError, run_plan
from .reference_labels import NoReferenceLabelerError
from .traces import (
    HARD_BREAK,
    SOFT_BREAK,
    SOLVE,
    make_record,
    plans_of,
    replay_in_bundle,
    write_json,
)

RECORD_SUFFIX = ".plan_check.json"
FAILED_REASON = "plan-check-failed"  # the reason a failed generation records
FINAL, WELL, OPEN = "final", "well", "open"  # where a plan's episode stops


def check_card_plans(bundle: ArtifactBundle, card: Card, run_seed: int) -> dict[str, Any]:
    """Play every plan of ``card`` through ``bundle``; the record says if the machine pays them.

    ``passed`` is None when nothing was checked: no plan could run in the card's env (each is
    listed with its ``error``, not a failure of the machine) or the bundle has no labeling.
    """
    if not bundle.labeling_source.strip():
        return {
            "card": card.id,
            "passed": None,
            "problems": ["no labeling source: nothing to replay"],
            "runs": [],
        }
    runs = [
        _check_run(bundle, card, plan, seed)
        for seed in card.reset_seeds(run_seed)
        for plan in plans_of(card)
    ]
    problems = [f"{run['plan']}-s{run['seed']}: {text}" for run in runs for text in run["problems"]]
    checked = sum("error" not in run for run in runs)
    return {
        "card": card.id,
        "passed": not problems if checked else None,
        "problems": problems,
        "runs": runs,
    }


def failure_reason(record: dict[str, Any]) -> str:
    """The reason of a failed plan check: its name, then the first problem."""
    return f"{FAILED_REASON}: {record['problems'][0]}"


def check_and_record(
    bundle: ArtifactBundle, card: Card, run_seed: int, folder: Path
) -> dict[str, Any]:
    """``check_card_plans``, with its record written beside the bundle ``folder``."""
    record = check_card_plans(bundle, card, run_seed)
    write_json(folder.with_name(folder.name + RECORD_SUFFIX), record, indent=2)
    return record


def _kind(card: Card, breaks: list[int] | None) -> str:
    """``solve`` (no breaks list), ``soft-break`` (breaks only soft clauses) or ``hard-break``."""
    if breaks is None:
        return SOLVE
    only_soft = bool(breaks) and all(card.expect[index][2] != HARD for index in breaks)
    return SOFT_BREAK if only_soft else HARD_BREAK


def _check_run(
    bundle: ArtifactBundle, card: Card, plan: tuple[str, Any, Any], seed: int
) -> dict[str, Any]:
    name, steps, breaks = plan
    kind = _kind(card, breaks)
    entry: dict[str, Any] = {"plan": name, "kind": kind, "seed": seed, "problems": []}
    try:
        rollout = run_plan(card.env, steps, seed)
    except (PlanError, NoReferenceLabelerError) as error:
        return {**entry, "error": f"cannot run: {error}"}
    replay = replay_in_bundle(bundle, make_record("", card, name, "plan", rollout))
    if replay.error:
        return {**entry, "problems": [f"the labeling failed: {replay.error}"]}

    machine = bundle.reward_machine
    finals, well = set(machine.final_states), set(machine.rejecting_states)
    # Training stops at the first final or rejecting state; the replay plays on, so cut it there.
    states = replay.rm_states
    stop = next((i for i, state in enumerate(states) if state in finals | well), len(states) - 1)
    state = states[stop]
    ending = {
        "steps": stop,
        "end_state": state,
        "end": FINAL if state in finals else WELL if state in well else OPEN,
        "owed": machine.judgment.end_charge(state) if machine.judgment else 0.0,
    }
    problems = _problems(kind, bool(finals), ending, replay.rewards[:stop])
    return {**entry, "problems": problems, **ending}


def _problems(
    kind: str, has_final: bool, ending: dict[str, Any], rewards: list[float]
) -> list[str]:
    """What the machine does wrong with a plan of this ``kind``, from where the episode stopped."""
    end, steps, owed = ending["end"], ending["steps"], ending["owed"]
    if steps == 0 and end != OPEN:
        return ["ends the episode before the agent acts"]
    if kind == SOFT_BREAK:  # a soft rule broken for good does not stop the goal; it must cost
        return (
            []
            if any(reward < 0 for reward in rewards)
            else ["breaks only soft rules and pays nothing"]
        )
    if kind == SOLVE:
        if end == WELL:
            return [f"enters the well at step {steps}"]
        if has_final and end != FINAL:
            return [f"ends in {ending['end_state']}, not the final"]
        return [f"ends owing {owed}"] if not has_final and owed else []
    if end == FINAL:
        return [f"reaches the final at step {steps}"]
    if not has_final and end == OPEN and not owed:
        return ["ends with nothing owed and out of the well"]
    return []
