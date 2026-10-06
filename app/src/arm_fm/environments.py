"""Generic Gymnasium environment creation and the MiniGrid labeling API."""

from typing import Any

import gymnasium as gym
import minigrid  # importing registers the MiniGrid and BabyAI gym ids


def make_environment(environment_id: str, **kwargs: Any) -> Any:
    """Create one registered Gymnasium environment by its id."""
    return gym.make(environment_id, **kwargs)


def minigrid_labeling_api() -> str:
    """Return the API contract used in generated MiniGrid predicates."""
    return (
        "env.grid.get(x, y), env.agent_pos, env.carrying, env.width, env.height; "
        "objects expose type, color, is_open, and is_locked"
    )
