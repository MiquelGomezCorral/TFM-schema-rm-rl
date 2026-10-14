"""Drop the Reward Machine states and transitions the environment cannot reach.

The environment's declared constraints say which proposition valuations can follow each other.
The walk starts at the initial state and tries every allowed valuation at every step, remembering
which tracked propositions were true so far. A state nobody reaches, and a transition nobody
takes, cannot matter to a run. Rewards, the final and the well are never added or changed here.
"""

import itertools
import re
from collections import defaultdict, deque
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass

from src.models import Constraint, ExclusiveConstraint, LatchConstraint, OrderConstraint

from .reward_machine import (
    RewardMachineStructure,
    Transition,
    evaluate_boolean_guard,
    parse_boolean_guard,
)

MAX_WALK_PROPOSITIONS = 16
_GUARD_NAME = re.compile(r"[a-z_][a-z0-9_]*")


@dataclass(frozen=True)
class ConstraintPruning:
    """The machine without what the constraints rule out, and what was removed.

    ``removed_states`` use the numbering of the machine before the removal; the kept states
    are renumbered, so only the counts mean anything to a reader of the new machine.
    """

    reward_machine: RewardMachineStructure
    removed_states: tuple[int, ...]
    removed_transitions: int


def prune_by_constraints(
    machine: RewardMachineStructure, constraints: Sequence[Constraint]
) -> ConstraintPruning:
    """Remove every state and transition no constraint-respecting run reaches.

    Works on compiler machines: guards are Boolean expressions with no ``else`` row, and a
    step no guard matches stays in its state. The kept states are numbered breadth first, as
    the reward layer numbers them. Raises ``ValueError`` when the constraints leave the final
    state unreachable.
    """
    if not constraints:
        return ConstraintPruning(machine, (), 0)

    guards = [_guard_text(transition) for transition in machine.transitions]
    visible = {name for guard in guards for name in _GUARD_NAME.findall(guard.lower())}
    visible -= {"true", "false"}
    tracked = _tracked(constraints)
    names = sorted(visible | tracked)
    if len(names) > MAX_WALK_PROPOSITIONS:
        raise ValueError(
            f"{len(names)} propositions are too many to check the constraints against the machine"
        )

    parsed = [parse_boolean_guard(guard, visible) for guard in guards]
    reached, taken = _walk(machine, parsed, constraints, tracked, names)
    if machine.final_state is not None and machine.final_state not in reached:
        raise ValueError(
            "The environment's constraints leave the final state unreachable, so no run can "
            "complete the task"
        )

    removed_states = tuple(state for state in machine.states if state not in reached)
    kept = [machine.transitions[index] for index in sorted(taken)]
    removed_transitions = len(machine.transitions) - len(kept)
    if not removed_states and not removed_transitions:
        return ConstraintPruning(machine, (), 0)
    return ConstraintPruning(_renumbered(machine, kept), removed_states, removed_transitions)


# ======================================================================================
#                                          WALK
# ======================================================================================


def _guard_text(transition: Transition) -> str:
    return " & ".join(transition.condition) or "true"


def _tracked(constraints: Iterable[Constraint]) -> set[str]:
    """The propositions whose history the walk must remember: the earlier ones and the latches."""
    tracked: set[str] = set()
    for constraint in constraints:
        match constraint:
            case OrderConstraint(earlier=name) | LatchConstraint(name=name):
                tracked.add(name)
    return tracked


def _walk(
    machine: RewardMachineStructure,
    guards: Sequence,
    constraints: Sequence[Constraint],
    tracked: Collection[str],
    names: Sequence[str],
) -> tuple[set[int], set[int]]:
    """Return the states reached and the indexes of the transitions taken.

    A proposition no guard mentions and no constraint tracks is left false: that never
    breaks a constraint, because it can only be a later proposition or one of an exclusive pair.
    """
    outgoing = defaultdict(list)
    for index, transition in enumerate(machine.transitions):
        outgoing[transition.source].append(index)

    valuations = [
        dict(zip(names, values, strict=True))
        for values in itertools.product((False, True), repeat=len(names))
    ]
    start = (machine.initial_state, frozenset())
    visited = {start}
    queue = deque([start])
    reached = {machine.initial_state}
    taken: set[int] = set()
    while queue:
        state, seen = queue.popleft()
        for valuation in valuations:
            if not _allows(constraints, valuation, seen):
                continue

            destination = state
            for index in outgoing[state]:
                if evaluate_boolean_guard(guards[index], valuation):
                    taken.add(index)
                    destination = machine.transitions[index].destination
                    break
            key = (destination, seen | {name for name in tracked if valuation.get(name)})
            if key not in visited:
                visited.add(key)
                reached.add(destination)
                queue.append(key)
    return reached, taken


def _allows(
    constraints: Iterable[Constraint], valuation: dict[str, bool], seen: frozenset[str]
) -> bool:
    """Whether the environment can produce ``valuation`` after the tracked ``seen`` ones."""
    history = seen | {name for name, value in valuation.items() if value}
    for constraint in constraints:
        match constraint:
            case OrderConstraint(later, earlier):
                allowed = not valuation.get(later) or earlier in history
            case ExclusiveConstraint(first, second):
                allowed = not (valuation.get(first) and valuation.get(second))
            case LatchConstraint(name):
                allowed = valuation.get(name) or name not in seen
        if not allowed:
            return False
    return True


# ======================================================================================
#                                       RENUMBERING
# ======================================================================================


def _renumbered(
    machine: RewardMachineStructure, kept: Sequence[Transition]
) -> RewardMachineStructure:
    """Number the states of the kept transitions breadth first, as the reward layer does."""
    outgoing = defaultdict(list)
    for transition in kept:
        outgoing[transition.source].append(transition)

    numbers = {machine.initial_state: 0}
    queue = deque([machine.initial_state])
    while queue:
        for transition in sorted(outgoing[queue.popleft()], key=lambda item: item.condition):
            if transition.destination not in numbers:
                numbers[transition.destination] = len(numbers)
                queue.append(transition.destination)

    transitions = sorted(
        (
            Transition(
                numbers[transition.source],
                numbers[transition.destination],
                transition.condition,
                transition.reward,
            )
            for transition in kept
        ),
        key=lambda item: (item.source, item.condition),
    )
    final = machine.final_state
    return RewardMachineStructure(
        states=tuple(range(len(numbers))),
        initial_state=0,
        final_state=None if final is None else numbers[final],
        rejecting_states=tuple(
            sorted(numbers[state] for state in machine.rejecting_states if state in numbers)
        ),
        transitions=tuple(transitions),
    )
