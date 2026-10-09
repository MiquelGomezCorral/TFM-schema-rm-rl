"""Gymnasium environments for training: per-family adapters and the Reward Machine wrapper.

An adapter owns everything environment-specific (observation pipeline, image encoder,
success rule), so the DQN loop stays environment-agnostic. MiniGrid is the only family.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

import gymnasium as gym
import minigrid  # importing registers the MiniGrid and BabyAI gym ids
import numpy as np
from gymnasium import spaces
from gymnasium.wrappers import FrameStackObservation, GrayscaleObservation
from minigrid.wrappers import ImgObsWrapper, RGBImgPartialObsWrapper
from torch import Tensor, nn

from src.compiler import RuntimeValidationError
from src.config import Configuration

from .artifacts import ArtifactBundle, load_bundle
from .runtime import RewardMachineEnvironment, RewardMachineRuntime, load_labeling_functions


@dataclass(frozen=True)
class RunEnvironment:
    """One training or evaluation environment with its family's encoder and success rule.

    ``make_encoder()`` returns a module mapping a batch of image observations to flat
    features. ``is_success(terminated, env_reward)`` decides whether an episode exited.
    """

    env: gym.Env
    make_encoder: Callable[[], nn.Module]
    is_success: Callable[[bool, float], bool]


def make_environment(environment_id: str, **kwargs: Any) -> Any:
    """Create one registered Gymnasium environment by its id."""
    return gym.make(environment_id, **kwargs)


def make_run_environment(CONFIG: Configuration) -> RunEnvironment:
    """Build a fresh run environment from ``CONFIG``, wrapped with the RM when ``use_rm``.

    Every call owns its own RM runtime and labeling memory, so train and eval
    environments never share RM state.

    Raises:
        ValueError: If the family, observation, gym id or RM inputs are missing or unknown.
    """
    if not CONFIG.gym_id:
        raise ValueError("train-rl needs gym_id in the run config")
    adapter = ENVIRONMENT_FAMILIES.get(CONFIG.env_family)
    if adapter is None:
        raise ValueError(
            f"Unknown env_family {CONFIG.env_family!r}; supported: {', '.join(ENVIRONMENT_FAMILIES)}"
        )

    run = adapter(CONFIG)
    if not CONFIG.use_rm:
        return run
    bundle, labeling = _reward_machine_inputs(CONFIG)
    return replace(run, env=RewardMachineObservation(run.env, bundle, labeling))


def minigrid_labeling_api() -> str:
    """Return the API contract used in generated MiniGrid predicates."""
    return (
        "env.grid.get(x, y), env.agent_pos, env.carrying, env.width, env.height; "
        "objects expose type, color, is_open, and is_locked"
    )


# ======================================================================================
#                                   MINIGRID ADAPTER
# ======================================================================================


class MiniGridCNN(nn.Module):
    """Small CNN over the symbolic 7x7x3 MiniGrid view (HWC uint8)."""

    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(3, 16, 2),
            nn.ReLU(),
            nn.Conv2d(16, 32, 2),
            nn.ReLU(),
            nn.Conv2d(32, 64, 2),
            nn.ReLU(),
            nn.Flatten(),
        )

    def forward(self, image: Tensor) -> Tensor:
        return self.network(image.permute(0, 3, 1, 2).float())


class NatureCNN(nn.Module):
    """Nature DQN encoder over 4 stacked 84x84 grayscale frames, as in CleanRL dqn_atari."""

    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(4, 32, 8, stride=4),
            nn.ReLU(),
            nn.Conv2d(32, 64, 4, stride=2),
            nn.ReLU(),
            nn.Conv2d(64, 64, 3, stride=1),
            nn.ReLU(),
            nn.Flatten(),
        )

    def forward(self, image: Tensor) -> Tensor:
        return self.network(image.float() / 255.0)


def minigrid_environment(CONFIG: Configuration) -> RunEnvironment:
    """Build a MiniGrid env with the ``symbolic`` or ``pixels`` observation pipeline."""
    env = make_environment(CONFIG.gym_id)
    if CONFIG.observation == "symbolic":
        return RunEnvironment(ImgObsWrapper(env), MiniGridCNN, minigrid_success)
    if CONFIG.observation == "pixels":
        # 7 tiles x 12 px = 84 px, so no ResizeObservation (it needs cv2).
        image = ImgObsWrapper(RGBImgPartialObsWrapper(env, tile_size=12))
        frames = FrameStackObservation(GrayscaleObservation(image), 4)
        return RunEnvironment(frames, NatureCNN, minigrid_success)
    raise ValueError(f"Unknown MiniGrid observation {CONFIG.observation!r}; use symbolic or pixels")


def minigrid_success(terminated: bool, env_reward: float) -> bool:
    """MiniGrid pays a positive reward only when it terminates on the mission."""
    return terminated and env_reward > 0


ENVIRONMENT_FAMILIES: dict[str, Callable[[Configuration], RunEnvironment]] = {
    "minigrid": minigrid_environment,
}


# ======================================================================================
#                                 REWARD MACHINE WRAPPER
# ======================================================================================


class RewardMachineObservation(gym.Wrapper):
    """Add the RM state embedding to observations and the RM fields to ``info``.

    ``RewardMachineEnvironment`` is not a ``gym.Env`` (``gym.Wrapper`` would reject it), so
    this wrapper composes one over the preprocessed env and delegates reset and step to it:
    one RM update per step, reward = env + RM, RM reset on env reset. Observations are
    ``{"image": obs, "rm_embedding": phi(u)}`` with phi(u_I) after reset. ``info`` gains
    ``env_reward``, ``rm_reward``, ``rm_state`` and ``rm_accept`` (state is final).
    """

    def __init__(
        self,
        env: gym.Env,
        bundle: ArtifactBundle,
        labeling: Mapping[str, Callable[[object], bool]],
    ) -> None:
        super().__init__(env)
        machine = bundle.reward_machine
        self.reward_machine = RewardMachineEnvironment(env, RewardMachineRuntime(machine), labeling)
        self.final_states = frozenset(machine.final_states)
        self.embeddings = {
            state: np.asarray(vector, dtype=np.float32)
            for state, vector in bundle.embeddings.items()
        }

        # Embedding values are negative too, so the space is unbounded.
        dimension = len(self.embeddings[machine.initial_state])
        self.observation_space = spaces.Dict(
            {
                "image": env.observation_space,
                "rm_embedding": spaces.Box(-np.inf, np.inf, (dimension,), np.float32),
            }
        )

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        observation, info = self.reward_machine.reset(seed=seed, options=options)
        state = self.reward_machine.runtime.state
        info = {**info, "rm_state": state, "rm_accept": state in self.final_states}
        return self._observation(observation, state), info

    def step(self, action):
        observation, reward, terminated, truncated, info = self.reward_machine.step(action)
        state = info["rm_state"]
        # RewardMachineEnvironment returns only the sum, so this can differ by one ulp.
        info["env_reward"] = reward - info["rm_reward"]
        info["rm_accept"] = state in self.final_states
        return self._observation(observation, state), reward, terminated, truncated, info

    def _observation(self, image: np.ndarray, state: str) -> dict[str, np.ndarray]:
        return {"image": image, "rm_embedding": self.embeddings[state]}


def _reward_machine_inputs(
    CONFIG: Configuration,
) -> tuple[ArtifactBundle, dict[str, Callable[[object], bool]]]:
    """Load the RM bundle and its labeling, optionally from ``labeling_bundle``.

    The RM, state descriptions and embeddings always come from ``bundle``.
    """
    if CONFIG.bundle is None:
        raise ValueError("use_rm needs a bundle in the run config")
    bundle = load_bundle(CONFIG.bundle)
    bundle.validate(require_complete=True)

    labeling_bundle = CONFIG.labeling_bundle or CONFIG.bundle
    source = (labeling_bundle / "labeling.py").read_text(encoding="utf-8")
    try:
        labeling = load_labeling_functions(source, bundle.reward_machine.propositions)
    except RuntimeValidationError as error:
        raise ValueError(
            f"Labeling from {labeling_bundle} does not match the propositions of "
            f"{CONFIG.bundle}: {error}"
        ) from error
    return bundle, labeling
