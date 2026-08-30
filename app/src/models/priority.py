"""Priority levels and their executable completion-reward policy."""

from dataclasses import dataclass
from enum import StrEnum


class PriorityLevel(StrEnum):
    """Supported ordering-priority levels."""

    NONE = "none"
    SOFT = "soft"
    MEDIUM = "medium"
    STRONG = "strong"
    HARD = "hard"

PRIORITY_CHOICES = ["infer", *(priority.value for priority in PriorityLevel)]


@dataclass(frozen=True)
class CompletionRewards:
    """Rewards, or rejection, for the ways an ordering can complete."""

    preferred: float
    reverse: float | None
    simultaneous: float | None


_COMPLETION_REWARDS = {
    PriorityLevel.NONE: CompletionRewards(1.00, 1.00, 1.00),
    PriorityLevel.SOFT: CompletionRewards(1.25, 0.75, 1.00),
    PriorityLevel.MEDIUM: CompletionRewards(1.50, 0.50, 1.00),
    PriorityLevel.STRONG: CompletionRewards(1.75, 0.25, 1.00),
    PriorityLevel.HARD: CompletionRewards(1.00, None, None),
}


def completion_rewards(priority: PriorityLevel) -> CompletionRewards:
    """Return the authoritative completion policy for one priority."""
    return _COMPLETION_REWARDS[priority]


def describe_reward_behavior(pattern: str, priority: PriorityLevel) -> str:
    """Describe the effective one-time reward behavior shown for approval."""
    if pattern == "Existence":
        return "first required occurrence: 1.00; later occurrences: 0.00"
    if pattern == "ExistenceTwo":
        return "second required occurrence: 1.00; later occurrences: 0.00"

    rewards = completion_rewards(priority)
    if priority is PriorityLevel.HARD:
        return "preferred: 1.00; reverse: reject; simultaneous: reject"
    return (
        f"preferred: {rewards.preferred:.2f}; reverse: {rewards.reverse:.2f}; "
        f"simultaneous: {rewards.simultaneous:.2f}"
    )
