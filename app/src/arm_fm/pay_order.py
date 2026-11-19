"""Walk a Reward Machine for what each way an episode can end pays, and check their order.

Report only: nothing here changes a machine. The walk reads the machine alone (transitions, final
and rejecting states, end judgment), so it runs on any bundle, compiled or not. It is approximate:
a machine cannot tell what the world forces, so every figure is what the machine allows.
"""

import itertools
import math
from collections.abc import Sequence
from dataclasses import fields
from typing import NamedTuple

from src.compiler import PaperRewardMachine
from src.compiler.reward_layer import RewardSwitches, discounted_steps
from src.config import Configuration

from .artifacts import ArtifactBundle
from .runtime import RewardMachineRuntime

_EPSILON = 1e-9

# The ways an episode can end, best first. Each must pay more than the next, except that
# "not started" only has to pay at least as much as a soft break.
ENDINGS = ("finished", "started", "not started", "soft break", "hard break")
_MAY_TIE = {("not started", "soft break")}

_Edge = tuple[str, str, float]  # source, destination, reward


class PayOrder(NamedTuple):
    """What a machine pays for each way an episode can end, and the first priority it breaks.

    ``pay`` maps an ending of ``ENDINGS`` to its return, or None when the machine has no such
    ending. ``broken`` is the first pair of present endings, better first, that the machine does
    not pay in that order. ``stall`` is what the promise cost charges over the step limit while a
    hard promise stays open (None without it); it is no ending and takes no part in the order.
    """

    pay: dict[str, float | None]
    broken: tuple[str, str] | None
    stall: float | None = None

    def summary(self) -> str:
        """The endings from the best pay to the worst, ``ok`` or the first broken pair, the stall."""
        present = sorted(
            ((value, name) for name, value in self.pay.items() if value is not None),
            key=lambda item: (-item[0], ENDINGS.index(item[1])),
        )
        order = " > ".join(f"{name} {value:g}" for value, name in present)
        if self.broken is None:
            text = f"{order}; ok"
        else:
            better, worse = self.broken
            need = "at least as much as" if self.broken in _MAY_TIE else "more than"
            text = f"{order}; broken: {better} must pay {need} {worse}"
        return text if self.stall is None else f"{text}; stall, hard promise open {self.stall:g}"


def record_pay_order(bundle: ArtifactBundle) -> dict:
    """Check the pay order of a bundle just built and record it in its manifest; report only.

    The gamma, step limit and soft breaks per step are the ones the manifest records (the
    reward switches the machine was priced with). ``effective_settings["pay_order"]`` keeps
    ``ok``, the mildest hard break charge and the summary line, and is returned. ``ok`` is None
    when the check did not run: with no step limit it would judge a horizon that is not the
    run's, and an error in it must not lose a bundle that cost model calls; the summary says
    which.
    """
    settings = bundle.manifest.effective_settings
    record = {"ok": None, "hard_charge": None, "summary": "not checked: no step limit"}
    if settings.get("step_limit") is not None:
        try:
            order = pay_order_of(
                bundle, settings["gamma"], settings["step_limit"], settings["soft_breaks_per_step"]
            )
        except Exception as error:  # report only: never fail the run that made the bundle
            record["summary"] = f"check failed: {type(error).__name__}: {error}"
        else:
            record = {
                "ok": order.broken is None,
                "hard_charge": order.pay["hard break"],
                "summary": order.summary(),
            }
    settings["pay_order"] = record
    return record


def has_soft_rules(bundle: ArtifactBundle) -> bool:
    """Whether the bundle's task has a soft clause; a bundle that stores no clauses is read as yes."""
    clauses = bundle.manifest.generation.get("clauses")
    return clauses is None or any(clause[2] == "soft" for clause in clauses)


def ceiling_priced(bundle: ArtifactBundle) -> bool:
    """Whether the hard break charge is the ceiling, so it depends on gamma, step limit and breaks.

    Only a bundle made with ``hard_ceiling`` and with repeating soft breaks is (its manifest records
    the values it assumed); the others pay the flat well charge whatever the run's values are. A
    manifest that records no ``hard_ceiling`` predates it.
    """
    recorded = bundle.manifest.effective_settings
    switches = RewardSwitches(
        **{"hard_ceiling": False}
        | {
            item.name: recorded[item.name]
            for item in fields(RewardSwitches)
            if item.name in recorded
        }
    )
    return switches.prices_soft_stream(has_soft_rules(bundle))


def pay_order_of(
    bundle: ArtifactBundle, gamma: float, step_limit: int | None, soft_breaks_per_step: int
) -> PayOrder:
    """``pay_order`` of a bundle's machine, with the promise cost and the soft rules from its manifest.

    A bundle that stores no clauses is read as having a soft rule. A step charges at most
    ``soft_breaks_per_step`` soft breaks of the cost the manifest records: the assumption the
    hard ceiling makes (``CONFIG.soft_breaks_per_step``).
    """
    settings = bundle.manifest.effective_settings
    break_cost = settings.get("soft_break_cost", Configuration.soft_break_cost)
    soft_step_cap = soft_breaks_per_step * break_cost if has_soft_rules(bundle) else 0.0
    return pay_order(
        bundle.reward_machine,
        gamma,
        step_limit,
        bool(settings.get("reward_promise_cost")),
        soft_step_cap,
    )


def pay_order(
    machine: PaperRewardMachine,
    gamma: float,
    step_limit: int | None,
    promise_cost: bool = False,
    soft_step_cap: float = math.inf,
) -> PayOrder:
    """What ``machine`` pays for each ending over ``step_limit`` steps (one when None) at ``gamma``.

    ``finished``: the best path to a final state. ``started``: the best state short of the end
    that is not the start and that a path reaches without losing pay (a broken soft rule, or a
    trigger the world fires, loses some), with its end charge. ``not started``: doing nothing, no proposition
    ever true. ``soft break``: the worst pay the machine can charge on a step that does not end
    the episode, on every step when a loop pays it. ``hard break``: the mildest edge into a
    rejecting state. The end charge is the end judgment's, paid on the last step; the flat
    time-limit penalty is left out: every episode that times out pays it, discounted to almost
    nothing. With ``promise_cost`` (the machine charges it) a pay of exactly the promise cost is
    the ``stall``, not a soft break: the machine alone cannot tell them apart, so a break that
    costs the same as the promise cost reads as a stall. ``soft_step_cap`` is the most a step
    can charge for soft breaks (the soft breaks per step assumed, times the break cost): a step
    or a loop the machine would charge more for reads as this much. A task without soft rules
    has a cap of 0, so no soft break: a negative edge is then a step back from progress.
    """
    steps = step_limit or 1
    ends = {*machine.final_states, *machine.rejecting_states}
    edges = [
        (item.source, item.destination, float(item.reward))
        for item in machine.transitions
        if item.source not in ends
    ]
    walkable = [edge for edge in edges if edge[1] not in machine.rejecting_states]
    best = _best_returns(walkable, machine.initial_state)
    judgment = machine.judgment
    tail = gamma ** (steps - 1)

    def end_charge(state: str) -> float:
        return tail * judgment.end_charge(state) if judgment else 0.0

    started = [
        best[state] + end_charge(state)
        for state in best
        if state != machine.initial_state and state not in ends and best[state] >= -_EPSILON
    ]
    idle, idling_in = _idle_run(machine, steps, gamma)
    if idling_in is not None:
        idle += end_charge(idling_in)

    open_edges = [edge for edge in walkable if edge[0] in best and edge[1] not in ends]
    loop = _worst_cycle_mean([state for state in best if state not in ends], open_edges)
    worst_edge = min((reward for *_, reward in open_edges), default=None)

    streamed = None if loop is None else loop * discounted_steps(steps, gamma)

    def stalls(rate: float | None) -> bool:
        return (
            promise_cost
            and rate is not None
            and abs(rate - Configuration.PROMISE_COST_REWARD) < _EPSILON
        )

    floor = -soft_step_cap
    edge_pay = None if worst_edge is None or stalls(worst_edge) else max(worst_edge, floor)
    stream_pay = (
        None if loop is None or stalls(loop) else max(loop, floor) * discounted_steps(steps, gamma)
    )
    breaks = [pay for pay in (edge_pay, stream_pay) if pay is not None and pay < 0]
    hard_breaks = [
        reward for _, destination, reward in edges if destination in machine.rejecting_states
    ]

    pay = {
        "finished": max(
            (best[state] for state in machine.final_states if state in best), default=None
        ),
        "started": max(started, default=None),
        "not started": idle,
        "soft break": min(breaks, default=None),
        "hard break": max(hard_breaks, default=None),
    }
    pay = {name: None if value is None else round(value, 9) + 0.0 for name, value in pay.items()}
    return PayOrder(pay, _first_broken(pay), round(streamed, 9) + 0.0 if stalls(loop) else None)


def _best_returns(edges: Sequence[_Edge], source: str) -> dict[str, float]:
    """The largest return of any path from ``source`` to each state it reaches.

    Loops pay 0 or less on a compiled machine (``_has_positive_cycle``), so the rounds end within
    one per state; the round count bounds a machine that does not keep that.
    """
    best = {source: 0.0}
    for _ in range(len(edges) + 1):
        improved = False
        for start, destination, reward in edges:
            if start in best and best[start] + reward > best.get(destination, -math.inf) + _EPSILON:
                best[destination] = best[start] + reward
                improved = True
        if not improved:
            break
    return best


def _idle_run(machine: PaperRewardMachine, steps: int, gamma: float) -> tuple[float, str | None]:
    """The discounted return of an agent that does nothing, and the state it idles in.

    The state is None when a final or rejecting state ended the episode before ``steps`` ran out.
    A step that stays in its state repeats every step after it, so the rest is summed at once.
    """
    ends = {*machine.final_states, *machine.rejecting_states}
    runtime = RewardMachineRuntime(machine, warning_handler=lambda _message: None)
    quiet = dict.fromkeys(runtime.propositions, False)
    total = 0.0
    for step in range(steps):
        moved = runtime.step(quiet)
        pay = gamma**step * moved.reward
        if moved.destination in ends:
            return total + pay, None
        if moved.destination == moved.source:
            return total + pay * discounted_steps(steps - step, gamma), moved.destination
        total += pay
    return total, runtime.state


def _worst_cycle_mean(states: Sequence[str], edges: Sequence[_Edge]) -> float | None:
    """The lowest average reward per edge of any cycle among ``edges`` (Karp), or None if none."""
    index = {state: number for number, state in enumerate(states)}
    count = len(states)
    walks = [[0.0] * count]  # walks[k][node]: the least reward of a k-edge walk ending there
    for _ in range(count):
        row = [math.inf] * count
        for source, destination, reward in edges:
            row[index[destination]] = min(
                row[index[destination]], walks[-1][index[source]] + reward
            )
        walks.append(row)
    means = [
        max(
            (walks[count][node] - walks[length][node]) / (count - length)
            for length in range(count)
            if walks[length][node] < math.inf
        )
        for node in range(count)
        if walks[count][node] < math.inf
    ]
    return min(means, default=None)


def _first_broken(pay: dict[str, float | None]) -> tuple[str, str] | None:
    """The first pair of present endings, better first, that the machine does not pay in order."""
    present = [name for name in ENDINGS if pay[name] is not None]
    for better, worse in itertools.pairwise(present):
        gap = pay[better] - pay[worse]
        if gap < -_EPSILON or (gap < _EPSILON and (better, worse) not in _MAY_TIE):
            return better, worse
    return None
