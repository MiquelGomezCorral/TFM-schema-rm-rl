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
