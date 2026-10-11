"""PPO training with optional Reward Machine conditioning (ARM-FM Table 6).

Adapted from CleanRL ``cleanrl/ppo_atari.py`` at commit
004f8a086a892a2a180f4dd332b90d83a968aa7a:
https://github.com/vwxyzjn/cleanrl/blob/004f8a086a892a2a180f4dd332b90d83a968aa7a/cleanrl/ppo_atari.py

Kept: orthogonal initialization, learning-rate annealing, GAE, the clipped surrogate and value
losses with advantage normalization, and the minibatch update schedule.
Changed: every env comes from ``make_run_environment`` (its own Reward Machine and labeling), the
vector env uses SAME_STEP autoreset with terminal data read from ``final_info``/``final_obs``,
truncated episodes bootstrap from the value of their final observation, an RM-embedding branch
joins the image features, periodic evaluation on a separate env, and CSV/JSON run metrics in the
run folder shared with DQN. Removed: tyro, Atari wrappers, wandb, TensorBoard and video capture.
``global_step`` counts agent actions summed over envs; engine frames are logged separately.

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

import math
import time
from contextlib import ExitStack
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import numpy as np
import torch
from gymnasium import spaces
from gymnasium.vector import AutoresetMode, SyncVectorEnv
from stable_baselines3.common.utils import set_random_seed
from torch import Tensor, nn, optim
from torch.distributions.categorical import Categorical

from src.config import Configuration

from .dqn import (
    EpisodeTracker,
    RunRecorder,
    evaluation_row,
    rm_embedding_branch,
)
from .environments import RunEnvironment, make_run_environment

TRAIN_COLUMNS = (
    "global_step",
    "engine_frames",
    "iteration",
    "learning_rate",
    "policy_loss",
    "value_loss",
    "entropy",
    "approx_kl",
    "clipfrac",
    "explained_variance",
    "sps",
    "wall_seconds",
    "collect_seconds",
    "update_seconds",
)
POSITIVE_SETTINGS = ("total_timesteps", "eval_frequency", "eval_episodes", "final_eval_episodes")
STEP_INFO_KEYS = ("env_reward", "rm_reward", "rm_state", "rm_accept")
HIDDEN_FEATURES = 512
LOG_EVERY_ITERATIONS = 10

Observation = dict[str, Tensor]


# ======================================================================================
#                                      PUBLIC API
# ======================================================================================


def train_ppo(CONFIG: Configuration) -> Path:
    """Train one PPO run and write its run folder under ``outputs/runs/<exp_name>/``.

    Runs ``ceil(total_timesteps / (ppo_num_envs * ppo_num_steps))`` iterations, so the budget is
    never cut short. ``layout`` and ``layout_seed`` are not used: evaluation episode ``i`` resets
    its env with ``eval_seed_base + i``. The final evaluation scores the final policy and is the
    last ``eval.csv`` row.

    Returns:
        Path: The run folder.

    Raises:
        ValueError: If the run config is invalid or the action space is not ``Discrete``.
    """
    _check_settings(CONFIG)
    set_random_seed(CONFIG.seed)
    torch.backends.cudnn.deterministic = CONFIG.torch_deterministic
    device = torch.device("cuda" if torch.cuda.is_available() and CONFIG.cuda else "cpu")

    # Every env registers its close as soon as it exists, so a failure while building env k, or
    # later in the run, still closes envs 0..k-1 (and each close runs even if another raises).
    with ExitStack() as cleanup:
        runs = [_open_run(CONFIG, cleanup) for _ in range(CONFIG.ppo_num_envs)]
        eval_run = _open_run(CONFIG, cleanup)
        envs = SyncVectorEnv(
            [partial(getattr, run, "env") for run in runs], autoreset_mode=AutoresetMode.SAME_STEP
        )
        directory = _run(CONFIG, runs, eval_run, envs, device)
    print(f"run folder {directory}")
    return directory


def _open_run(CONFIG: Configuration, cleanup: ExitStack) -> RunEnvironment:
    run = make_run_environment(CONFIG)
    cleanup.callback(run.env.close)
    return run


def _run(
    CONFIG: Configuration,
    runs: list[RunEnvironment],
    eval_run: RunEnvironment,
    envs: SyncVectorEnv,
    device: torch.device,
) -> Path:
    if not isinstance(envs.single_action_space, spaces.Discrete):
        raise ValueError(
            f"train-rl PPO needs a Discrete action space; {CONFIG.gym_id} has "
            f"{envs.single_action_space}"
        )
    learner = PPOLearner.create(CONFIG, runs[0], envs.single_observation_space, device)
    recorder = RunRecorder.create(CONFIG, device, TRAIN_COLUMNS)
    collector = RolloutCollector(CONFIG, envs, runs, device)
    _train(CONFIG, collector, eval_run, learner, recorder)

    global_step = collector.global_step
    final_eval = evaluate(CONFIG, eval_run, learner.agent, CONFIG.final_eval_episodes)
    recorder.write_evaluation(global_step, final_eval, CONFIG.success_threshold)
    fields = {**learner.summary_fields(), **collector.summary_fields()}
    recorder.write_summary(CONFIG, fields, final_eval)
    torch.save(learner.agent.state_dict(), recorder.directory / "agent.pt")
    return recorder.directory


def load_ppo_agent(path: Path, run: RunEnvironment, device: torch.device) -> PPOAgent:
    """Rebuild the agent for ``run``'s spaces and load the ``agent.pt`` state dict at ``path``."""
    agent = PPOAgent(run.make_encoder(), run.env.observation_space, int(run.env.action_space.n))
    agent.load_state_dict(torch.load(path, map_location=device))
    return agent.to(device)


def _check_settings(CONFIG: Configuration) -> None:
    """Reject settings that would crash mid-run, before the run folder exists."""
    if CONFIG.algorithm != "ppo":
        raise ValueError(f"train_ppo trains algorithm: ppo, not {CONFIG.algorithm!r}")
    not_positive = [name for name in POSITIVE_SETTINGS if getattr(CONFIG, name) <= 0]
    if not_positive:
        raise ValueError(f"These run settings must be positive: {', '.join(not_positive)}")
    minibatch_size = CONFIG.ppo_num_envs * CONFIG.ppo_num_steps // CONFIG.ppo_num_minibatches
    if minibatch_size < 2:
        raise ValueError(
            f"PPO minibatch size must be at least 2 (got {minibatch_size} = ppo_num_envs "
            f"{CONFIG.ppo_num_envs} * ppo_num_steps {CONFIG.ppo_num_steps} / ppo_num_minibatches "
            f"{CONFIG.ppo_num_minibatches}): advantage normalization needs two samples"
        )


# ======================================================================================
#                                        AGENT
# ======================================================================================


def _orthogonal(layer: nn.Module, std: float) -> None:
    nn.init.orthogonal_(layer.weight, std)
    nn.init.constant_(layer.bias, 0.0)


class PPOAgent(nn.Module):
    """Encoder features plus an optional RM-embedding branch, one shared hidden layer, two heads.

    Observations are dicts of batched tensors: ``image`` and, with an RM, ``rm_embedding``.
    """

    def __init__(
        self, encoder: nn.Module, observation_space: spaces.Space, action_count: int
    ) -> None:
        super().__init__()
        self.encoder = encoder
        self.rm_embedding: nn.Module | None = None
        image_space = observation_space
        rm_feature_count = 0
        if isinstance(observation_space, spaces.Dict):
            image_space = observation_space["image"]
            dimension = observation_space["rm_embedding"].shape[0]
            rm_feature_count = dimension // 4
            self.rm_embedding = rm_embedding_branch(dimension)

        with torch.no_grad():
            image_feature_count = encoder(torch.zeros((1, *image_space.shape))).shape[1]
        self.hidden = nn.Sequential(
            nn.Linear(image_feature_count + rm_feature_count, HIDDEN_FEATURES), nn.ReLU()
        )
        self.actor = nn.Linear(HIDDEN_FEATURES, action_count)
        self.critic = nn.Linear(HIDDEN_FEATURES, 1)

        for module in self.modules():
            if isinstance(module, nn.Conv2d | nn.Linear):
                _orthogonal(module, math.sqrt(2))
        _orthogonal(self.actor, 0.01)
        _orthogonal(self.critic, 1.0)

    def _features(self, observation: Observation) -> Tensor:
        features = self.encoder(observation["image"])
        if self.rm_embedding is not None:
            features = torch.cat([features, self.rm_embedding(observation["rm_embedding"])], dim=1)
        return self.hidden(features)

    def get_value(self, observation: Observation) -> Tensor:
        return self.critic(self._features(observation))

    def get_action_and_value(
        self, observation: Observation, action: Tensor | None = None
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        hidden = self._features(observation)
        distribution = Categorical(logits=self.actor(hidden))
        if action is None:
            action = distribution.sample()
        return action, distribution.log_prob(action), distribution.entropy(), self.critic(hidden)

    @torch.no_grad()
    def act(
        self,
        observation: np.ndarray | dict[str, np.ndarray],
        generator: torch.Generator | None = None,
        deterministic: bool = False,
    ) -> int:
        """Action for one unbatched observation: sampled from the policy, or its argmax."""
        device = next(self.parameters()).device
        batch = {key: value[None] for key, value in _as_dict(observation).items()}
        logits = self.actor(self._features(_to_tensors(batch, device)))
        if deterministic:
            return int(logits.argmax(dim=1).item())
        return int(torch.multinomial(logits.softmax(dim=1).cpu(), 1, generator=generator).item())


def _as_dict(observation: np.ndarray | dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return observation if isinstance(observation, dict) else {"image": observation}


def _to_tensors(observation: dict[str, np.ndarray], device: torch.device) -> Observation:
    return {key: torch.as_tensor(value, device=device) for key, value in observation.items()}


# ======================================================================================
#                                  ROLLOUTS AND UPDATES
# ======================================================================================


@dataclass
class Rollout:
    """One iteration of experience: ``(ppo_num_steps, ppo_num_envs)`` tensors per field."""

    observations: Observation
    actions: Tensor
    logprobs: Tensor
    rewards: Tensor
    dones: Tensor
    values: Tensor

    @classmethod
    def create(
        cls, CONFIG: Configuration, observation_space: spaces.Space, device: torch.device
    ) -> Rollout:
        shape = (CONFIG.ppo_num_steps, CONFIG.ppo_num_envs)
        space_by_key = (
            dict(observation_space.spaces)
            if isinstance(observation_space, spaces.Dict)
            else {"image": observation_space}
        )
        observations = {
            key: torch.zeros(
                (*shape, *space.shape),
                dtype=torch.as_tensor(np.empty((), space.dtype)).dtype,
                device=device,
            )
            for key, space in space_by_key.items()
        }
        zeros = partial(torch.zeros, shape, device=device)
        return cls(observations, zeros(dtype=torch.long), zeros(), zeros(), zeros(), zeros())

    def advantages(
        self, CONFIG: Configuration, next_value: Tensor, next_done: Tensor
    ) -> tuple[Tensor, Tensor]:
        """GAE advantages and returns; ``next_value`` and ``next_done`` follow the last step."""
        advantages = torch.zeros_like(self.rewards)
        last_advantage = 0.0
        discount = CONFIG.gamma * CONFIG.ppo_gae_lambda
        for t in reversed(range(CONFIG.ppo_num_steps)):
            if t == CONFIG.ppo_num_steps - 1:
                non_terminal, next_values = 1.0 - next_done, next_value
            else:
                non_terminal, next_values = 1.0 - self.dones[t + 1], self.values[t + 1]
            delta = self.rewards[t] + CONFIG.gamma * next_values * non_terminal - self.values[t]
            last_advantage = delta + discount * non_terminal * last_advantage
            advantages[t] = last_advantage
        return advantages, advantages + self.values


@dataclass
class Batch:
    """The flattened rollout, indexable by minibatch indices."""

    observations: Observation
    actions: Tensor
    logprobs: Tensor
    values: Tensor
    advantages: Tensor
    returns: Tensor

    def __getitem__(self, indices: Tensor) -> Batch:
        return Batch(
            {key: value[indices] for key, value in self.observations.items()},
            self.actions[indices],
            self.logprobs[indices],
            self.values[indices],
            self.advantages[indices],
            self.returns[indices],
        )


class RolloutCollector:
    """Step the vector env, fill rollouts and keep per-env episode statistics.

    ``global_step`` counts agent actions summed over envs. Terminal data of an episode comes from
    ``final_info``/``final_obs`` (SAME_STEP autoreset); a truncated episode adds
    ``gamma * V(final observation)`` to its last reward so the time limit is not a terminal.
    """

    def __init__(
        self,
        CONFIG: Configuration,
        envs: SyncVectorEnv,
        runs: list[RunEnvironment],
        device: torch.device,
    ) -> None:
        self.envs = envs
        self.runs = runs
        self.device = device
        self.global_step = 0
        self.trackers = [EpisodeTracker() for _ in runs]
        self.rm_states: set[str] = set()
        observation, _ = envs.reset(seed=CONFIG.seed)
        self.next_observation = _to_tensors(_as_dict(observation), device)
        self.next_done = torch.zeros(len(runs), device=device)

    def collect(
        self, CONFIG: Configuration, agent: PPOAgent, rollout: Rollout, recorder: RunRecorder
    ) -> None:
        """Run ``ppo_num_steps`` vector steps into ``rollout``, logging finished episodes."""
        for step in range(CONFIG.ppo_num_steps):
            self.global_step += len(self.runs)
            for key, value in self.next_observation.items():
                rollout.observations[key][step] = value
            rollout.dones[step] = self.next_done

            with torch.no_grad():
                action, logprob, _, value = agent.get_action_and_value(self.next_observation)
            rollout.values[step] = value.flatten()
            rollout.actions[step] = action
            rollout.logprobs[step] = logprob

            observation, reward, terminated, truncated, infos = self.envs.step(action.cpu().numpy())
            done = np.logical_or(terminated, truncated)
            reward = torch.as_tensor(reward, dtype=torch.float32, device=self.device)
            timed_out = np.nonzero(truncated & ~terminated)[0]
            rollout.rewards[step] = self._bootstrap_timeouts(
                CONFIG, agent, reward, timed_out, infos
            )

            self._record_episodes(recorder, reward, terminated, truncated, infos)
            self.next_observation = _to_tensors(_as_dict(observation), self.device)
            self.next_done = torch.as_tensor(done, dtype=torch.float32, device=self.device)

    def engine_frames(self) -> int | None:
        """Engine steps simulated so far over all envs, or None when the env family has none."""
        frames = [getattr(run.env.unwrapped, "engine_frames", None) for run in self.runs]
        return None if frames[0] is None else sum(frames)

    def summary_fields(self) -> dict[str, object]:
        """The collector's entries of ``summary.json``."""
        fields: dict[str, object] = {
            "total_env_steps": self.global_step,
            "engine_frames": self.engine_frames(),
        }
        if self.rm_states:
            fields["rm_states_visited"] = sorted(self.rm_states)
        return fields

    def _bootstrap_timeouts(
        self,
        CONFIG: Configuration,
        agent: PPOAgent,
        reward: Tensor,
        timed_out: np.ndarray,
        infos: dict,
    ) -> Tensor:
        if len(timed_out) == 0:
            return reward
        finals = [_as_dict(infos["final_obs"][index]) for index in timed_out]
        batch = {key: np.stack([final[key] for final in finals]) for key in finals[0]}
        with torch.no_grad():
            values = agent.get_value(_to_tensors(batch, self.device)).flatten()
        reward = reward.clone()
        reward[torch.as_tensor(timed_out, device=self.device)] += CONFIG.gamma * values
        return reward

    def _record_episodes(
        self,
        recorder: RunRecorder,
        reward: Tensor,
        terminated: np.ndarray,
        truncated: np.ndarray,
        infos: dict,
    ) -> None:
        done = np.logical_or(terminated, truncated)
        for index, run in enumerate(self.runs):
            info = _step_info(infos, done, index)
            step = (
                None,
                float(reward[index]),
                bool(terminated[index]),
                bool(truncated[index]),
                info,
            )
            self.trackers[index].record(step, run.is_success)
            if "rm_state" in info:
                self.rm_states.add(str(info["rm_state"]))
            if done[index]:
                recorder.write_episode(self.global_step, self.trackers[index], None)
                self.trackers[index] = EpisodeTracker()


def _step_info(infos: dict, done: np.ndarray, index: int) -> dict[str, object]:
    """The step info of env ``index``; an episode's last step lives in ``final_info``."""
    source = infos["final_info"] if done[index] else infos
    return {key: source[key][index] for key in STEP_INFO_KEYS if key in source}


@dataclass
class PPOLearner:
    """The agent, its optimizer and update counts."""

    agent: PPOAgent
    optimizer: optim.Optimizer
    initial_parameters: Tensor
    shuffler: np.random.Generator
    gradient_updates: int = 0

    @classmethod
    def create(
        cls,
        CONFIG: Configuration,
        run: RunEnvironment,
        observation_space: spaces.Space,
        device: torch.device,
    ) -> PPOLearner:
        action_count = int(run.env.action_space.n)
        agent = PPOAgent(run.make_encoder(), observation_space, action_count).to(device)
        optimizer = optim.Adam(agent.parameters(), lr=CONFIG.ppo_learning_rate, eps=1e-5)
        initial = nn.utils.parameters_to_vector(agent.parameters()).detach().clone()
        return cls(agent, optimizer, initial, np.random.default_rng(CONFIG.seed))

    def set_learning_rate(self, learning_rate: float) -> None:
        self.optimizer.param_groups[0]["lr"] = learning_rate

    def parameter_change_norm(self) -> float:
        final = nn.utils.parameters_to_vector(self.agent.parameters()).detach()
        return float(torch.linalg.vector_norm(final - self.initial_parameters))

    def summary_fields(self) -> dict[str, object]:
        """The learner's entries of ``summary.json``."""
        return {
            "gradient_updates": self.gradient_updates,
            "parameter_change_norm": self.parameter_change_norm(),
        }

    def update(
        self, CONFIG: Configuration, rollout: Rollout, advantages: Tensor, returns: Tensor
    ) -> dict[str, float]:
        """Run ``ppo_update_epochs`` epochs of clipped minibatch updates over the rollout.

        Returns:
            dict[str, float]: The last minibatch's losses and KL, the mean clip fraction and the
            explained variance of the value head, for ``train.csv``.
        """
        batch_size = CONFIG.ppo_num_steps * CONFIG.ppo_num_envs
        minibatch_size = batch_size // CONFIG.ppo_num_minibatches
        batch = Batch(
            {key: value.flatten(0, 1) for key, value in rollout.observations.items()},
            rollout.actions.flatten(),
            rollout.logprobs.flatten(),
            rollout.values.flatten(),
            advantages.flatten(),
            returns.flatten(),
        )

        indices = np.arange(batch_size)
        clip_fractions: list[float] = []
        metrics: dict[str, float] = {}
        for _ in range(CONFIG.ppo_update_epochs):
            self.shuffler.shuffle(indices)
            for start in range(0, batch_size, minibatch_size):
                chosen = torch.as_tensor(
                    indices[start : start + minibatch_size], device=batch.actions.device
                )
                metrics = self._minibatch_step(CONFIG, batch[chosen])
                clip_fractions.append(metrics.pop("clipfrac"))
        metrics["clipfrac"] = float(np.mean(clip_fractions))
        metrics["explained_variance"] = _explained_variance(batch.values, batch.returns)
        return metrics

    def _minibatch_step(self, CONFIG: Configuration, batch: Batch) -> dict[str, float]:
        _, new_logprob, entropy, new_value = self.agent.get_action_and_value(
            batch.observations, batch.actions
        )
        log_ratio = new_logprob - batch.logprobs
        ratio = log_ratio.exp()
        with torch.no_grad():
            approx_kl = ((ratio - 1) - log_ratio).mean()
            clip_fraction = ((ratio - 1.0).abs() > CONFIG.ppo_clip_coef).float().mean()

        advantage = batch.advantages
        if CONFIG.ppo_norm_adv:
            advantage = (advantage - advantage.mean()) / (advantage.std() + 1e-8)
        clip = CONFIG.ppo_clip_coef
        policy_loss = torch.max(
            -advantage * ratio, -advantage * torch.clamp(ratio, 1 - clip, 1 + clip)
        ).mean()

        new_value = new_value.view(-1)
        if CONFIG.ppo_clip_vloss:
            clipped = batch.values + torch.clamp(new_value - batch.values, -clip, clip)
            value_loss = (
                0.5
                * torch.max((new_value - batch.returns) ** 2, (clipped - batch.returns) ** 2).mean()
            )
        else:
            value_loss = 0.5 * ((new_value - batch.returns) ** 2).mean()

        entropy_loss = entropy.mean()
        loss = policy_loss - CONFIG.ppo_ent_coef * entropy_loss + CONFIG.ppo_vf_coef * value_loss
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.agent.parameters(), CONFIG.ppo_max_grad_norm)
        self.optimizer.step()
        self.gradient_updates += 1
        return {
            "policy_loss": policy_loss.item(),
            "value_loss": value_loss.item(),
            "entropy": entropy_loss.item(),
            "approx_kl": approx_kl.item(),
            "clipfrac": clip_fraction.item(),
        }


def _explained_variance(predicted: Tensor, target: Tensor) -> float:
    y_pred, y_true = predicted.cpu().numpy(), target.cpu().numpy()
    variance = np.var(y_true)
    return float("nan") if variance == 0 else float(1 - np.var(y_true - y_pred) / variance)


# ======================================================================================
#                                   TRAINING LOOP
# ======================================================================================


def _train(
    CONFIG: Configuration,
    collector: RolloutCollector,
    eval_run: RunEnvironment,
    learner: PPOLearner,
    recorder: RunRecorder,
) -> None:
    batch_size = CONFIG.ppo_num_steps * CONFIG.ppo_num_envs
    iterations = math.ceil(CONFIG.total_timesteps / batch_size)
    rollout = Rollout.create(CONFIG, collector.envs.single_observation_space, collector.device)
    next_evaluation = CONFIG.eval_frequency

    for iteration in range(1, iterations + 1):
        learning_rate = CONFIG.ppo_learning_rate
        if CONFIG.ppo_anneal_lr:
            learning_rate *= 1.0 - (iteration - 1.0) / iterations
        learner.set_learning_rate(learning_rate)

        started = time.monotonic()
        collector.collect(CONFIG, learner.agent, rollout, recorder)
        collected = time.monotonic()
        with torch.no_grad():
            next_value = learner.agent.get_value(collector.next_observation).reshape(1, -1)
        advantages, returns = rollout.advantages(CONFIG, next_value, collector.next_done)
        metrics = learner.update(CONFIG, rollout, advantages, returns)
        updated = time.monotonic()

        global_step = collector.global_step
        sps = int(global_step / recorder.wall_seconds)
        recorder.write_training_row(
            {
                "global_step": global_step,
                "engine_frames": collector.engine_frames(),
                "iteration": iteration,
                "learning_rate": learning_rate,
                "sps": sps,
                "wall_seconds": recorder.wall_seconds,
                "collect_seconds": collected - started,
                "update_seconds": updated - collected,
                **metrics,
            }
        )
        if iteration % LOG_EVERY_ITERATIONS == 0:
            print(f"iteration {iteration}/{iterations}: step {global_step}, {sps} sps", flush=True)
        # The final evaluation (train_ppo) covers the last iteration.
        if global_step >= next_evaluation and iteration < iterations:
            row = evaluate(CONFIG, eval_run, learner.agent, CONFIG.eval_episodes)
            recorder.write_evaluation(global_step, row, CONFIG.success_threshold)
            while next_evaluation <= global_step:
                next_evaluation += CONFIG.eval_frequency


# ======================================================================================
#                                     EVALUATION
# ======================================================================================


def evaluate(
    CONFIG: Configuration, run: RunEnvironment, agent: PPOAgent, episode_count: int
) -> dict[str, object]:
    """Roll out ``episode_count`` policy-sampling episodes and return one ``eval.csv`` row.

    Episode ``i`` resets with seed ``eval_seed_base + i``. Sampling draws come from a fresh
    generator seeded with the run seed, never from the training streams.
    """
    generator = torch.Generator().manual_seed(CONFIG.seed)
    seeds = [CONFIG.eval_seed_base + index for index in range(episode_count)]
    episodes = [_evaluation_episode(run, agent, seed, generator) for seed in seeds]
    return evaluation_row(episodes)


def _evaluation_episode(
    run: RunEnvironment, agent: PPOAgent, seed: int, generator: torch.Generator
) -> EpisodeTracker:
    episode = EpisodeTracker(seed=seed)
    observation, _ = run.env.reset(seed=seed)
    done = False
    while not done:
        step = run.env.step(agent.act(observation, generator))
        episode.record(step, run.is_success)
        observation, _, terminated, truncated, _ = step
        done = terminated or truncated
    return episode
