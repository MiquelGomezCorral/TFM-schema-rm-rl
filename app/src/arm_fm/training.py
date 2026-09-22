"""Native Tianshou ARM-FM learners, collectors, and strict checkpoints."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from .artifacts import ArtifactBundle
from .runtime import RewardMachineEnvironment, RewardMachineRuntime

TIANSHOU_VERSION = "2.0.1"
RND_UPSTREAM = "RLeXplore (MIT), revision recorded as reconstructed adaptation"
ALGORITHMS = {
    "minigrid": "dqn", "babyai": "dqn", "xland": "rainbow",
    "xland-minigrid": "rainbow", "craftium": "ppo", "metaworld": "sac",
    "meta-world": "sac",
}
ALGORITHM_COMPONENTS = {
    "dqn": {
        "learner": "tianshou.DQN", "double_q": False, "target_update": 2_500,
        "epsilon": (1.0, 0.01, 0.35), "train_frequency": 4,
    },
    "rainbow": {
        "learner": "tianshou.RainbowDQN", "double_q": True,
        "replay": "PrioritizedVectorReplayBuffer", "per_alpha": 0.5,
        "per_beta": 0.4, "n_step": 3, "atoms": 51, "v_range": (-10.0, 10.0),
        "target_update": 5_000, "epsilon": (1.0, 0.05, 0.1), "train_frequency": 4,
        "dueling": True, "noisy_linear": True,
    },
    "ppo": {
        "learner": "tianshou.PPO", "rollout": 128, "minibatches": 4,
        "epochs": 4, "gae_lambda": 0.95, "clip": 0.1, "max_grad_norm": 0.5,
    },
    "sac": {
        "learner": "ARMFMPeriodicSAC(tianshou.SAC)", "replay": "VectorReplayBuffer",
        "policy_frequency": 2, "critic_frequency": 1,
    },
}


@dataclass(frozen=True)
class TrainingConfig:
    algorithm: str
    total_timesteps: int
    learning_rate: float
    gamma: float = 0.99
    batch_size: int = 32
    seed: int = 42
    task_group: tuple[int, ...] = ()
    sparse_baseline: bool = False
    rnd: bool = False
    exploration: bool = True
    replay_capacity: int = 1_000_000
    learning_starts: int = 0
    train_frequency: int | None = None
    target_update_frequency: int | None = None
    rnd_coefficient: float = 0.01
    rollout_length: int = 128
    epsilon_start: float | None = None
    epsilon_end: float | None = None
    epsilon_fraction: float | None = None


@dataclass(frozen=True)
class ExperimentManifest:
    domain: str
    algorithm: str
    train_tasks: tuple[int, ...]
    held_out_tasks: tuple[int, ...] = ()
    seeds: tuple[int, ...] = (0, 1, 2)
    ablations: tuple[str, ...] = ()
    reconstructed_choices: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskManifestEntry:
    task_id: str
    bundle: Path
    environment_description: Path
    environment_id: str
    settings: dict[str, Any] = field(default_factory=dict)
    split: str = "train"


def load_task_manifest(path: str | Path) -> tuple[TaskManifestEntry, ...]:
    manifest_path = Path(path).resolve()
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = value.get("tasks", value) if isinstance(value, dict) else value
    if not isinstance(records, dict):
        raise ValueError("Task manifest must map task ids to entries")
    entries = []
    for task_id, item in records.items():
        if not isinstance(item, dict) or not isinstance(item.get("bundle"), str):
            raise ValueError(f"Task manifest entry {task_id!r} requires a bundle path")
        environment_description = item.get("environment_description")
        environment_id = item.get("environment_id")
        if not isinstance(environment_description, str) or not environment_description.strip():
            raise ValueError(f"Task manifest entry {task_id!r} requires environment_description")
        if not isinstance(environment_id, str) or not environment_id.strip():
            raise ValueError(f"Task manifest entry {task_id!r} requires environment_id")
        entries.append(TaskManifestEntry(
            str(task_id),
            (manifest_path.parent / item["bundle"]).resolve(),
            (manifest_path.parent / environment_description).resolve(),
            environment_id,
            dict(item.get("settings", {})), str(item.get("split", "train")),
        ))
    return tuple(entries)


def paper_experiment_manifest(domain: str) -> ExperimentManifest:
    algorithm = algorithm_for_domain(domain)
    if "xland" in domain.lower():
        return ExperimentManifest(
            domain, algorithm, (197,),
            (212, 260, 859, 594, 571, 602, 751, 660, 616),
            ablations=("rewards-only", "embeddings-only", "full"),
            reconstructed_choices=("first 1,000 medium-1m rulesets", "three independent seeds"),
        )
    return ExperimentManifest(
        domain, algorithm, (), reconstructed_choices=(
            "task partitions and unpublished wrappers are reconstructed", "three independent seeds",
        ),
    )


@dataclass(frozen=True)
class TransitionRecord:
    observation: Any
    rm_state: str
    action: Any
    reward: float
    next_observation: Any
    next_rm_state: str
    terminated: bool
    truncated: bool
    embedding: tuple[float, ...] = ()
    next_embedding: tuple[float, ...] = ()


@dataclass
class TrainingCheckpoint:
    """Checkpoint with Tianshou's complete native algorithm state."""

    algorithm: str
    timestep: int
    seed: int
    config: dict[str, Any]
    algorithm_state: Any = None
    normalization: dict[str, Any] = field(default_factory=dict)
    rnd_state: Any = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def save(self, path: str | Path) -> Path:
        import torch

        if self.algorithm_state is None:
            raise ValueError("Checkpoint requires a native Algorithm.state_dict")
        payload = asdict(self)
        _validate_checkpoint_value(payload, torch)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        torch.save(payload, target)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "TrainingCheckpoint":
        import torch

        data = torch.load(Path(path), map_location="cpu", weights_only=True)
        if not isinstance(data, dict):
            raise ValueError("Checkpoint must contain a mapping")
        _validate_checkpoint_value(data, torch)
        checkpoint = cls(**data)
        if checkpoint.algorithm_state is None:
            raise ValueError("Checkpoint is missing native algorithm state")
        return checkpoint


def _validate_checkpoint_value(value: object, torch_module: object) -> None:
    """Keep native checkpoints to tensors and primitive containers."""
    tensor_type = getattr(torch_module, "Tensor")
    if value is None or isinstance(value, (bool, int, float, str, bytes, tensor_type)):
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_checkpoint_value(key, torch_module)
            _validate_checkpoint_value(item, torch_module)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_checkpoint_value(item, torch_module)
        return
    raise TypeError(f"Checkpoint contains unsupported value: {type(value).__name__}")


def algorithm_for_domain(domain: str) -> str:
    normalized = domain.lower().replace("_", "-")
    if "xland-minigrid" in normalized or "xland" in normalized:
        return "rainbow"
    if "craftium" in normalized:
        return "ppo"
    if "metaworld" in normalized or "meta-world" in normalized:
        return "sac"
    if "minigrid" in normalized or "babyai" in normalized:
        return "dqn"
    raise ValueError(f"Unsupported ARM-FM training domain: {domain!r}")


def paper_training_config(domain: str, *, seed: int = 42, rnd: bool = False) -> TrainingConfig:
    algorithm = algorithm_for_domain(domain)
    rnd = rnd or _explicit_rnd_variant(domain)
    values = {
        "dqn": (10_000_000, 1e-4, 32, 80_000, 4, 2_500, 1.0, 0.01, 0.35),
        "rainbow": (5_000_000, 6.25e-5, 32, 80_000, 4, 5_000, 1.0, 0.05, 0.1),
        "ppo": (10_000_000, 5e-5, 128, 0, None, None, None, None, None),
        "sac": (15_000_000, 3e-4, 512, 5_000, 1, None, None, None, None),
    }
    total, learning_rate, batch_size, starts, frequency, target, eps_start, eps_end, eps_fraction = values[algorithm]
    return TrainingConfig(
        algorithm, total, learning_rate, batch_size=batch_size, seed=seed, rnd=rnd,
        learning_starts=starts, train_frequency=frequency, target_update_frequency=target,
        rnd_coefficient=0.01 if rnd else 0.0,
        epsilon_start=eps_start, epsilon_end=eps_end, epsilon_fraction=eps_fraction,
    )


def train_larm(
    bundle: ArtifactBundle,
    environment: object | list[object] | tuple[object, ...],
    policy: "BuiltinPolicy | None" = None,
    config: TrainingConfig | None = None,
    *,
    embeddings: dict[str, list[float]] | None = None,
    checkpoint_path: str | Path | None = None,
) -> TrainingCheckpoint:
    """Train via one native Collector and native algorithm trainer."""
    if config is None and isinstance(policy, TrainingConfig):
        config, policy = policy, None
    if config is None:
        raise ValueError("TrainingConfig is required")
    if config.total_timesteps < 1:
        raise ValueError("total_timesteps must be positive")
    if config.algorithm not in ALGORITHM_COMPONENTS:
        raise ValueError(f"Unsupported training algorithm: {config.algorithm}")
    config = replace(config, replay_capacity=min(config.replay_capacity, config.total_timesteps))
    bundle.validate(require_complete=True)
    embeddings = embeddings or bundle.embeddings
    if set(embeddings) != set(bundle.reward_machine.states):
        raise ValueError("Training requires one embedding per RM state")
    environments = tuple(environment) if isinstance(environment, (list, tuple)) else (environment,)
    if config.algorithm == "ppo" and len(environments) != 4:
        raise ValueError("Craftium PPO requires exactly four independent environments")
    wrappers = [
        _embedded_environment(
            RewardMachineEnvironment(
                item, RewardMachineRuntime(bundle.reward_machine), bundle.labeling_source,
            ),
            embeddings,
        )
        for item in environments
    ]
    if len(wrappers) == 1:
        training_environment = wrappers[0]
        buffer_num = 1
        first_observation, _ = training_environment.reset()
        policy_observation = first_observation
    else:
        from tianshou.env import DummyVectorEnv

        _ensure_compatible_spaces(wrappers)
        training_environment = DummyVectorEnv([lambda env=item: env for item in wrappers])
        first_observation, _ = training_environment.reset()
        policy_observation = first_observation[0]
        buffer_num = len(wrappers)
    scheduler = _ppo_scheduler(config, buffer_num)
    if policy is None:
        policy = BuiltinPolicy(
            config.algorithm, _action_space(environments[0]), seed=config.seed,
            rnd=config.rnd, learning_rate=config.learning_rate,
            lr_scheduler_factory=scheduler,
        )
    policy._ensure(policy_observation)
    policy.train()
    algorithm = policy.algorithm_impl
    timestep = _run_native_training(
        algorithm, training_environment, config, buffer_num=buffer_num, rnd=policy._rnd
    )
    checkpoint = TrainingCheckpoint(
        config.algorithm, timestep, config.seed, asdict(config),
        algorithm_state=algorithm.state_dict(),
        normalization=policy.normalization,
        rnd_state=policy.rnd_state_dict(),
        provenance={
            "tianshou": TIANSHOU_VERSION,
            "algorithm_components": ALGORITHM_COMPONENTS[config.algorithm],
            "rnd_upstream": RND_UPSTREAM,
            "environment": bundle.manifest.environment,
            "task": bundle.manifest.task,
        },
    )
    if checkpoint_path is not None:
        checkpoint.save(checkpoint_path)
    return checkpoint


def train_manifest(
    entries: tuple[TaskManifestEntry, ...],
    environments: dict[str, object],
    config: TrainingConfig,
    *,
    checkpoint_path: str | Path | None = None,
) -> TrainingCheckpoint:
    """Train one native policy over independently wrapped task environments."""
    train_entries = tuple(entry for entry in entries if entry.split == "train")
    held_out = {entry.task_id for entry in entries if entry.split in {"heldout", "test", "eval"}}
    train_ids = {entry.task_id for entry in train_entries}
    if not train_entries:
        raise ValueError("Task manifest has no training entries")
    if config.algorithm == "ppo" and len(train_entries) != 4:
        raise ValueError("Manifest PPO runs require exactly four independent training entries")
    if train_ids & held_out:
        raise ValueError("Training and held-out task identities must be disjoint")
    from .artifacts import load_bundle
    from tianshou.env import DummyVectorEnv

    wrappers = []
    for entry in train_entries:
        if entry.task_id not in environments:
            raise ValueError(f"Missing environment for task {entry.task_id!r}")
        bundle = load_bundle(entry.bundle)
        bundle.validate(require_complete=True)
        env = RewardMachineEnvironment(
            environments[entry.task_id], RewardMachineRuntime(bundle.reward_machine), bundle.labeling_source,
        )
        wrappers.append(_embedded_environment(env, bundle.embeddings))
    _ensure_compatible_spaces(wrappers)
    vector_env = DummyVectorEnv([lambda env=env: env for env in wrappers])
    first_observation, _ = vector_env.reset()
    policy = BuiltinPolicy(
        config.algorithm, wrappers[0].action_space, seed=config.seed,
        rnd=config.rnd, learning_rate=config.learning_rate,
        lr_scheduler_factory=_ppo_scheduler(config, len(wrappers)),
    )
    policy._ensure(first_observation[0])
    policy.train()
    timestep = _run_native_training(
        policy.algorithm_impl, vector_env, config, buffer_num=len(wrappers), rnd=policy._rnd
    )
    checkpoint = TrainingCheckpoint(
        config.algorithm, timestep, config.seed, asdict(config),
        algorithm_state=policy.algorithm_impl.state_dict(), normalization=policy.normalization,
        rnd_state=policy.rnd_state_dict(),
        provenance={"tianshou": TIANSHOU_VERSION, "tasks": sorted(train_ids)},
    )
    if checkpoint_path is not None:
        checkpoint.save(checkpoint_path)
    return checkpoint


def load_builtin_policy(
    checkpoint: TrainingCheckpoint,
    environment: object,
    bundle: ArtifactBundle,
) -> "BuiltinPolicy":
    """Recreate and strictly restore the native algorithm for frozen evaluation."""
    config = TrainingConfig(**checkpoint.config)
    wrapped = _embedded_environment(
        RewardMachineEnvironment(
            environment, RewardMachineRuntime(bundle.reward_machine), bundle.labeling_source,
        ),
        bundle.embeddings,
    )
    observation, _ = wrapped.reset()
    policy = BuiltinPolicy(
        config.algorithm, _action_space(environment), seed=checkpoint.seed,
        rnd=config.rnd, learning_rate=config.learning_rate,
        lr_scheduler_factory=_ppo_scheduler(config, 4 if config.algorithm == "ppo" else 1),
    )
    policy._ensure(observation)
    policy.algorithm_impl.load_state_dict(dict(checkpoint.algorithm_state), strict=True)
    policy.normalization = dict(checkpoint.normalization)
    policy.load_rnd_state(checkpoint.rnd_state)
    policy.eval()
    return policy


class BuiltinPolicy:
    """Thin public wrapper around a native Tianshou algorithm/policy."""

    def __init__(self, algorithm: str, action_space: object, *, seed: int = 42,
                 rnd: bool = False, learning_rate: float = 1e-4,
                 lr_scheduler_factory: object | None = None) -> None:
        import torch

        if algorithm not in ALGORITHM_COMPONENTS:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        torch.manual_seed(seed)
        self.algorithm = algorithm
        self.action_space = action_space
        self.rnd_enabled = rnd
        self.learning_rate = learning_rate
        self.lr_scheduler_factory = lr_scheduler_factory
        self.training = True
        self.normalization: dict[str, Any] = {}
        self.algorithm_impl = None
        self._algorithm_impl = None
        self._rnd: RNDModule | None = None

    def _ensure(self, observation: Any) -> None:
        if self.algorithm_impl is not None:
            return
        self.algorithm_impl = _create_native_algorithm(
            self.algorithm, self.action_space, observation, self.learning_rate,
            lr_scheduler_factory=self.lr_scheduler_factory,
        )
        self._algorithm_impl = self.algorithm_impl
        if self.rnd_enabled:
            self._rnd = RNDModule(max(1, int(_observation_array(_raw_observation(observation)).size)))

    def train(self) -> None:
        self.training = True
        if self.algorithm_impl is not None:
            self.algorithm_impl.train()
        if self._rnd is not None:
            self._rnd.train(True)

    def eval(self) -> None:
        self.training = False
        if self.algorithm_impl is not None:
            self.algorithm_impl.eval()
        if self._rnd is not None:
            self._rnd.eval()

    def act(self, observation: Any, embedding: list[float] | tuple[float, ...], *, explore: bool) -> Any:
        import torch
        from tianshou.data import Batch
        from tianshou.utils.torch_utils import policy_within_training_step

        packed = {"observation": observation, "embedding": list(embedding)}
        self._ensure(packed)
        if hasattr(self.algorithm_impl.policy, "set_eps_inference"):
            self.algorithm_impl.policy.set_eps_inference(0.0)
        context = policy_within_training_step(self.algorithm_impl.policy) if explore else _null_context()
        with torch.no_grad(), context:
            result = self.algorithm_impl.policy(
                Batch(obs={"observation": [observation], "embedding": [list(embedding)]}, info={})
            )
        action = result.act
        value = action[0] if hasattr(action, "__len__") else action
        return value.detach().cpu().numpy() if hasattr(value, "detach") and getattr(value, "ndim", 0) else (
            value.item() if hasattr(value, "item") else value
        )

    def state_dict(self) -> dict[str, Any]:
        self._require_algorithm()
        return self.algorithm_impl.state_dict()

    def rnd_state_dict(self) -> dict[str, Any] | None:
        return self._rnd.state_dict_with_optimizer() if self._rnd is not None else None

    def load_rnd_state(self, state: dict[str, Any] | None) -> None:
        if state is None:
            return
        if self._rnd is None:
            raise ValueError("Checkpoint contains RND state but policy has no RND module")
        self._rnd.load_state_dict(state["module"], strict=True)
        self._rnd.optimizer.load_state_dict(state["optimizer"])

    def _require_algorithm(self):
        if self.algorithm_impl is None:
            raise RuntimeError("Policy has not been initialized with an environment observation")


def _import_sac():
    from tianshou.algorithm.modelfree.sac import SAC
    return SAC


class PeriodicSAC(_import_sac()):
    """Native SAC math with critic updates every step and actor every second step."""

    def __init__(self, **kwargs):
        import torch

        super().__init__(**kwargs)
        self.register_buffer("arm_actor_update_count", torch.zeros((), dtype=torch.long))

    def _update_with_batch(self, batch):
        import torch
        from tianshou.algorithm.modelfree.sac import SACTrainingStats
        from tianshou.utils.conversion import to_optional_float

        td1, critic1_loss = self._minimize_critic_squared_loss(batch, self.critic, self.critic_optim)
        td2, critic2_loss = self._minimize_critic_squared_loss(batch, self.critic2, self.critic2_optim)
        batch.weight = (td1 + td2) / 2.0
        self.arm_actor_update_count.add_(1)
        actor_loss = torch.zeros((), device=critic1_loss.device)
        alpha_loss = None
        if int(self.arm_actor_update_count.item()) % 2 == 0:
            obs_result = self.policy(batch)
            current_q1a = self.critic(batch.obs, obs_result.act).flatten()
            current_q2a = self.critic2(batch.obs, obs_result.act).flatten()
            actor_loss = (self.alpha.value * obs_result.log_prob.flatten() - torch.min(current_q1a, current_q2a)).mean()
            self.policy_optim.step(actor_loss)
            alpha_loss = self.alpha.update(-obs_result.log_prob.detach())
        self._update_lagged_network_weights()
        return SACTrainingStats(
            actor_loss=float(actor_loss.detach().cpu()), critic1_loss=critic1_loss.item(),
            critic2_loss=critic2_loss.item(), alpha=to_optional_float(self.alpha.value),
            alpha_loss=to_optional_float(alpha_loss),
        )


def _create_native_algorithm(
    algorithm: str,
    action_space: object,
    observation: Any,
    learning_rate: float,
    *,
    lr_scheduler_factory: object | None = None,
):
    import gymnasium as gym
    from tianshou.algorithm.optim import AdamOptimizerFactory
    from tianshou.algorithm.modelfree.c51 import C51Policy
    from tianshou.algorithm.modelfree.dqn import DiscreteQLearningPolicy
    from tianshou.utils.net.discrete import DiscreteActor, DiscreteCritic

    optimizer = AdamOptimizerFactory(lr=learning_rate)
    if lr_scheduler_factory is not None:
        optimizer.with_lr_scheduler_factory(lr_scheduler_factory)
    if hasattr(action_space, "n"):
        action_space = gym.spaces.Discrete(int(action_space.n))
        if algorithm == "rainbow":
            model = _DiscreteNet(observation, action_space.n, 51, dueling=True)
            policy = C51Policy(model=model, action_space=action_space, num_atoms=51,
                               v_min=-10.0, v_max=10.0, eps_training=1.0, eps_inference=0.0)
            from tianshou.algorithm import RainbowDQN
            return RainbowDQN(policy=policy, optim=optimizer, gamma=0.99,
                              n_step_return_horizon=3, target_update_freq=5_000)
        if algorithm == "dqn":
            model = _DiscreteNet(observation, action_space.n, 1, dueling=False)
            policy = DiscreteQLearningPolicy(model=model, action_space=action_space,
                                              eps_training=1.0, eps_inference=0.0)
            from tianshou.algorithm import DQN
            return DQN(policy=policy, optim=optimizer, gamma=0.99,
                       target_update_freq=2_500, is_double=False)
        if algorithm != "ppo":
            raise ValueError(f"Algorithm {algorithm!r} requires a continuous action space")
        from tianshou.algorithm import PPO
        from tianshou.algorithm.modelfree.reinforce import DiscreteActorPolicy
        actor = DiscreteActor(preprocess_net=_ArmEncoder(observation), action_shape=action_space.n)
        critic = DiscreteCritic(preprocess_net=_ArmEncoder(observation))
        policy = DiscreteActorPolicy(actor=actor, action_space=action_space, deterministic_eval=True)
        return PPO(policy=policy, critic=critic, optim=optimizer, gamma=0.99,
                   gae_lambda=0.95, eps_clip=0.1, max_grad_norm=0.5,
                   value_clip=True, ent_coef=0.01, vf_coef=0.5,
                   max_batchsize=128, advantage_normalization=True)

    action_size = int(math.prod(getattr(action_space, "shape", (1,))))
    import gymnasium as gym
    space = gym.spaces.Box(-1.0, 1.0, shape=(action_size,), dtype="float32")
    if algorithm == "ppo":
        from tianshou.algorithm import PPO
        from tianshou.algorithm.modelfree.reinforce import ProbabilisticActorPolicy
        from tianshou.utils.net.continuous import ContinuousActorProbabilistic
        actor = ContinuousActorProbabilistic(preprocess_net=_ArmEncoder(observation), action_shape=action_size)
        policy = ProbabilisticActorPolicy(actor=actor, action_space=space, action_scaling=False,
                                          action_bound_method=None, dist_fn=_normal_distribution,
                                          deterministic_eval=True)
        return PPO(policy=policy, critic=_ArmValue(observation), optim=optimizer, gamma=0.99,
                   gae_lambda=0.95, eps_clip=0.1, max_grad_norm=0.5,
                   value_clip=True, ent_coef=0.01, vf_coef=0.5,
                   max_batchsize=128, advantage_normalization=True)
    if algorithm != "sac":
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    from tianshou.algorithm.modelfree.sac import SACPolicy
    from tianshou.utils.net.continuous import ContinuousActorProbabilistic
    actor = ContinuousActorProbabilistic(preprocess_net=_ArmEncoder(observation), action_shape=action_size)
    policy = SACPolicy(actor=actor, action_space=space, action_scaling=False, deterministic_eval=True)
    return PeriodicSAC(
        policy=policy, policy_optim=optimizer, critic=_ArmCritic(observation, action_size),
        critic_optim=AdamOptimizerFactory(lr=learning_rate), critic2=_ArmCritic(observation, action_size),
        critic2_optim=AdamOptimizerFactory(lr=learning_rate), gamma=0.99, tau=0.005, alpha=0.2,
    )


def _run_native_training(algorithm, environment, config: TrainingConfig, *, buffer_num: int = 1, rnd=None) -> int:
    from tianshou.data import Collector, PrioritizedVectorReplayBuffer, VectorReplayBuffer
    from tianshou.env import DummyVectorEnv
    from tianshou.trainer import OffPolicyTrainer, OffPolicyTrainerParams, OnPolicyTrainer, OnPolicyTrainerParams

    if not hasattr(environment, "__len__"):
        environment = DummyVectorEnv([lambda: environment])
        buffer_num = 1
    if config.algorithm == "ppo" and buffer_num != 4:
        raise ValueError("Native PPO requires exactly four environment lanes")
    if config.algorithm == "rainbow":
        buffer = PrioritizedVectorReplayBuffer(total_size=config.replay_capacity, buffer_num=buffer_num,
                                               alpha=0.5, beta=0.4)
    else:
        buffer = VectorReplayBuffer(config.replay_capacity, buffer_num)
    def on_step(_action_batch, rollout_batch):
        if rnd is None:
            return
        pairs = _observation_pairs(rollout_batch.obs_next)
        raw = [item[0] for item in pairs]
        if config.rnd_coefficient:
            import numpy as np

            bonus = np.asarray([rnd.reward(value) for value in raw], dtype=np.float32)
            rollout_batch.rew = rollout_batch.rew + config.rnd_coefficient * bonus
        rnd.update(raw)

    collector = Collector(algorithm, environment, buffer, on_step_hook=on_step if rnd is not None else None)
    collector.reset()
    total = config.total_timesteps
    warmup_steps = 0
    if config.algorithm == "ppo":
        rollout_length = 128
        collection_steps = buffer_num * rollout_length
        params = OnPolicyTrainerParams(
            max_epochs=1, epoch_num_steps=total,
            training_collector=collector, collection_step_num_env_steps=collection_steps,
            batch_size=128, update_step_num_repetitions=4,
            verbose=False, show_progress=False,
        )
        OnPolicyTrainer(algorithm, params).run(reset_collectors=False)
    else:
        requested_warmup = min(max(0, config.learning_starts), total)
        if requested_warmup:
            warmup = collector.collect(n_step=requested_warmup, random=True)
            warmup_steps = int(warmup.n_collected_steps)
        remaining = max(0, total - warmup_steps)
        if not remaining:
            return int(getattr(collector, "collect_step", warmup_steps))
        frequency = max(1, config.train_frequency or 1)
        collect_steps = min(remaining, frequency)
        ratio = 1.0 / collect_steps

        def schedule(_epoch, env_step):
            start = config.epsilon_start
            end = config.epsilon_end
            fraction = config.epsilon_fraction
            absolute_step = warmup_steps + env_step
            if (
                hasattr(algorithm.policy, "set_eps_training")
                and start is not None
                and end is not None
                and fraction is not None
                and config.exploration
            ):
                horizon = max(1.0, total * fraction)
                progress = min(1.0, float(absolute_step) / horizon)
                algorithm.policy.set_eps_training(start + progress * (end - start))
            _set_learning_rate(algorithm, config.learning_rate, absolute_step / max(1, total))

        params = OffPolicyTrainerParams(
            max_epochs=1, epoch_num_steps=remaining, training_collector=collector,
            collection_step_num_env_steps=collect_steps, batch_size=config.batch_size,
            update_step_num_gradient_steps_per_sample=ratio, training_fn=schedule,
            verbose=False, show_progress=False,
        )
        OffPolicyTrainer(algorithm, params).run(reset_collectors=False)
    return int(getattr(collector, "collect_step", warmup_steps))


def _set_learning_rate(algorithm: object, initial: float, progress: float) -> None:
    """Linearly advance off-policy optimizer progress after random warmup."""
    import torch

    rate = initial * max(0.0, 1.0 - min(1.0, progress))
    for value in vars(algorithm).values():
        if isinstance(value, torch.optim.Optimizer):
            for group in value.param_groups:
                group["lr"] = rate


def _ppo_scheduler(config: TrainingConfig, buffer_num: int):
    if config.algorithm != "ppo":
        return None
    from tianshou.algorithm.optim import LRSchedulerFactoryLinear

    return LRSchedulerFactoryLinear(1, config.total_timesteps, buffer_num * 128)


def _explicit_rnd_variant(domain: str) -> bool:
    """Enable RND only for a domain name that explicitly opts into it."""
    return "rnd" in domain.lower().replace("_", "-").split("-")


class _EmbeddedEnvironment:
    def __init__(self, environment: RewardMachineEnvironment, embeddings: dict[str, list[float]]) -> None:
        self.environment, self.embeddings = environment, embeddings
        self.action_space = getattr(environment, "action_space", type("Discrete", (), {"n": 1})())
        self.observation_space = getattr(environment, "observation_space", None)
        self.unwrapped = self

    def reset(self, **kwargs):
        result = self.environment.reset(**kwargs)
        observation = result[0] if isinstance(result, tuple) else result
        info = result[1] if isinstance(result, tuple) and len(result) > 1 else {}
        return self._pack(observation, self.environment.runtime.state), info

    def step(self, action):
        result = self.environment.step(action)
        if len(result) == 5:
            observation, reward, terminated, truncated, info = result
        else:
            observation, reward, terminated, info = result
            truncated = False
        state = dict(info or {}).get("rm_state", self.environment.runtime.state)
        return self._pack(observation, state), reward, terminated, truncated, info

    def _pack(self, observation, state):
        return {"observation": observation, "embedding": list(self.embeddings[state])}

    def __getattr__(self, name):
        return getattr(self.environment, name)


def _embedded_environment(environment, embeddings):
    return _EmbeddedEnvironment(environment, embeddings)


class _DiscreteNet(__import__("torch").nn.Module):
    def __init__(self, sample, action_count: int, atoms: int, *, dueling: bool) -> None:
        import torch
        super().__init__()
        from tianshou.utils.net.common import Net
        from tianshou.utils.net.discrete import NoisyLinear

        self.encoder = _ArmEncoder(sample)
        dueling_param = (
            {"hidden_sizes": (128,), "linear_layer": NoisyLinear},
            {"hidden_sizes": (128,), "linear_layer": NoisyLinear},
        ) if dueling else None
        self.net = Net(
            state_shape=self.encoder.output_dim, action_shape=action_count, hidden_sizes=(128,),
            num_atoms=atoms, softmax=atoms > 1, dueling_param=dueling_param,
            linear_layer=NoisyLinear if dueling else torch.nn.Linear,
        )

    def __call__(self, obs, state=None, info=None):
        features, _ = self.encoder(obs, state, info)
        return self.net(features, state, info)

    def parameters(self):
        return list(self.encoder.parameters()) + list(self.net.parameters())


class _ArmEncoder(__import__("torch").nn.Module):
    def __init__(self, sample: Any) -> None:
        super().__init__()
        self._module = _EncoderModule(sample)

    def forward(self, obs, state=None, info=None):
        return self._module(obs), state

    def get_output_dim(self):
        return self._module.output_dim

    @property
    def output_dim(self):
        return self._module.output_dim


class _EncoderModule(__import__("torch").nn.Module):
    def __init__(self, sample: Any) -> None:
        import torch
        from torch import nn

        super().__init__()
        raw = _raw_observation(sample)
        array = _observation_array(raw)
        self.spatial = array.ndim >= 3
        if self.spatial:
            if array.shape[0] <= 4:
                channels, height, width = array.shape[0], array.shape[1], array.shape[2]
            else:
                height, width, channels = array.shape[0], array.shape[1], array.shape[2]
            self.channels = channels
            self.network = nn.Sequential(
                nn.Conv2d(channels, 16, 3, padding=1), nn.ReLU(),
                nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.ReLU(), nn.Flatten(),
            )
            with torch.no_grad():
                base = int(self.network(torch.zeros(1, channels, height, width)).shape[-1])
        else:
            base = max(1, int(array.size))
            self.network = nn.Sequential(nn.Flatten(), nn.Linear(base, 128), nn.ReLU())
            base = 128
        self.embedding_size = max(1, int(_embedding_array(sample).size))
        self.embedding = nn.Sequential(nn.Linear(self.embedding_size, 32), nn.ReLU())
        self.output_dim = base + 32

    def forward(self, observations):
        import torch

        features = []
        for raw, embedding in _observation_pairs(observations):
            encoded = self.network(_observation_tensor(raw, self.spatial, getattr(self, "channels", None)))
            emb = torch.as_tensor(embedding, dtype=torch.float32).reshape(1, -1)
            features.append(torch.cat((encoded, self.embedding(emb)), dim=1).squeeze(0))
        return torch.stack(features)


class _ArmValue(__import__("torch").nn.Module):
    def __init__(self, sample):
        import torch
        from torch import nn

        super().__init__()
        self.encoder = _EncoderModule(sample)
        self.value = nn.Linear(self.encoder.output_dim, 1)

    def forward(self, obs, state=None, info=None):
        return self.value(self.encoder(obs))


class _ArmCritic(__import__("torch").nn.Module):
    def __init__(self, sample, action_size: int):
        import torch
        from torch import nn

        super().__init__()
        self.encoder = _EncoderModule(sample)
        self.value = nn.Sequential(
            nn.Linear(self.encoder.output_dim + action_size, 128), nn.ReLU(), nn.Linear(128, 1)
        )

    def forward(self, obs, act=None, info=None):
        import torch

        features = self.encoder(obs)
        if act is None:
            act = torch.zeros((features.shape[0], self.value[0].in_features - features.shape[1]), device=features.device)
        action = torch.as_tensor(act, dtype=features.dtype, device=features.device).reshape(features.shape[0], -1)
        return self.value(torch.cat((features, action), dim=1))


class RNDModule(__import__("torch").nn.Module):
    """Small attributed RLeXplore-style RND adaptation."""

    def __init__(self, input_size: int) -> None:
        import torch
        from torch import nn

        super().__init__()
        self.target = nn.Sequential(nn.Linear(input_size, 64), nn.ReLU(), nn.Linear(64, 32))
        self.predictor = nn.Sequential(nn.Linear(input_size, 64), nn.ReLU(), nn.Linear(64, 32))
        self.optimizer = torch.optim.Adam(self.predictor.parameters(), lr=1e-4)
        for parameter in self.target.parameters():
            parameter.requires_grad_(False)
        self.eval()

    def train(self, mode: bool = True):
        super().train(mode)
        self.target.eval()
        for parameter in self.target.parameters():
            parameter.requires_grad_(False)
        return self

    def update(self, observations: Any) -> float:
        import torch

        if not self.training:
            raise RuntimeError("RND predictor updates are disabled during evaluation")
        values = torch.stack([_flat_tensor(value) for value in observations])
        prediction = self.predictor(values)
        with torch.no_grad():
            target = self.target(values)
        loss = (prediction - target).square().mean()
        self.optimizer.zero_grad(); loss.backward(); self.optimizer.step()
        return float(loss.detach().cpu())

    def reward(self, observation: Any) -> float:
        import torch

        with torch.no_grad():
            value = _flat_tensor(observation).unsqueeze(0)
            return float((self.predictor(value) - self.target(value)).square().mean())

    def state_dict_with_optimizer(self) -> dict[str, Any]:
        return {"module": self.state_dict(), "optimizer": self.optimizer.state_dict()}


def _action_space(environment):
    return getattr(environment, "action_space", type("Discrete", (), {"n": 1})())


def _observation_pairs(observations):
    import numpy as np

    if hasattr(observations, "observation") and hasattr(observations, "embedding"):
        raw, embedding = observations.observation, observations.embedding
    elif isinstance(observations, dict) and {"observation", "embedding"} <= observations.keys():
        raw, embedding = observations["observation"], observations["embedding"]
    else:
        raise ValueError("ARM-FM observations must contain observation and embedding")
    embedding_array = np.asarray(embedding, dtype=object)
    if embedding_array.ndim < 2:
        return [(raw, embedding)]
    return [(_index_batch(raw, i), embedding[i]) for i in range(len(embedding))]


def _index_batch(value, index):
    if isinstance(value, dict):
        return {key: _index_batch(item, index) for key, item in value.items()}
    try:
        return value[index]
    except (IndexError, KeyError, TypeError):
        return value


def _raw_observation(value):
    if isinstance(value, dict) and "observation" in value:
        return value["observation"]
    if hasattr(value, "observation"):
        return value.observation
    return value


def _embedding_array(value):
    import numpy as np

    if isinstance(value, dict):
        value = value.get("embedding", [0.0])
    elif hasattr(value, "embedding"):
        value = value.embedding
    return np.asarray(value, dtype=np.float32).reshape(-1)


def _observation_array(value):
    import numpy as np

    if isinstance(value, dict):
        values = []
        for item in value.values():
            array = np.asarray(item)
            if np.issubdtype(array.dtype, np.number):
                values.append(array.astype(np.float32).reshape(-1))
        return np.concatenate(values) if values else np.zeros(1, dtype=np.float32)
    return np.asarray(value, dtype=np.float32)


def _observation_tensor(value, spatial: bool, channels: int | None):
    import numpy as np
    import torch

    array = _observation_array(value).astype(np.float32)
    if spatial:
        if array.ndim == 3 and array.shape[0] != channels:
            array = np.moveaxis(array, -1, 0)
        return torch.as_tensor(array).unsqueeze(0)
    return torch.as_tensor(array).reshape(1, -1)


def _flat_tensor(value):
    import torch

    return torch.as_tensor(_observation_array(value), dtype=torch.float32).reshape(-1)


def _normal_distribution(values):
    import torch

    loc, scale = values
    return torch.distributions.Independent(torch.distributions.Normal(loc, scale), 1)


def _space_signature(space):
    if space is None:
        return None
    def values(name):
        value = getattr(space, name, None)
        return value.tolist() if hasattr(value, "tolist") else value

    return (
        type(space).__name__, getattr(space, "shape", None), getattr(space, "n", None),
        values("low"), values("high"),
    )


def _ensure_compatible_spaces(environments) -> None:
    action = _space_signature(environments[0].action_space)
    observation = _space_signature(environments[0].observation_space)
    for environment in environments[1:]:
        if _space_signature(environment.action_space) != action or _space_signature(environment.observation_space) != observation:
            raise ValueError("Manifest task environments must have compatible spaces")


class _null_context:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False
