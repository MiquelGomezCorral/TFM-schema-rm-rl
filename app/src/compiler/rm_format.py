"""The shared ARM-FM two-section Reward Machine text format.

The compiler writes this format and the ARM-FM runtime reads it, so it lives below both:
``src.arm_fm`` imports it, and it never imports ``src.arm_fm``.
"""

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .reward_machine import (
    RewardMachineStructure,
    Transition,
    parse_boolean_guard,
    states_without_path_to_final,
)

_TRANSITION = re.compile(r"^\(\s*([^,]+?)\s*,\s*(.+?)\s*\)\s*->\s*(\S+)\s*$")
_REWARD = re.compile(
    r"^\(\s*([^,]+?)\s*,\s*(.+?)\s*,\s*([^,]+?)\s*\)\s*->\s*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*$"
)
_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]*", re.IGNORECASE)
_STATE_NUMBER = re.compile(r"^u(\d+)$", re.IGNORECASE)
_HEADER_LINE = re.compile(r"([A-Z_]+):\s*(.*)")


class RuntimeValidationError(ValueError):
    """A paper-format RM or valuation violates the runtime contract."""


@dataclass(frozen=True)
class RuntimeTransition:
    """One ordered transition in the paper's string-state format."""

    source: str
    condition: str
    destination: str
    reward: float = 0.0

    @property
    def is_else(self) -> bool:
        return self.condition.strip().lower() == "else"


@dataclass(frozen=True)
class PaperRewardMachine:
    """A paper-style RM with optional, possibly multiple final states."""

    states: tuple[str, ...]
    initial_state: str
    transitions: tuple[RuntimeTransition, ...]
    final_states: tuple[str, ...] = ()
    propositions: tuple[str, ...] = ()
    default_reward: float | None = None

    def __post_init__(self) -> None:
        states = tuple(str(state) for state in self.states)
        finals = tuple(self.final_states)
        _check_states(states, self.initial_state, finals)
        _check_transitions(self.transitions, set(states))
        _check_default_reward(self.default_reward)
        proposition_names = tuple(self.propositions) or _guard_propositions(self.transitions)
        _check_guards(self.transitions, proposition_names)
        object.__setattr__(self, "states", states)
        object.__setattr__(self, "final_states", finals)
        object.__setattr__(self, "propositions", proposition_names)


def _check_states(states: tuple[str, ...], initial_state: str, finals: tuple[str, ...]) -> None:
    if not states or len(set(states)) != len(states):
        raise RuntimeValidationError("Reward Machine states must be nonempty and unique")
    if initial_state not in states:
        raise RuntimeValidationError("Reward Machine initial state is not declared")
    if not set(finals) <= set(states):
        raise RuntimeValidationError("Reward Machine final state is not declared")


def _check_transitions(transitions: Sequence[RuntimeTransition], declared: set[str]) -> None:
    for transition in transitions:
        if transition.source not in declared or transition.destination not in declared:
            raise RuntimeValidationError("Transition references an undeclared state")
        if not math.isfinite(float(transition.reward)):
            raise RuntimeValidationError("Transition rewards must be finite")


def _check_default_reward(default_reward: float | None) -> None:
    if default_reward is not None and (
        not math.isfinite(float(default_reward)) or float(default_reward) != 0
    ):
        raise RuntimeValidationError("Default reward must be zero when declared")


def _check_guards(transitions: Sequence[RuntimeTransition], propositions: tuple[str, ...]) -> None:
    if len(set(propositions)) != len(propositions):
        raise RuntimeValidationError("Reward Machine propositions must be unique")
    for transition in transitions:
        if not transition.is_else:
            try:
                parse_boolean_guard(transition.condition, propositions)
            except ValueError as error:
                raise RuntimeValidationError(str(error)) from error


# ======================================================================================
#                                   COMPILER ADAPTERS
# ======================================================================================


def serialize_reward_machine(reward_machine: RewardMachineStructure) -> str:
    """Serialize compiler states in the shared ARM-FM two-section format."""
    return serialize_paper_reward_machine(compiler_machine_to_paper(reward_machine, ()))


def parse_reward_machine(text: str) -> RewardMachineStructure:
    """Read ARM-FM text, including explicit self-loops and ``else`` fallback rows."""
    machine = parse_paper_reward_machine(text, require_final_states=True)
    if len(machine.final_states) != 1:
        raise ValueError("Compiler Reward Machine imports require exactly one FINAL_STATES entry")
    if machine.initial_state in machine.final_states:
        raise ValueError("Initial and final states must differ")
    return paper_to_structure(machine)


# ======================================================================================
#                                   PARSE AND SERIALIZE
# ======================================================================================


def parse_paper_reward_machine(
    text: str,
    *,
    propositions: Sequence[str] = (),
    final_states: Sequence[str] = (),
    require_final_states: bool = False,
) -> PaperRewardMachine:
    """Parse separate ``TRANSITION_FUNCTION`` and ``REWARD_FUNCTION`` sections."""
    if not isinstance(text, str):
        raise RuntimeValidationError("Reward Machine content must be text")
    sections = _split_sections(text)
    required = {"STATES", "INITIAL_STATE", "TRANSITION_FUNCTION", "REWARD_FUNCTION"}
    missing = required - sections.keys()
    if missing:
        raise RuntimeValidationError(
            f"Reward Machine is missing section(s): {', '.join(sorted(missing))}"
        )
    states = _parse_names(sections["STATES"], "state")
    initial = sections["INITIAL_STATE"].strip()
    if initial not in states:
        raise RuntimeValidationError("Reward Machine initial state is not declared")
    parsed_finals = tuple(final_states) or _parse_names(
        sections.get("FINAL_STATES", sections.get("FINAL_STATE", "")), "final state"
    )
    if require_final_states and ("FINAL_STATES" not in sections or not parsed_finals):
        raise RuntimeValidationError("Reward Machine must declare FINAL_STATES")
    default_reward = _parse_default_reward(sections.get("DEFAULT_REWARD"))
    transitions = _parse_transitions(sections["TRANSITION_FUNCTION"], states)
    rewards = _parse_rewards(sections["REWARD_FUNCTION"])
    return PaperRewardMachine(
        states=states,
        initial_state=initial,
        transitions=_with_rewards(transitions, rewards),
        final_states=parsed_finals,
        propositions=tuple(propositions),
        default_reward=default_reward,
    )


def _parse_transitions(section: str, states: tuple[str, ...]) -> list[RuntimeTransition]:
    transitions: list[RuntimeTransition] = []
    seen: set[tuple[str, str]] = set()
    for line_number, line in _content_lines(section):
        match = _TRANSITION.fullmatch(line)
        if match is None:
            raise RuntimeValidationError(f"Malformed transition on line {line_number}")
        source, condition, destination = (part.strip() for part in match.groups())
        if source not in states or destination not in states:
            raise RuntimeValidationError(
                f"Transition on line {line_number} references an undeclared state"
            )
        key = (source, condition.lower())
        if key in seen:
            raise RuntimeValidationError(f"Duplicate transition on line {line_number}")
        seen.add(key)
        transitions.append(RuntimeTransition(source, condition, destination))
    return transitions


def _parse_rewards(section: str) -> dict[tuple[str, str, str], float]:
    rewards: dict[tuple[str, str, str], float] = {}
    for line_number, line in _content_lines(section):
        match = _REWARD.fullmatch(line)
        if match is None:
            raise RuntimeValidationError(f"Malformed reward on line {line_number}")
        source, condition, destination, raw_reward = (part.strip() for part in match.groups())
        key = (source, condition.lower(), destination)
        if key in rewards:
            raise RuntimeValidationError(f"Duplicate reward on line {line_number}")
        rewards[key] = _finite_reward(raw_reward, line_number)
    return rewards


def _with_rewards(
    transitions: Sequence[RuntimeTransition],
    rewards: Mapping[tuple[str, str, str], float],
) -> tuple[RuntimeTransition, ...]:
    """Attach each reward row to its transition; a reward without a transition is an error."""
    transition_keys = {
        (item.source, item.condition.lower(), item.destination) for item in transitions
    }
    unknown_rewards = set(rewards) - transition_keys
    if unknown_rewards:
        source, condition, destination = sorted(unknown_rewards)[0]
        raise RuntimeValidationError(
            f"Reward refers to nonexistent transition ({source}, {condition}, {destination})"
        )
    return tuple(
        RuntimeTransition(
            item.source,
            item.condition,
            item.destination,
            rewards.get((item.source, item.condition.lower(), item.destination), 0.0),
        )
        for item in transitions
    )


def _state_order(name: str) -> tuple[int, int, str]:
    """Order ``u<N>`` states numerically, keeping other names last and alphabetical."""
    match = _STATE_NUMBER.fullmatch(name)
    if match is None:
        return (1, 0, name)
    return (0, int(match.group(1)), name)


def _ordered_states(machine: PaperRewardMachine) -> tuple[str, ...]:
    """Sort the declared states so the ``STATES`` header reads ``u0, u1, u2, …``."""
    return tuple(sorted(machine.states, key=_state_order))


def _transitions_by_source(
    machine: PaperRewardMachine,
    states: tuple[str, ...],
) -> tuple[RuntimeTransition, ...]:
    """Group transitions under their source state, in ``states`` order."""
    position = {name: index for index, name in enumerate(states)}
    return tuple(
        sorted(
            machine.transitions,
            key=lambda item: position.get(item.source, len(position)),
        )
    )


def serialize_paper_reward_machine(machine: PaperRewardMachine) -> str:
    """Serialize a paper-style RM, retaining zero-reward state-changing edges."""
    states = _ordered_states(machine)
    transitions = _transitions_by_source(machine, states)
    lines = [
        "REWARD_MACHINE:",
        f"STATES: {', '.join(states)}",
        f"INITIAL_STATE: {machine.initial_state}",
    ]
    if machine.final_states:
        lines.append(f"FINAL_STATES: {', '.join(machine.final_states)}")
    if machine.default_reward is not None:
        lines.append(f"DEFAULT_REWARD: {_format_reward(machine.default_reward)}")
    lines.append("TRANSITION_FUNCTION:")
    lines.extend(f"({item.source}, {item.condition}) -> {item.destination}" for item in transitions)
    lines.append("REWARD_FUNCTION:")
    lines.extend(
        f"({item.source}, {item.condition}, {item.destination}) -> {_format_reward(item.reward)}"
        for item in transitions
        if item.reward != 0
    )
    return "\n".join(lines) + "\n"


def compiler_machine_to_paper(
    reward_machine: object,
    propositions: Sequence[str],
) -> PaperRewardMachine:
    """Adapt the existing numeric compiler result without rebuilding its topology."""
    states = tuple(reward_machine.states)
    state_names = {state: f"u{index}" for index, state in enumerate(states)}
    transitions = []
    for item in reward_machine.transitions:
        condition = " & ".join(item.condition) if item.condition else "true"
        transitions.append(
            RuntimeTransition(
                state_names[item.source],
                condition,
                state_names[item.destination],
                float(item.reward),
            )
        )
    return PaperRewardMachine(
        states=tuple(state_names[state] for state in states),
        initial_state=state_names[reward_machine.initial_state],
        transitions=tuple(transitions),
        final_states=(state_names[reward_machine.final_state],),
        propositions=tuple(propositions),
        default_reward=0.0,
    )


def paper_to_structure(machine: PaperRewardMachine) -> RewardMachineStructure:
    """Convert a parsed paper Reward Machine into the compiler's numeric structure."""
    if len(machine.final_states) != 1:
        raise ValueError("The graph renderer needs exactly one FINAL_STATES entry")

    names = list(machine.states)
    index = {name: position for position, name in enumerate(names)}
    final_state = index[machine.final_states[0]]
    transitions = tuple(
        Transition(
            index[transition.source],
            index[transition.destination],
            (transition.condition,),
            transition.reward,
        )
        for transition in machine.transitions
    )
    edges = ((transition.source, transition.destination) for transition in transitions)
    return RewardMachineStructure(
        states=tuple(range(len(names))),
        initial_state=index[machine.initial_state],
        final_state=final_state,
        rejecting_states=tuple(
            sorted(states_without_path_to_final(range(len(names)), edges, final_state))
        ),
        transitions=transitions,
    )


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith(":") and line[:-1].strip().replace(" ", "_").isidentifier():
            name = line[:-1].strip().replace(" ", "_").upper()
            if name in {"REWARD_MACHINE", "REWARD_FUNCTION", "TRANSITION_FUNCTION"}:
                current = name
                sections.setdefault(name, [])
                continue
        if current is None:
            match = _HEADER_LINE.fullmatch(line)
            if match:
                sections[match.group(1)] = [match.group(2)]
            continue
        header = _HEADER_LINE.fullmatch(line)
        if header and header.group(1) in {
            "STATES",
            "INITIAL_STATE",
            "FINAL_STATE",
            "FINAL_STATES",
            "DEFAULT_REWARD",
        }:
            sections[header.group(1)] = [header.group(2)]
        else:
            sections[current].append(f"{line_number}:{line}")
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _content_lines(content: str):
    for line in content.splitlines():
        if ":" in line and line.split(":", 1)[0].isdigit():
            line_number, value = line.split(":", 1)
            yield int(line_number), value.strip()


def _parse_names(value: str, description: str) -> tuple[str, ...]:
    if not value:
        return ()
    names = tuple(item.strip() for item in value.split(",") if item.strip())
    if not names or len(names) != len(set(names)):
        raise RuntimeValidationError(f"{description.title()} list must be nonempty and unique")
    return names


def _finite_reward(value: str, line_number: int) -> float:
    try:
        reward = float(value)
    except ValueError as error:
        raise RuntimeValidationError(f"Invalid reward on line {line_number}") from error
    if not math.isfinite(reward):
        raise RuntimeValidationError(f"Reward on line {line_number} must be finite")
    return reward


def _parse_default_reward(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        reward = float(value.strip())
    except ValueError as error:
        raise RuntimeValidationError("Invalid DEFAULT_REWARD header") from error
    if not math.isfinite(reward) or reward != 0:
        raise RuntimeValidationError("DEFAULT_REWARD must be 0")
    return reward


def _guard_propositions(transitions: Sequence[RuntimeTransition]) -> tuple[str, ...]:
    names: list[str] = []
    for transition in transitions:
        if transition.is_else:
            continue
        for name in _IDENTIFIER.findall(transition.condition.lower()):
            if name not in {"true", "false"} and name not in names:
                names.append(name)
    return tuple(names)


def _format_reward(value: float) -> str:
    return "0" if value == 0 else f"{value:g}"
