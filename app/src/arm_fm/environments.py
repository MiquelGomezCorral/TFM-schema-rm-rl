"""Gymnasium environments for training: per-family adapters and the Reward Machine wrapper.

An adapter owns everything environment-specific (observation pipeline, image encoder,
success rule), so the training loops stay environment-agnostic. Families: MiniGrid and Craftium.
"""

import copy
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import gymnasium as gym
import minigrid  # importing registers the MiniGrid and BabyAI gym ids
import numpy as np
import torch
from gymnasium import spaces
from gymnasium.wrappers import FrameStackObservation, GrayscaleObservation, ResizeObservation
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


def terminated_with_reward(terminated: bool, env_reward: float) -> bool:
    """Success rule of the MiniGrid and Craftium families.

    Both pay a positive reward only when the episode terminates on its goal.
    """
    return terminated and env_reward > 0


def make_environment(environment_id: str, **kwargs: Any) -> Any:
    """Create one registered Gymnasium environment by its id."""
    return gym.make(environment_id, **kwargs)


def make_run_environment(CONFIG: Configuration) -> RunEnvironment:
    """Build a fresh run environment from ``CONFIG``, wrapped with the RM when ``use_rm``.

    Every call owns its own RM runtime and labeling memory, so train and eval
    environments never share RM state.

    With ``task_bundles`` it builds one such environment per task and returns them as one
    ``MultiTaskEnvironment``. With ``success: rm`` an episode ends on RM acceptance.

    Raises:
        ValueError: If the family, observation, gym id or RM inputs are missing or unknown.
    """
    if CONFIG.task_bundles:
        return _multi_task_run(CONFIG)
    if not CONFIG.gym_id:
        raise ValueError("train-rl needs gym_id in the run config")
    adapter = ENVIRONMENT_FAMILIES.get(CONFIG.env_family)
    if adapter is None:
        raise ValueError(
            f"Unknown env_family {CONFIG.env_family!r}; supported: {', '.join(ENVIRONMENT_FAMILIES)}"
        )

    # Load the RM first so a bad bundle fails before an engine or env exists.
    rm_inputs = _reward_machine_inputs(CONFIG) if CONFIG.use_rm else None
    run = adapter(CONFIG)
    if rm_inputs is None:
        if CONFIG.success == "rm":
            raise ValueError("success: rm needs use_rm: true")
        return run
    try:
        env = RewardMachineObservation(run.env, *rm_inputs)
    except Exception:
        run.env.close()
        raise
    if CONFIG.success == "rm":
        env = RMAcceptanceTermination(env)
        return replace(run, env=env, is_success=env.is_success)
    return replace(run, env=env)


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
    env = make_environment(CONFIG.gym_id, **CONFIG.env_kwargs)
    if CONFIG.observation == "symbolic":
        return RunEnvironment(ImgObsWrapper(env), MiniGridCNN, terminated_with_reward)
    if CONFIG.observation == "pixels":
        # The authors' pipeline: 56 px render (7 tiles x 8 px), resized to 84 px with OpenCV.
        image = ResizeObservation(ImgObsWrapper(RGBImgPartialObsWrapper(env)), (84, 84))
        frames = FrameStackObservation(GrayscaleObservation(image), 4)
        return RunEnvironment(frames, NatureCNN, terminated_with_reward)
    raise ValueError(f"Unknown MiniGrid observation {CONFIG.observation!r}; use symbolic or pixels")


# ======================================================================================
#                                   CRAFTIUM ADAPTER
# ======================================================================================


class AreaResizeObservation(gym.ObservationWrapper):
    """Shrink 2-D uint8 frames to ``shape`` (height, width) by area averaging, without OpenCV."""

    def __init__(self, env: gym.Env, shape: tuple[int, int]) -> None:
        super().__init__(env)
        self.shape = shape
        self.observation_space = spaces.Box(0, 255, shape, np.uint8)

    def observation(self, observation: np.ndarray) -> np.ndarray:
        frame = torch.from_numpy(observation)[None, None].float()
        return nn.functional.adaptive_avg_pool2d(frame, self.shape)[0, 0].round().byte().numpy()


def craftium_environment(CONFIG: Configuration) -> RunEnvironment:
    """Build a Craftium env: Discrete actions, 84x84 grayscale frames, 4 stacked (CleanRL Atari).

    The registered Craftium id already returns grayscale frames and a Discrete action space;
    its ``inventory`` and ``milestones`` are read by the labeling functions.
    """
    env = make_environment(CONFIG.gym_id, **CONFIG.env_kwargs)
    return RunEnvironment(
        FrameStackObservation(AreaResizeObservation(env, (84, 84)), 4),
        NatureCNN,
        terminated_with_reward,
    )


ENVIRONMENT_FAMILIES: dict[str, Callable[[Configuration], RunEnvironment]] = {
    "minigrid": minigrid_environment,
    "craftium": craftium_environment,
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


class RMAcceptanceTermination(gym.Wrapper):
    """End an episode when the RM reaches a final state (config ``success: rm``).

    For missions the environment cannot judge. It adds no reward: the episode just ends, and
    ``is_success`` counts an exit only when the episode ended on RM acceptance. Wrap it
    directly around ``RewardMachineObservation``, whose ``info["rm_accept"]`` it reads.
    """

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)
        self.accepted = False

    def step(self, action):
        observation, reward, terminated, truncated, info = self.env.step(action)
        self.accepted = info["rm_accept"]
        return observation, reward, terminated or self.accepted, truncated, info

    def is_success(self, terminated: bool, _env_reward: float) -> bool:
        return terminated and self.accepted


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
    source = bundle.labeling_source
    if CONFIG.labeling_bundle is not None:
        source = (CONFIG.labeling_bundle / "labeling.py").read_text(encoding="utf-8")
    try:
        labeling = load_labeling_functions(source, bundle.reward_machine.propositions)
    except RuntimeValidationError as error:
        raise ValueError(
            f"Labeling from {labeling_bundle} does not match the propositions of "
            f"{CONFIG.bundle}: {error}"
        ) from error
    return bundle, labeling


# ======================================================================================
#                                      MULTI-TASK
# ======================================================================================


def task_name(entry: Mapping[str, Any]) -> str:
    """A ``task_bundles`` entry is named after its bundle folder."""
    return Path(entry["bundle"]).name


class MultiTaskEnvironment(gym.Env):
    """Several task environments behind one env; every training episode draws one task.

    Each task keeps its own env, RM, labeling, embeddings and success rule, so the policy
    sees only the shared observation. ``reset`` draws the task from a RNG of its own, seeded
    from the run seed, unless ``options={"task": index}`` names one (evaluation cycles them).
    ``info["task"]`` carries the current task's name.
    """

    def __init__(self, runs: Mapping[str, RunEnvironment], seed: int) -> None:
        self.names = tuple(runs)
        self.runs = tuple(runs.values())
        first = self.runs[0].env
        for name, run in runs.items():
            if (
                run.env.observation_space != first.observation_space
                or run.env.action_space != first.action_space
            ):
                raise ValueError(
                    f"Task {name!r} differs from {self.names[0]!r} in observation space, "
                    "action space or RM embedding dimension; tasks in one run must match"
                )
        self.observation_space = first.observation_space
        self.action_space = first.action_space
        self._seed = seed
        self._task_rng = random.Random(f"tasks-{seed}")
        self._started: set[int] = set()
        self._index = 0

    @property
    def current_task(self) -> str:
        return self.names[self._index]

    @property
    def unwrapped(self):
        """The current task's own environment, so grid state stays readable."""
        return self.runs[self._index].env.unwrapped

    def is_success(self, terminated: bool, env_reward: float) -> bool:
        return self.runs[self._index].is_success(terminated, env_reward)

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        task = (options or {}).get("task")
        self._index = self._task_rng.randrange(len(self.runs)) if task is None else task
        # A task's first reset needs a seed, or its layouts would not be reproducible.
        if seed is None and self._index not in self._started:
            seed = self._seed + self._index
        self._started.add(self._index)
        observation, info = self.runs[self._index].env.reset(seed=seed)
        return observation, {**info, "task": self.current_task}

    def step(self, action):
        observation, reward, terminated, truncated, info = self.runs[self._index].env.step(action)
        return observation, reward, terminated, truncated, {**info, "task": self.current_task}


def _multi_task_run(CONFIG: Configuration) -> RunEnvironment:
    """One ``MultiTaskEnvironment`` over ``CONFIG.task_bundles``, each built like a single task."""
    names = [task_name(entry) for entry in CONFIG.task_bundles]
    if len(set(names)) != len(names):
        raise ValueError(f"task_bundles need distinct bundle folder names, got {names}")
    runs = {
        name: make_run_environment(_task_config(CONFIG, entry))
        for name, entry in zip(names, CONFIG.task_bundles, strict=True)
    }
    env = MultiTaskEnvironment(runs, CONFIG.seed)
    return RunEnvironment(env, runs[names[0]].make_encoder, env.is_success)


def _task_config(CONFIG: Configuration, entry: Mapping[str, Any]) -> Configuration:
    """A copy of ``CONFIG`` that runs one ``task_bundles`` entry as a single task.

    The entry's ``env_kwargs`` extend the run's. ``labeling_bundle`` and ``success`` belong to
    the entry alone, with ``success`` falling back to the run's.
    """
    task = copy.copy(CONFIG)  # replace() would reload the YAML over these values
    task.bundle = entry["bundle"]
    task.labeling_bundle = entry.get("labeling_bundle")
    task.env_kwargs = {**CONFIG.env_kwargs, **entry.get("env_kwargs", {})}
    task.success = entry.get("success", CONFIG.success)
    task.task_bundles = []
    return task
