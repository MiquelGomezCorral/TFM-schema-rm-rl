"""Plan check: what a generated machine does with its card's own plans.

Each plan is judged the way training plays it: the episode stops at the first final or rejecting
state of the machine (the runtime's ``terminate_on_rm``), whatever the card's ``goal``, and
nothing after that counts. The solving plan must stop in a final state without entering the well
first; a machine with no final state must end it with nothing owed. A wrong plan that breaks a
hard rule must not stop in a final state. A wrong plan that breaks only soft rules still reaches
the goal, so it must pay a negative reward (the trace bank's R43 rule) or end where the solving
plan on its layout ends and pay less than it, plain (a soft rule broken at the end, such as
``Existence``'s, or on the finishing edge is priced by a smaller payout). With no final state, every
wrong plan, and an idle plan where it breaks a rule of the card, must pay less than the solving
plan on the same layout, plain and discounted at the bundle's gamma (the card review's pay test; a
bundle whose solving plan paid on no layout fails), and must end in the well where it breaks a
hard rule for good (``broken@i`` in the card's judge, not ``open_at_end``). An idle run that keeps
every rule is held to the solving plan's rules. A machine that stops before the agent acts fails
every plan. The plans run in
the card's real env on the layouts of the trace bank, through the bundle's own labeling and Reward
Machine. No model call. The record of one bundle sits beside its folder, like the labeling check's.
"""

from pathlib import Path
from typing import Any

from src.arm_fm.artifacts import ArtifactBundle
from src.config import Configuration

from .cards import Card
from .declare_judge import BROKEN, HARD, Judgment, judge_trace
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
IDLE = "idle"  # the plan that only waits, played on a machine with no final state
KEEPS_RULES = "keeps-rules"  # the kind of an idle run that breaks no rule of its card
SOFT_UNPAID = "breaks only soft rules and pays nothing"
# A wait stops where the env ends the episode (plans.py), so this one waits to the level's end.
_IDLE_STEPS = ({"do": "wait", "n": 10**6},)


def check_card_plans(bundle: ArtifactBundle, card: Card, run_seed: int) -> dict[str, Any]:
    """Play every plan of ``card`` through ``bundle``; the record says if the machine pays them.

    A machine with no final state also plays the idle plan, and its wrong runs must pay less than
    the solving run of their layout (``_check_pay``) and end in the well where they break a hard
    rule for good (``_unpriced_breaks``). ``passed`` is None when nothing was checked:
    no plan could run in the card's env (each is listed with its ``error``, not a failure of the
    machine) or the bundle has no labeling.
    """
    if not bundle.labeling_source.strip():
        return {
            "card": card.id,
            "passed": None,
            "problems": ["no labeling source: nothing to replay"],
            "runs": [],
        }
    no_goal = not bundle.reward_machine.final_states
    plans = plans_of(card) + ([(IDLE, _IDLE_STEPS, [])] if no_goal else [])
    gamma = bundle.manifest.effective_settings.get("gamma") or Configuration.gamma
    runs = [
        _check_run(bundle, card, plan, seed, gamma)
        for seed in card.reset_seeds(run_seed)
        for plan in plans
    ]
    _price_soft_breaks(runs)
    problems = _check_pay(runs) if no_goal else []
    problems += [
        f"{run['plan']}-s{run['seed']}: {text}" for run in runs for text in run["problems"]
    ]
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
    bundle: ArtifactBundle, card: Card, plan: tuple[str, Any, Any], seed: int, gamma: float
) -> dict[str, Any]:
    name, steps, breaks = plan
    kind = _kind(card, breaks)
    entry: dict[str, Any] = {"plan": name, "kind": kind, "seed": seed, "problems": []}
    try:
        rollout = run_plan(card.env, steps, seed)
    except (PlanError, NoReferenceLabelerError) as error:
        return {**entry, "error": f"cannot run: {error}"}
    machine = bundle.reward_machine
    finals, well = set(machine.final_states), set(machine.rejecting_states)
    judgment = None if finals or kind == SOLVE else judge_trace(card.expect, rollout.labels)
    if name == IDLE:  # idling is a wrong plan only on a layout where it breaks a rule
        broken = judgment.failed()
        entry["kind"] = _kind(card, broken) if broken else KEEPS_RULES
    replay = replay_in_bundle(bundle, make_record("", card, name, "plan", rollout))
    if replay.error:
        return {**entry, "problems": [f"the labeling failed: {replay.error}"]}

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
    rewards = replay.rewards[:stop]
    discounted = sum(gamma**step * reward for step, reward in enumerate(rewards))
    problems = _problems(entry["kind"], bool(finals), ending, rewards)
    if judgment is not None and ending["end"] != WELL:
        problems += _unpriced_breaks(judgment)
    return {
        **entry,
        "problems": problems,
        **ending,
        "pay": [round(sum(rewards), 4), round(discounted, 4)],
    }


def _check_pay(runs: list[dict[str, Any]]) -> list[str]:
    """Add a problem to each wrong run that pays as much as the solving run of its seed.

    ``pay`` is ``[plain, discounted]``; a wrong run must pay less on both. An idle run that keeps
    every rule and a seed whose solving run did not play are not compared. Returns the problem of
    the bundle as a whole: no solving run paid on any seed, so nothing was compared.
    """
    solved = {run["seed"]: run["pay"] for run in runs if run["kind"] == SOLVE and "pay" in run}
    if not solved:
        return ["no solving run to compare pay with"]
    for run in runs:
        best = solved.get(run["seed"])
        if run["kind"] in (SOLVE, KEEPS_RULES) or best is None or "pay" not in run:
            continue
        if any(paid >= solve for paid, solve in zip(run["pay"], best, strict=True)):
            run["problems"].append(f"pays {run['pay']}, not less than the solving plan's {best}")
    return []


def _price_soft_breaks(runs: list[dict[str, Any]]) -> None:
    """Drop ``SOFT_UNPAID`` from a soft break that ends like the solving run of its seed, paying less.

    Only plain pay counts: a slower plan pays less discounted pay with nothing charged. The end
    must match, so a soft rule compiled as hard (the plan reaches the goal, the machine does not)
    still fails.
    """
    solved = {run["seed"]: run for run in runs if run["kind"] == SOLVE and "pay" in run}
    for run in runs:
        best = solved.get(run["seed"])
        if SOFT_UNPAID not in run["problems"] or best is None:
            continue
        if run["end"] == best["end"] and run["pay"][0] < best["pay"][0]:
            run["problems"].remove(SOFT_UNPAID)


def _unpriced_breaks(judgment: Judgment) -> list[str]:
    """The hard rules a run breaks for good although the machine kept it out of the well."""
    return [
        f"breaks hard {verdict.clause[0]}({', '.join(verdict.clause[1])}) at step {verdict.step} "
        "and does not end in the well"
        for verdict in judgment.verdicts
        if verdict.clause[2] == HARD and verdict.status == BROKEN
    ]


def _problems(
    kind: str, has_final: bool, ending: dict[str, Any], rewards: list[float]
) -> list[str]:
    """What the machine does wrong with a plan of this ``kind``, from where the episode stopped."""
    end, steps, owed = ending["end"], ending["steps"], ending["owed"]
    if steps == 0 and end != OPEN:
        return ["ends the episode before the agent acts"]
    if kind == SOFT_BREAK:  # a soft rule broken for good does not stop the goal; it must cost
        return [] if any(reward < 0 for reward in rewards) else [SOFT_UNPAID]
    if kind in (SOLVE, KEEPS_RULES):  # an idle run that keeps every rule must not be punished
        if end == WELL:
            return [f"enters the well at step {steps}"]
        if has_final and end != FINAL:
            return [f"ends in {ending['end_state']}, not the final"]
        return [f"ends owing {owed}"] if not has_final and owed else []
    return [f"reaches the final at step {steps}"] if end == FINAL else []
