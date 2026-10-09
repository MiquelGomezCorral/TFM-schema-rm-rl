"""DQN training with optional Reward Machine conditioning (ARM-FM Alg. 1, Table 5).

Adapted from CleanRL ``cleanrl/dqn_atari.py`` at commit
004f8a086a892a2a180f4dd332b90d83a968aa7a:
https://github.com/vwxyzjn/cleanrl/blob/004f8a086a892a2a180f4dd332b90d83a968aa7a/cleanrl/dqn_atari.py

Kept: ``linear_schedule``, the epsilon-greedy action, the MSE TD update and the target copy.
Changed: one non-vector env with manual resets, SB3 replay buffers storing
``done = terminated``, an optional RM-embedding branch in the Q-network, periodic greedy
evaluation, and CSV/JSON run metrics. Removed: tyro, vector envs, Atari wrappers,
wandb/Hugging Face upload and TensorBoard.

MIT License

Copyright (c) 2019 CleanRL developers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import csv
import itertools
import json
import os
import random
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
import yaml
from gymnasium import spaces
from stable_baselines3.common.buffers import DictReplayBuffer, ReplayBuffer
from stable_baselines3.common.utils import set_random_seed
from torch import Tensor, nn, optim

from src.config import Configuration

from .environments import RunEnvironment, make_run_environment

LAYOUTS = ("fixed", "procedural")
POSITIVE_SETTINGS = (
    "total_timesteps",
    "batch_size",
    "train_frequency",
    "target_network_frequency",
    "exploration_fraction",
    "eval_frequency",
    "eval_episodes",
    "final_eval_episodes",
)
TRAIN_LOG_EVERY_UPDATES = 100

# The Configuration fields recorded in a run's config.yaml.
RUN_SETTINGS = (
    "yaml_config_name",
    "exp_name",
    "seed",
    "gym_id",
    "env_family",
    "observation",
    "layout",
    "layout_seed",
    "use_rm",
    "bundle",
    "labeling_bundle",
    "total_timesteps",
    "learning_rate",
    "buffer_size",
    "gamma",
    "tau",
    "target_network_frequency",
    "batch_size",
    "start_e",
    "end_e",
    "exploration_fraction",
    "learning_starts",
    "train_frequency",
    "eval_frequency",
    "eval_episodes",
    "final_eval_episodes",
    "eval_epsilon",
    "eval_seed_base",
    "success_threshold",
    "cuda",
    "torch_deterministic",
)

EPISODE_COLUMNS = (
    "global_step",
    "episode",
    "env_return",
    "rm_return",
    "total_return",
    "length",
    "exited",
    "final_rm_state",
    "epsilon",
    "wall_seconds",
)
EVAL_COLUMNS = (
    "global_step",
    "episodes",
    "exit_rate",
    "mean_length",
    "mean_env_return",
    "mean_rm_return",
    "mean_total_return",
    "rm_accept_rate",
    "accept_exit_agreement",
    "seeds",
)
TRAIN_COLUMNS = ("global_step", "td_loss", "q_mean", "epsilon", "sps")


# ======================================================================================
#                                      PUBLIC API
# ======================================================================================


def train_dqn(CONFIG: Configuration) -> Path:
    """Train one DQN run and write its run folder under ``outputs/runs/<exp_name>/``.

    Every logged ``global_step`` counts training env steps taken so far; evaluation steps
    run on a separate env with their own RNG and never count. The final evaluation scores
    the final policy and is the last ``eval.csv`` row, at ``total_timesteps``.

    Returns:
        Path: The run folder.

    Raises:
        ValueError: If the run config is invalid or the action space is not ``Discrete``.
    """
    _check_settings(CONFIG)
    set_random_seed(CONFIG.seed)
    torch.backends.cudnn.deterministic = CONFIG.torch_deterministic
    device = torch.device("cuda" if torch.cuda.is_available() and CONFIG.cuda else "cpu")

    train_run = make_run_environment(CONFIG)
    eval_run = make_run_environment(CONFIG)
    if not isinstance(train_run.env.action_space, spaces.Discrete):
        raise ValueError(
            f"train-rl DQN needs a Discrete action space; {CONFIG.gym_id} has "
            f"{train_run.env.action_space}"
        )
    train_run.env.action_space.seed(CONFIG.seed)
    eval_run.env.action_space.seed(CONFIG.seed)

    learner = DQNLearner.create(CONFIG, train_run, device)
    recorder = RunRecorder.create(CONFIG, device)
    _train(CONFIG, train_run, eval_run, learner, recorder)

    final_eval = evaluate(CONFIG, eval_run, learner.q_network, CONFIG.final_eval_episodes)
    recorder.write_evaluation(CONFIG.total_timesteps, final_eval, CONFIG.success_threshold)
    recorder.write_summary(CONFIG, learner, final_eval)
    torch.save(learner.q_network.state_dict(), recorder.directory / "q_network.pt")
    print(f"run folder {recorder.directory}")
    return recorder.directory


def _check_settings(CONFIG: Configuration) -> None:
    """Reject settings that would crash mid-run, before the run folder exists."""
    if CONFIG.layout not in LAYOUTS:
        raise ValueError(f"Unknown layout {CONFIG.layout!r}; use one of {', '.join(LAYOUTS)}")
    not_positive = [name for name in POSITIVE_SETTINGS if getattr(CONFIG, name) <= 0]
    if not_positive:
        raise ValueError(f"These run settings must be positive: {', '.join(not_positive)}")
    if CONFIG.learning_starts < 0:
        raise ValueError("learning_starts must not be negative")


def linear_schedule(start_e: float, end_e: float, duration: float, t: int) -> float:
    """Epsilon decays linearly from ``start_e`` to ``end_e`` over ``duration`` steps."""
    slope = (end_e - start_e) / duration
    return max(slope * t + start_e, end_e)


# ======================================================================================
#                                      Q-NETWORK
# ======================================================================================


class QNetwork(nn.Module):
    """Encoder features, plus an RM-embedding MLP (d -> d/4 -> d/4) for Dict observations.

    The concatenated features feed Linear 512 -> ReLU -> |A|. A Box observation space
    (``use_rm: false``) has no embedding branch.
    """

    def __init__(
        self, encoder: nn.Module, observation_space: spaces.Space, action_count: int
    ) -> None:
        super().__init__()
        self.encoder = encoder
        self.rm_embedding: nn.Module | None = None
        image_space = observation_space
        if isinstance(observation_space, spaces.Dict):
            image_space = observation_space["image"]
            dimension = observation_space["rm_embedding"].shape[0]
            self.rm_embedding = nn.Sequential(
                nn.Linear(dimension, dimension // 4),
                nn.ReLU(),
                nn.Linear(dimension // 4, dimension // 4),
                nn.ReLU(),
            )

        with torch.no_grad():
            feature_count = encoder(torch.zeros((1, *image_space.shape))).shape[1]
        if self.rm_embedding is not None:
            feature_count += observation_space["rm_embedding"].shape[0] // 4
        self.head = nn.Sequential(
            nn.Linear(feature_count, 512),
            nn.ReLU(),
            nn.Linear(512, action_count),
        )

    def forward(self, observations: Tensor | dict[str, Tensor]) -> Tensor:
        if self.rm_embedding is None:
            return self.head(self.encoder(observations))
        features = torch.cat(
            [
                self.encoder(observations["image"]),
                self.rm_embedding(observations["rm_embedding"]),
            ],
            dim=1,
        )
        return self.head(features)


def select_action(
    q_network: QNetwork,
    observation: np.ndarray | dict[str, np.ndarray],
    epsilon: float,
    action_space: spaces.Discrete,
    rng: random.Random,
) -> int:
    """Epsilon-greedy action for one observation; ``rng`` is drawn only when epsilon > 0."""
    if epsilon > 0 and rng.random() < epsilon:
        return int(action_space.sample())
    device = next(q_network.parameters()).device
    if isinstance(observation, dict):
        batch = {
            key: torch.as_tensor(value, device=device)[None] for key, value in observation.items()
        }
    else:
        batch = torch.as_tensor(observation, device=device)[None]
    with torch.no_grad():
        return int(q_network(batch).argmax(dim=1).item())


# ======================================================================================
#                                 REPLAY AND UPDATES
# ======================================================================================


def create_replay_buffer(CONFIG: Configuration, env: gym.Env, device: torch.device) -> ReplayBuffer:
    """SB3 replay sized ``min(buffer_size, total_timesteps)``; Dict observations use the Dict buffer."""
    buffer_class = (
        DictReplayBuffer if isinstance(env.observation_space, spaces.Dict) else ReplayBuffer
    )
    return buffer_class(
        min(CONFIG.buffer_size, CONFIG.total_timesteps),
        env.observation_space,
        env.action_space,
        device=device,
        n_envs=1,
        optimize_memory_usage=False,
        handle_timeout_termination=False,
    )


def store_transition(
    buffer: ReplayBuffer,
    observation: np.ndarray | dict[str, np.ndarray],
    action: int,
    step: tuple,
) -> None:
    """Store one ``env.step`` result with ``done = terminated``.

    A truncated episode is not terminal, and ``next_obs`` is the real final observation
    (with the RM, it carries phi(u_{t+1})).
    """
    next_observation, reward, terminated, _truncated, info = step
    buffer.add(
        observation,
        next_observation,
        np.array([action]),
        np.array([reward]),
        np.array([terminated]),
        [info],
    )


@dataclass
class DQNLearner:
    """Online and target Q-networks, their optimizer, the replay buffer and update counts."""

    q_network: QNetwork
    target_network: QNetwork
    optimizer: optim.Optimizer
    buffer: ReplayBuffer
    initial_parameters: Tensor
    gradient_updates: int = 0
    target_syncs: int = 0

    @classmethod
    def create(cls, CONFIG: Configuration, run: RunEnvironment, device: torch.device) -> DQNLearner:
        space, action_count = run.env.observation_space, int(run.env.action_space.n)
        q_network = QNetwork(run.make_encoder(), space, action_count).to(device)
        target_network = QNetwork(run.make_encoder(), space, action_count).to(device)
        target_network.load_state_dict(q_network.state_dict())
        return cls(
            q_network,
            target_network,
            optim.Adam(q_network.parameters(), lr=CONFIG.learning_rate),
            create_replay_buffer(CONFIG, run.env, device),
            nn.utils.parameters_to_vector(q_network.parameters()).detach().clone(),
        )

    def update(self, CONFIG: Configuration, global_step: int) -> tuple[float, float] | None:
        """Run CleanRL's update schedule for one step index.

        Returns:
            tuple[float, float] | None: ``(td_loss, q_mean)`` every
            ``TRAIN_LOG_EVERY_UPDATES`` gradient updates, otherwise None.
        """
        if global_step <= CONFIG.learning_starts:
            return None
        metrics = None
        if global_step % CONFIG.train_frequency == 0:
            metrics = self._gradient_step(CONFIG)
        if global_step % CONFIG.target_network_frequency == 0:
            self._sync_target(CONFIG.tau)
        return metrics

    def parameter_change_norm(self) -> float:
        final = nn.utils.parameters_to_vector(self.q_network.parameters()).detach()
        return float(torch.linalg.vector_norm(final - self.initial_parameters))

    def _gradient_step(self, CONFIG: Configuration) -> tuple[float, float] | None:
        data = self.buffer.sample(CONFIG.batch_size)
        with torch.no_grad():
            target_max, _ = self.target_network(data.next_observations).max(dim=1)
            td_target = data.rewards.flatten() + CONFIG.gamma * target_max * (
                1 - data.dones.flatten()
            )
        old_val = self.q_network(data.observations).gather(1, data.actions).squeeze(1)
        loss = nn.functional.mse_loss(td_target, old_val)

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        self.gradient_updates += 1
        if self.gradient_updates % TRAIN_LOG_EVERY_UPDATES:
            return None
        return loss.item(), old_val.mean().item()

    def _sync_target(self, tau: float) -> None:
        for target_param, q_param in zip(
            self.target_network.parameters(), self.q_network.parameters(), strict=True
        ):
            target_param.data.copy_(tau * q_param.data + (1.0 - tau) * target_param.data)
        self.target_syncs += 1


# ======================================================================================
#                                   TRAINING LOOP
# ======================================================================================


def _train(
    CONFIG: Configuration,
    train_run: RunEnvironment,
    eval_run: RunEnvironment,
    learner: DQNLearner,
    recorder: RunRecorder,
) -> None:
    env = train_run.env
    reset_seeds = _training_reset_seeds(CONFIG)
    exploration_steps = CONFIG.exploration_fraction * CONFIG.total_timesteps
    exploration_rng = random.Random(CONFIG.seed)
    episode = EpisodeTracker()
    observation, _ = env.reset(seed=next(reset_seeds))

    for global_step in range(CONFIG.total_timesteps):
        epsilon = linear_schedule(CONFIG.start_e, CONFIG.end_e, exploration_steps, global_step)
        action = select_action(
            learner.q_network, observation, epsilon, env.action_space, exploration_rng
        )
        step = env.step(action)
        store_transition(learner.buffer, observation, action, step)
        episode.record(step, train_run.is_success)

        # == Manual reset: the stored next_obs above is the real final observation ==
        observation, _, terminated, truncated, _ = step
        env_steps = global_step + 1
        if terminated or truncated:
            recorder.write_episode(env_steps, episode, epsilon)
            episode = EpisodeTracker()
            observation, _ = env.reset(seed=next(reset_seeds))

        metrics = learner.update(CONFIG, global_step)
        if metrics is not None:
            recorder.write_training(env_steps, metrics, epsilon)
        # The final evaluation (train_dqn) covers the last step.
        if env_steps % CONFIG.eval_frequency == 0 and env_steps < CONFIG.total_timesteps:
            row = evaluate(CONFIG, eval_run, learner.q_network, CONFIG.eval_episodes)
            recorder.write_evaluation(env_steps, row, CONFIG.success_threshold)


def _layout_seed(CONFIG: Configuration) -> int:
    return CONFIG.seed if CONFIG.layout_seed is None else CONFIG.layout_seed


def _training_reset_seeds(CONFIG: Configuration) -> Iterator[int | None]:
    """Fixed: every reset uses the layout seed. Procedural: seed only the first reset."""
    if CONFIG.layout == "fixed":
        return itertools.repeat(_layout_seed(CONFIG))
    return itertools.chain([CONFIG.seed], itertools.repeat(None))


@dataclass
class EpisodeTracker:
    """Returns, length and final RM fields of one episode; RM fields stay None without an RM."""

    env_return: float = 0.0
    rm_return: float | None = None
    length: int = 0
    exited: bool = False
    rm_state: str | None = None
    rm_accept: bool | None = None

    @property
    def total_return(self) -> float:
        return self.env_return + (self.rm_return or 0.0)

    def record(self, step: tuple, is_success: Callable[[bool, float], bool]) -> None:
        _, reward, terminated, _, info = step
        env_reward = info.get("env_reward", reward)
        self.env_return += env_reward
        self.length += 1
        self.exited = is_success(terminated, env_reward)
        if "rm_reward" in info:
            self.rm_return = (self.rm_return or 0.0) + info["rm_reward"]
            self.rm_state = info["rm_state"]
            self.rm_accept = info["rm_accept"]


# ======================================================================================
#                                     EVALUATION
# ======================================================================================


def evaluate(
    CONFIG: Configuration, run: RunEnvironment, q_network: QNetwork, episode_count: int
) -> dict[str, object]:
    """Roll out ``eval_epsilon``-greedy episodes and return one ``eval.csv`` row.

    A fixed layout runs 1 episode on the layout seed; a procedural layout runs
    ``episode_count`` episodes on held-out seeds ``eval_seed_base + i``. Exploration draws
    come from a fresh RNG seeded with the run seed, never from the training stream.
    """
    rng = random.Random(CONFIG.seed)
    if CONFIG.layout == "fixed":
        seeds = [_layout_seed(CONFIG)]
    else:
        seeds = [CONFIG.eval_seed_base + index for index in range(episode_count)]
    episodes = [
        _evaluation_episode(run, q_network, CONFIG.eval_epsilon, seed, rng) for seed in seeds
    ]

    row: dict[str, object] = {
        "episodes": len(episodes),
        "exit_rate": _mean(episode.exited for episode in episodes),
        "mean_length": _mean(episode.length for episode in episodes),
        "mean_env_return": _mean(episode.env_return for episode in episodes),
        "mean_total_return": _mean(episode.total_return for episode in episodes),
        "seeds": " ".join(str(seed) for seed in seeds),
    }
    if episodes[0].rm_return is not None:
        row["mean_rm_return"] = _mean(episode.rm_return for episode in episodes)
        row["rm_accept_rate"] = _mean(episode.rm_accept for episode in episodes)
        row["accept_exit_agreement"] = _mean(
            episode.rm_accept == episode.exited for episode in episodes
        )
    return row


def _evaluation_episode(
    run: RunEnvironment, q_network: QNetwork, epsilon: float, seed: int, rng: random.Random
) -> EpisodeTracker:
    episode = EpisodeTracker()
    observation, _ = run.env.reset(seed=seed)
    done = False
    while not done:
        action = select_action(q_network, observation, epsilon, run.env.action_space, rng)
        step = run.env.step(action)
        episode.record(step, run.is_success)
        observation, _, terminated, truncated, _ = step
        done = terminated or truncated
    return episode


def _mean(values: Iterable[float]) -> float:
    return float(np.mean(list(values)))


# ======================================================================================
#                                     RUN FOLDER
# ======================================================================================


class RunRecorder:
    """Own one run folder: ``config.yaml``, the CSV logs and ``summary.json``.

    CSV rows are appended as they happen, so an interrupted run keeps its history.
    """

    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.started = time.monotonic()
        self.episode_count = 0
        self.steps_to_success: int | None = None
        for name, columns in (
            ("episodes.csv", EPISODE_COLUMNS),
            ("eval.csv", EVAL_COLUMNS),
            ("train.csv", TRAIN_COLUMNS),
        ):
            with (directory / name).open("w", newline="", encoding="utf-8") as file:
                csv.DictWriter(file, columns).writeheader()

    @classmethod
    def create(cls, CONFIG: Configuration, device: torch.device) -> RunRecorder:
        """Create ``outputs/runs/<exp_name>/seed<seed>-<UTC>-<pid>/`` with ``config.yaml``."""
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        name = f"seed{CONFIG.seed}-{stamp}-{os.getpid()}"
        recorder = cls(CONFIG.OUTPUT_PATH / "runs" / CONFIG.exp_name / name)
        settings = {field: _plain(getattr(CONFIG, field)) for field in RUN_SETTINGS}
        settings["layout_seed"] = _layout_seed(CONFIG)
        settings["device"] = str(device)
        settings["git_head"] = _git_head()
        (recorder.directory / "config.yaml").write_text(
            yaml.safe_dump(settings, sort_keys=False), encoding="utf-8"
        )
        return recorder

    @property
    def wall_seconds(self) -> float:
        return time.monotonic() - self.started

    def write_episode(self, env_steps: int, episode: EpisodeTracker, epsilon: float) -> None:
        self.episode_count += 1
        self._append(
            "episodes.csv",
            EPISODE_COLUMNS,
            {
                "global_step": env_steps,
                "episode": self.episode_count,
                "env_return": episode.env_return,
                "rm_return": episode.rm_return,
                "total_return": episode.total_return,
                "length": episode.length,
                "exited": episode.exited,
                "final_rm_state": episode.rm_state,
                "epsilon": epsilon,
                "wall_seconds": self.wall_seconds,
            },
        )

    def write_training(self, env_steps: int, metrics: tuple[float, float], epsilon: float) -> None:
        td_loss, q_mean = metrics
        sps = int(env_steps / self.wall_seconds)
        row = {"td_loss": td_loss, "q_mean": q_mean, "epsilon": epsilon, "sps": sps}
        self._append("train.csv", TRAIN_COLUMNS, {"global_step": env_steps, **row})

    def write_evaluation(self, env_steps: int, row: dict[str, object], threshold: float) -> None:
        """Append one eval row; the first row reaching ``threshold`` sets ``steps_to_success``."""
        if self.steps_to_success is None and row["exit_rate"] >= threshold:
            self.steps_to_success = env_steps
        self._append("eval.csv", EVAL_COLUMNS, {"global_step": env_steps, **row})
        print(
            f"step {env_steps}: exit_rate {row['exit_rate']:.2f}, "
            f"mean_env_return {row['mean_env_return']:.3f}, {self.wall_seconds:.0f} s"
        )

    def write_summary(
        self, CONFIG: Configuration, learner: DQNLearner, final_eval: dict[str, object]
    ) -> None:
        summary = {
            "total_env_steps": CONFIG.total_timesteps,
            "total_training_episodes": self.episode_count,
            "wall_seconds": self.wall_seconds,
            "gradient_updates": learner.gradient_updates,
            "target_syncs": learner.target_syncs,
            "parameter_change_norm": learner.parameter_change_norm(),
            "steps_to_success": self.steps_to_success,
            "success_threshold": CONFIG.success_threshold,
            "final_eval": final_eval,
        }
        (self.directory / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )

    def _append(self, name: str, columns: Sequence[str], row: dict[str, object]) -> None:
        with (self.directory / name).open("a", newline="", encoding="utf-8") as file:
            csv.DictWriter(file, columns).writerow(row)


def _plain(value: object) -> object:
    """Make a Configuration value YAML-safe; paths become absolute strings."""
    return str(value.resolve()) if isinstance(value, Path) else value


def _git_head() -> str | None:
    """HEAD commit, suffixed ``-dirty`` when ``git status --porcelain`` lists changes."""
    head = _git("rev-parse", "HEAD")
    if not head:
        return None
    return f"{head}-dirty" if _git("status", "--porcelain") else head


def _git(*arguments: str) -> str:
    git = shutil.which("git")
    if git is None:
        return ""
    completed = subprocess.run(  # noqa: S603  approved: fixed git argv, no shell
        [git, *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=Configuration.WORKSPACE_PATH,
    )
    return completed.stdout.strip()
