"""Project configuration from CLI arguments and environment variables."""

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

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
    """Project settings: CLI options plus the derived output folders."""

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
    checkpoint: Path | None = None
    total_timesteps: int | None = None
    algorithm: str = "dqn"
    rnd: bool = False
    learning_rate: float | None = None
    task_manifest: Path | None = None
    rm_file: Path | None = None

    def __post_init__(self) -> None:
        self._resolve_paths()
        self._resolve_models()
        self._validate_embeddings()

        if not self.task_critic and not self.rm_critic:
            print_warn(
                "Both critics are disabled: every compiler result is accepted without review."
            )

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
        self.checkpoint = _optional_path(self.checkpoint)
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
