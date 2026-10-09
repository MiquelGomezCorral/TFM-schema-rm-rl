"""Project configuration from CLI arguments and environment variables."""

import os
from dataclasses import dataclass, field, fields
from enum import StrEnum
from pathlib import Path
from types import UnionType
from typing import ClassVar, get_args

import yaml
from maikol_utils.file_utils import make_dirs
from maikol_utils.print_utils import print_warn

LLM_PROVIDERS = ("openai", "opencode", "antigravity")


class PriorityLevel(StrEnum):
    """Supported ordering-priority levels for task clauses."""

    NONE = "none"
    SOFT = "soft"
    HARD = "hard"


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


# ================================ Graph defaults ================================


@dataclass(frozen=True)
class GraphStyle:
    """Sizing for rendered Reward Machine graphs, in SVG user units.

    Shared by the web graph export and the render_rm script. ``margin`` and
    ``arc_room`` are the blank space kept around the drawing; lower them for a
    tighter picture and raise them if labels feel crowded.

    States flow top to bottom in layers: ``node_gap`` spaces states within one
    layer and ``layer_gap`` spaces the layers.
    """

    node_width: int = 92
    node_height: int = 56
    node_gap: int = 140  # horizontal spacing between states in a layer
    layer_gap: int = 118  # vertical spacing between layers
    margin: int = 60  # blank space around the drawing
    arc_room: int = 48  # extra right-side room for self-loops


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

    # Each task gets this many proposal attempts; each candidate this many tagging requests.
    PROPOSAL_ATTEMPTS: ClassVar[int] = 3
    TAGGING_ATTEMPTS: ClassVar[int] = 3
    MAX_TASK_CLAUSES: ClassVar[int] = 25
    CLAUSE_COMPLETION_REWARD: ClassVar[float] = 0.1
    TASK_COMPLETION_REWARD: ClassVar[float] = 1.0

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
    task_critic: bool = True
    rm_critic: bool = True
    labeling: bool = False
    embeddings: bool = False
    embedding_endpoint: str = "http://127.0.0.1:8934/v1/embeddings"
    embedding_model: str = "nomic-embed-text"
    embedding_revision: str = (
        "sha256:970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6"
    )
    embedding_context: bool = False
    embedding_timeout: float = 30.0
    svg: bool = False
    svg_dir: Path | None = None
    steps_report: Path | None = None
    trace_dir: Path | None = None
    seed: int = 42
    mode: str = "arm-fm"
    bundle: Path | None = None
    manifests: list[Path] = field(default_factory=list)
    domain: str | None = None
    task_manifest: Path | None = None
    rm_file: Path | None = None

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
    use_rm: bool = True

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

    def __post_init__(self) -> None:
        # The YAML loads first so its path values get the same Path conversion.
        if self.yaml_config_name:
            self._load_yaml_configuration(self.yaml_config_name)
        self._resolve_paths()
        self._resolve_models()
        self._validate_embeddings()

        if not self.task_critic and not self.rm_critic:
            print_warn(
                "Both critics are disabled: every compiler result is accepted without review."
            )

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
        self.steps_report = _optional_path(self.steps_report)
        self.trace_dir = _optional_path(self.trace_dir)
        self.manifests = [Path(path) for path in self.manifests]
        self.svg_dir = Path(self.svg_dir) if self.svg_dir is not None else self.OUTPUT_PATH / "svgs"

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
        self.embedding_endpoint = (self.embedding_endpoint or "").strip()
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
