"""Inferred task-clause priorities and reward-shaping policy."""

from enum import StrEnum


class PriorityLevel(StrEnum):
    """Supported ordering-priority levels."""

    NONE = "none"
    SOFT = "soft"
    HARD = "hard"

MAX_TASK_CLAUSES = 10
CLAUSE_COMPLETION_REWARD = 0.1
TASK_COMPLETION_REWARD = 1.0


def describe_reward_behavior(pattern: str, priority: PriorityLevel) -> str:
    """Describe the effective one-time reward behavior."""
    if pattern == "Existence":
        return "first required occurrence: +0.10 once"
    if pattern == "ExistenceTwo":
        return "second required occurrence: +0.10 once"
    if priority is PriorityLevel.HARD:
        return "preferred: +0.10 once; reverse/simultaneous: reject"
    return "preferred: +0.10 once; reverse/simultaneous: 0.00"
