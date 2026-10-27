"""Project configuration from CLI arguments and environment variables."""

import os
from dataclasses import dataclass, field, fields
from enum import StrEnum
from pathlib import Path
from types import UnionType
from typing import ClassVar, get_args
from urllib.parse import urlparse

import yaml
from maikol_utils.file_utils import make_dirs

LLM_PROVIDERS = ("openai", "opencode", "antigravity")
# One level for the generator and the critic; each provider adapter maps it to its own option.
REASONING_LEVELS = ("none", "low", "medium", "high", "max")
DEFAULT_LLAMA_SERVER_PORT = "8934"


class PriorityLevel(StrEnum):
    """How a task clause is enforced: ``hard`` shapes the machine, ``soft`` only its rewards."""

    HARD = "hard"
    SOFT = "soft"


def _optional_path(value: Path | str | None) -> Path | None:
    return Path(value) if value is not None else None


def _numeric_type(annotation: object) -> type | None:
    # `int | None` and `float | None` fields are numeric too.
    options = get_args(annotation) if isinstance(annotation, UnionType) else (annotation,)
    return next((option for option in options if option in (int, float)), None)


def _coerce_number(numeric_type: type, value: object) -> int | float:
    # bool is an int subclass, so `true` would silently become 1.
    if isinstance(value, bool):
        raise TypeError(f"expected a number, got {value!r}")
    if numeric_type is float:
        return float(value)
    if isinstance(value, int):
        return value

    # Accept `3e5` or `3.0e5`, but never truncate a fraction such as 2.7.
    number = float(value)
    if not number.is_integer():
        raise ValueError(f"expected an integer, got {value!r}")
    return int(number)


ALGORITHMS = ("dqn", "ppo")
SUCCESS_MODES = ("env", "rm")
REWARD_SOURCES = ("rm", "env", "both")
TASK_BUNDLE_KEYS = ("bundle", "labeling_bundle", "env_kwargs", "success")
PPO_POSITIVE = (
    "ppo_num_envs",
    "ppo_num_steps",
    "ppo_num_minibatches",
    "ppo_update_epochs",
    "ppo_learning_rate",
    "ppo_max_grad_norm",
    "ppo_clip_coef",
)
PPO_NON_NEGATIVE = ("ppo_ent_coef", "ppo_vf_coef")
PPO_NUMBERS = (*PPO_POSITIVE, *PPO_NON_NEGATIVE, "ppo_gae_lambda")
PPO_FLAGS = ("ppo_anneal_lr", "ppo_clip_vloss", "ppo_norm_adv")


def _is_finite_number(value: object) -> bool:
    # NaN fails the comparison too, and bool is not a setting value.
    return (
        isinstance(value, int | float) and not isinstance(value, bool) and abs(value) < float("inf")
    )


def _check_env_kwargs(value: object, where: str) -> None:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{where} must be a mapping with string keys")


def _check_removed_keys(yaml_data: dict, config_path: Path) -> None:
    """Name the replacement of ``use_rm``, which a bare unknown-key error would not."""
    if "use_rm" in yaml_data:
        raise ValueError(
            f"{config_path}: use_rm was replaced by reward_source "
            f"({', '.join(REWARD_SOURCES)}); use_rm: false is reward_source: env"
        )


def _task_bundle(entry: object, index: int) -> dict:
    """Validate one ``task_bundles`` entry and convert its bundle paths to ``Path``."""
    where = f"task_bundles[{index}]"
    if not isinstance(entry, dict):
        raise ValueError(f"{where} must be a mapping")
    unknown = sorted(str(key) for key in entry.keys() - set(TASK_BUNDLE_KEYS))
    if unknown:
        raise ValueError(f"Unknown keys in {where}: {', '.join(unknown)}")
    if entry.get("bundle") is None:
        raise ValueError(f"{where} needs a bundle")
    if entry.get("success", "env") not in SUCCESS_MODES:
        raise ValueError(f"{where}.success must be one of {', '.join(SUCCESS_MODES)}")
    _check_env_kwargs(entry.get("env_kwargs", {}), f"{where}.env_kwargs")

    converted = dict(entry)
    for key in ("bundle", "labeling_bundle"):
        if converted.get(key) is not None:
            converted[key] = Path(converted[key])
    return converted


# ================================ Graph defaults ================================


@dataclass(frozen=True)
class GraphStyle:
    """Sizing for rendered Reward Machine graphs, in SVG user units.

    Shared by the web graph export and the render_rm script. ``margin`` and
    ``arc_room`` are the blank space kept around the drawing; lower them for a
    tighter picture and raise them if labels feel crowded.

    States are circles of ``node_diameter`` that flow top to bottom in layers:
    ``node_gap`` is the least horizontal distance between two states in a layer
    and ``layer_gap`` spaces the layers. An edge label sits on a chip ``label_height``
    tall and ``label_padding`` plus ``label_char_width`` per character wide.
    """

    node_diameter: int = 64
    node_gap: int = 130  # least horizontal distance between states in a layer
    layer_gap: int = 120  # vertical spacing between layers
    margin: int = 60  # blank space around the drawing
    arc_room: int = 48  # extra right-side room for self-loops
    label_height: int = 18
    label_char_width: float = 6.2
    label_padding: int = 12

    def label_width(self, text: str) -> float:
        """Return the width of the label chip for ``text``."""
        return len(text) * self.label_char_width + self.label_padding


@dataclass
class Configuration:
    """Project settings: CLI options, an optional YAML run config, and the output folders."""

    # ======================================================================================
    #                                      PATHS
    # ======================================================================================

    WORKSPACE_PATH: ClassVar[Path] = Path(__file__).resolve().parents[3]
    DATA_PATH: ClassVar[Path] = WORKSPACE_PATH / "data"
    OUTPUT_PATH: ClassVar[Path] = WORKSPACE_PATH / "outputs"
    RM_PATH: ClassVar[Path] = OUTPUT_PATH / "RMs"
    TRACE_PATH: ClassVar[Path] = OUTPUT_PATH / "traces"
    REPORT_PATH: ClassVar[Path] = OUTPUT_PATH / "reports"
    MODELS_PATH: ClassVar[Path] = WORKSPACE_PATH / "models"
    CONFIG_PATH: ClassVar[Path] = WORKSPACE_PATH / "configs"
    LOGS_PATH: ClassVar[Path] = WORKSPACE_PATH / "logs"
    EMBEDDINGS_PATH: ClassVar[Path] = MODELS_PATH / "state_embeddings"

    # ======================================================================================
    #                                   REWARD MACHINE
    # ======================================================================================

    # Each candidate gets this many tagging requests. Only a critic rejection uses one of
    # ``attempts``; a provider or content failure reruns the attempt, at most this many times.
    TAGGING_ATTEMPTS: ClassVar[int] = 3
    UNCOUNTED_RETRIES: ClassVar[int] = 10
    ATTEMPT_LIMITS: ClassVar[range] = range(1, 11)
    # The provider sometimes answers HTTP 400 at random; the same call is repeated this many
    # times, this far apart, before it counts as a failure. Repeats use no proposal attempt.
    # A repeat uses a new provider session, because OpenCode's 400 sticks to the session.
    PROVIDER_RETRIES: ClassVar[int] = 10
    PROVIDER_RETRY_WAIT_S: ClassVar[float] = 1.0
    MAX_TASK_CLAUSES: ClassVar[int] = 25
    # Paid per step closer to the final state, measured on the longest remaining path.
    PROGRESS_REWARD: ClassVar[float] = 0.1
    TASK_COMPLETION_REWARD: ClassVar[float] = 1.0
    WELL_REWARD: ClassVar[float] = -1.0
    # Soft clauses: paid when one breaks, and on the finishing edge when one is still pending.
    SOFT_BREAK_REWARD: ClassVar[float] = -0.5
    SOFT_PENDING_AT_FINISH_REWARD: ClassVar[float] = -0.5
    # Added to the RM reward on the step where the time limit ends an episode the RM did not.
    TIME_LIMIT_PENALTY: ClassVar[float] = -0.5
    # A machine with no final state is judged where the environment ends an episode: each hard
    # and soft promise still open pays one of these, instead of TIME_LIMIT_PENALTY.
    HARD_FAILED_REWARD: ClassVar[float] = -1.0
    SOFT_FAILED_REWARD: ClassVar[float] = -0.5

    # ============================== Runtime options ==============================

    environment: Path | None = None
    tasks: list[str] = field(default_factory=list)
    output: Path | None = None
    llm_provider: str | None = None
    model: str | None = None
    generator_model: str | None = None
    critic_model: str | None = None
    judge_model: str = "Qwen3-30B-A3B-Instruct-2507"
    mona_executable: str | None = None
    overwrite: bool = False
    critic: bool = True
    # A soft rule's -0.5 is paid at every new break (on) or once per episode (off).
    recurrent_soft_penalty: bool = True
    reasoning: str = "none"
    attempts: int = 3
    labeling: bool = False
    state_descriptions: bool = True
    embeddings: bool = False
    # None means the local llama-server on LLAMA_SERVER_PORT; see llama_server_command.
    embedding_endpoint: str | None = None
    embedding_model: str = "nomic-embed-text"
    embedding_revision: str = (
        "sha256:970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6"
    )
    embedding_context: bool = False
    embedding_timeout: float = 30.0
    svg: bool = False
    svg_dir: Path | None = None
    html: bool = False  # render-rm: also write an interactive .html beside each SVG
    steps_report: Path | None = None
    trace_dir: Path | None = None
    seed: int = 42
    mode: str = "arm-fm"
    bundle: Path | None = None
    manifests: list[Path] = field(default_factory=list)
    domain: str | None = None
    task_manifest: Path | None = None
    rm_file: Path | None = None
    reference: Path | None = None  # import-paper-bundle: clone of the authors' repository
    paper_env: str | None = None  # import-paper-bundle: released environment name
    paper_sources: Path | None = None  # generate-larm --mode paper: its paper-sources.json
    draws: int = 3  # generate-larm --mode paper: independent generations

    # ============================== Training (train-rl) ==============================
    # A YAML run config overrides these; defaults follow ARM-FM Table 5.

    yaml_config_name: str | None = None
    exp_name: str = "dqn"
    gym_id: str | None = None
    env_family: str = "minigrid"
    observation: str = "symbolic"
    layout: str = "fixed"
    layout_seed: int | None = None  # None means the run seed
    labeling_bundle: Path | None = None
    # The learner's reward: ``rm`` the RM reward alone, ``both`` environment + RM reward, ``env``
    # the plain environment with no RM. The flag is run-wide.
    reward_source: str = "rm"
    env_kwargs: dict = field(default_factory=dict)  # keyword arguments of gym.make
    algorithm: str = "dqn"
    # Which rule counts an episode as a success: the environment's own (``env``) or RM
    # acceptance (``rm``).
    success: str = "env"
    # Several tasks in one run: entries of ``bundle`` plus optional ``labeling_bundle``,
    # ``env_kwargs`` and ``success``. Mutually exclusive with ``bundle``.
    task_bundles: list[dict] = field(default_factory=list)

    total_timesteps: int = 300_000
    learning_rate: float = 1e-4
    buffer_size: int = 1_000_000
    gamma: float = 0.99
    tau: float = 1.0
    target_network_frequency: int = 2_500
    batch_size: int = 32
    start_e: float = 1.0
    end_e: float = 0.01
    exploration_fraction: float = 0.35
    learning_starts: int = 80_000
    train_frequency: int = 4

    eval_frequency: int = 10_000
    eval_episodes: int = 10
    final_eval_episodes: int = 100
    eval_epsilon: float = 0.0
    eval_seed_base: int = 1_000_000
    success_threshold: float = 0.9
    cuda: bool = True
    torch_deterministic: bool = True

    # PPO (ARM-FM Table 6); ``gamma`` is shared with DQN.
    ppo_num_envs: int = 4
    ppo_num_steps: int = 128
    ppo_num_minibatches: int = 4
    ppo_update_epochs: int = 4
    ppo_learning_rate: float = 5e-5
    ppo_anneal_lr: bool = True
    ppo_max_grad_norm: float = 0.5
    ppo_gae_lambda: float = 0.95
    ppo_clip_coef: float = 0.1
    ppo_clip_vloss: bool = True
    ppo_norm_adv: bool = True
    ppo_ent_coef: float = 0.01
    ppo_vf_coef: float = 0.5

    def __post_init__(self) -> None:
        # The YAML loads first so its path values get the same Path conversion.
        if self.yaml_config_name:
            self._load_yaml_configuration(self.yaml_config_name)
        self._resolve_paths()
        self._validate_training()
        self._resolve_models()
        self._validate_embeddings()
        self._validate_generation()

    def _load_yaml_configuration(self, yaml_file: str) -> None:
        """Set fields from a YAML run config under CONFIG_PATH, or from an existing path.

        The YAML is applied in ``__post_init__``, so it overrides constructor and CLI values for
        the same fields (YAML wins). ``seed`` is CLI-only and rejected here. Only dataclass
        fields are accepted, and a field whose type excludes ``None`` needs a value. Numeric
        fields are coerced because YAML reads ``1e-4`` and ``3e5`` (no dot) as strings.

        Raises:
            ValueError: If the root is not a mapping, a key is unknown or ``seed``, or a value
                does not fit its field. The message names the file.
        """
        config_path = self.CONFIG_PATH / yaml_file
        if not config_path.is_file():
            config_path = Path(yaml_file)
        with config_path.open(encoding="utf-8") as file:
            yaml_data = yaml.safe_load(file)

        if yaml_data is None:  # empty file
            yaml_data = {}
        if not isinstance(yaml_data, dict):
            raise ValueError(f"{config_path} must be a YAML mapping")

        _check_removed_keys(yaml_data, config_path)
        field_types = {item.name: item.type for item in fields(self)}
        unknown = sorted(str(key) for key in yaml_data.keys() - field_types.keys())
        if unknown:
            raise ValueError(f"Unknown keys in {config_path}: {', '.join(unknown)}")
        if "seed" in yaml_data:
            raise ValueError(f"{config_path} must not set seed; pass --seed instead")

        for key, value in yaml_data.items():
            annotation = field_types[key]
            if value is None and type(None) not in get_args(annotation):
                raise ValueError(f"{config_path}: {key} needs a value")

            numeric_type = _numeric_type(annotation)
            if value is None or numeric_type is None:
                setattr(self, key, value)
                continue
            try:
                number = _coerce_number(numeric_type, value)
            except (TypeError, ValueError) as error:
                raise ValueError(f"{config_path}: invalid {key}: {error}") from error
            setattr(self, key, number)

    def _resolve_paths(self) -> None:
        # Keep every derived output folder under the configured root.
        output_root = Path(self.OUTPUT_PATH)
        self.RM_PATH = output_root / "RMs"
        self.TRACE_PATH = output_root / "traces"
        self.REPORT_PATH = output_root / "reports"
        self.EMBEDDINGS_PATH = Path(self.MODELS_PATH) / "state_embeddings"
        make_dirs(
            [
                self.DATA_PATH,
                self.OUTPUT_PATH,
                self.RM_PATH,
                self.TRACE_PATH,
                self.REPORT_PATH,
                self.MODELS_PATH,
                self.LOGS_PATH,
                self.EMBEDDINGS_PATH,
            ]
        )

        self.environment = _optional_path(self.environment)
        self.output = _optional_path(self.output)
        if self.output is not None and self.output.name != str(self.output):
            raise ValueError("--output must be a file name without a directory")
        self.bundle = _optional_path(self.bundle)
        self.labeling_bundle = _optional_path(self.labeling_bundle)
        self.task_manifest = _optional_path(self.task_manifest)
        self.rm_file = _optional_path(self.rm_file)
        self.reference = _optional_path(self.reference)
        self.paper_sources = _optional_path(self.paper_sources)
        self.steps_report = _optional_path(self.steps_report)
        self.trace_dir = _optional_path(self.trace_dir)
        self.manifests = [Path(path) for path in self.manifests]
        self.svg_dir = Path(self.svg_dir) if self.svg_dir is not None else self.OUTPUT_PATH / "svgs"

    def _validate_training(self) -> None:
        if self.algorithm not in ALGORITHMS:
            raise ValueError(
                f"algorithm must be one of {', '.join(ALGORITHMS)}: {self.algorithm!r}"
            )
        if self.success not in SUCCESS_MODES:
            raise ValueError(f"success must be one of {', '.join(SUCCESS_MODES)}: {self.success!r}")
        if self.reward_source not in REWARD_SOURCES:
            raise ValueError(
                f"reward_source must be one of {', '.join(REWARD_SOURCES)}: {self.reward_source!r}"
            )
        if self.reward_source == "env" and self.success == "rm":
            raise ValueError("success: rm needs a Reward Machine; reward_source: env has none")
        _check_env_kwargs(self.env_kwargs, "env_kwargs")

        if not isinstance(self.task_bundles, list):
            raise ValueError("task_bundles must be a list of mappings")
        if self.task_bundles and self.bundle is not None:
            raise ValueError("task_bundles and bundle are mutually exclusive")
        if self.task_bundles and self.reward_source == "env":
            raise ValueError("task_bundles needs a Reward Machine; reward_source: env has none")
        self.task_bundles = [
            _task_bundle(entry, index) for index, entry in enumerate(self.task_bundles)
        ]
        self._validate_ppo()

    def _validate_ppo(self) -> None:
        not_finite = [name for name in PPO_NUMBERS if not _is_finite_number(getattr(self, name))]
        if not_finite:
            raise ValueError(f"These PPO settings must be finite numbers: {', '.join(not_finite)}")
        not_positive = [name for name in PPO_POSITIVE if getattr(self, name) <= 0]
        if not_positive:
            raise ValueError(f"These PPO settings must be positive: {', '.join(not_positive)}")
        negative = [name for name in PPO_NON_NEGATIVE if getattr(self, name) < 0]
        if negative:
            raise ValueError(f"These PPO settings must not be negative: {', '.join(negative)}")
        not_flags = [name for name in PPO_FLAGS if not isinstance(getattr(self, name), bool)]
        if not_flags:
            raise ValueError(f"These PPO settings must be true or false: {', '.join(not_flags)}")
        if not 0 <= self.ppo_gae_lambda <= 1:
            raise ValueError("ppo_gae_lambda must be between 0 and 1")
        if (self.ppo_num_envs * self.ppo_num_steps) % self.ppo_num_minibatches:
            raise ValueError("ppo_num_envs * ppo_num_steps must divide by ppo_num_minibatches")

    def _validate_generation(self) -> None:
        if self.reasoning not in REASONING_LEVELS:
            raise ValueError(
                f"reasoning must be one of {', '.join(REASONING_LEVELS)}: {self.reasoning!r}"
            )
        if self.attempts not in self.ATTEMPT_LIMITS:
            raise ValueError(
                f"attempts must be between {self.ATTEMPT_LIMITS.start} and "
                f"{self.ATTEMPT_LIMITS.stop - 1}: {self.attempts!r}"
            )
        if not self.state_descriptions and (self.labeling or self.embeddings):
            raise ValueError(
                "Labeling and embeddings need state descriptions; enable --state-descriptions"
            )

    def _resolve_models(self) -> None:
        # dotenv already strips inline `# comments` from unquoted .env values.
        self.llm_provider = (
            self.llm_provider or os.environ.get("LLM_PROVIDER") or "openai"
        ).lower()
        if self.llm_provider not in LLM_PROVIDERS:
            raise ValueError(f"Unsupported LLM_PROVIDER: {self.llm_provider!r}")

        # An explicit --model beats the role variables; the provider model is the fallback.
        prefix = self.llm_provider.upper()
        provider_model = os.environ.get(f"{prefix}_MODEL")
        self.generator_model = (
            self.generator_model
            or self.model
            or os.environ.get(f"{prefix}_MODEL_GENERATOR")
            or provider_model
        )
        self.critic_model = self.critic_model or os.environ.get(f"{prefix}_MODEL_CRITIC")
        self.model = self.model or provider_model
        self.mona_executable = self.mona_executable or os.environ.get("MONA_EXECUTABLE") or "mona"

    def _validate_embeddings(self) -> None:
        port = os.environ.get("LLAMA_SERVER_PORT") or DEFAULT_LLAMA_SERVER_PORT
        self.embedding_endpoint = (
            self.embedding_endpoint or f"http://127.0.0.1:{port}/v1/embeddings"
        ).strip()
        self.embedding_model = (self.embedding_model or "").strip()
        self.embedding_revision = (self.embedding_revision or "").strip()
        if not self.embeddings:
            return

        if not self.embedding_endpoint.startswith(("http://", "https://")):
            raise ValueError(
                f"Embedding endpoint must be an http(s) URL: {self.embedding_endpoint!r}"
            )
        if not self.embedding_model:
            raise ValueError("Embedding model must be nonempty when embeddings are enabled")
        if not self.embedding_revision:
            raise ValueError("Embedding revision must be nonempty when embeddings are enabled")
        if self.embedding_timeout <= 0:
            raise ValueError("Embedding timeout must be positive when embeddings are enabled")

    def llama_server_command(self) -> str:
        """Return the llama-server command that serves ``embedding_endpoint``.

        The binary and GGUF paths come from ``LLAMA_SERVER_BIN`` and ``LLAMA_SERVER_MODEL``.
        """
        port = urlparse(self.embedding_endpoint).port
        binary = os.environ.get("LLAMA_SERVER_BIN") or "llama-server"
        model = os.environ.get("LLAMA_SERVER_MODEL") or "<path/to/nomic-embed-text.gguf>"
        return (
            f"{binary} -m {model} --host 127.0.0.1 --port {port}"
            f" --embedding --pooling mean --alias {self.embedding_model}"
            " --n-gpu-layers 99 --ctx-size 2048"
        )
