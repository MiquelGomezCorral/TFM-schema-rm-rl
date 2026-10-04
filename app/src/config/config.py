"""Project configuration from CLI arguments and environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from maikol_utils.file_utils import make_dirs
from maikol_utils.print_utils import print_warn


def _clean_model(value: str | None) -> str | None:
    """Drop an inline env-file comment and surrounding space from a model id."""
    return value.split("#")[0].strip() if value else None


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
    node_gap: int = 140     # horizontal spacing between states in a layer
    layer_gap: int = 118    # vertical spacing between layers
    margin: int = 60        # blank space around the drawing
    arc_room: int = 48      # extra right-side room for self-loops


@dataclass
class Configuration:
    """Configuration class for the project."""

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
    embedding_revision: str = "sha256:970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6"
    embedding_context: str = ""
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
    algorithm: str | None = None
    learning_rate: float | None = None
    task_manifest: Path | None = None

    def __post_init__(self) -> None:
        """Normalize paths and resolve optional environment configuration."""
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
        if self.environment is not None:
            self.environment = Path(self.environment)
        if self.output is not None:
            self.output = Path(self.output)
            if self.output.name != str(self.output):
                raise ValueError("--output must be a file name without a directory")
        if self.bundle is not None:
            self.bundle = Path(self.bundle)
        if self.checkpoint is not None:
            self.checkpoint = Path(self.checkpoint)
        if self.task_manifest is not None:
            self.task_manifest = Path(self.task_manifest)
        if self.steps_report is not None:
            self.steps_report = Path(self.steps_report)
        if self.trace_dir is not None:
            self.trace_dir = Path(self.trace_dir)
        self.manifests = [Path(path) for path in self.manifests]
        self.svg_dir = (
            Path(self.svg_dir) if self.svg_dir is not None else self.OUTPUT_PATH / "svgs"
        )

        self.llm_provider = (
            self.llm_provider or os.environ.get("LLM_PROVIDER") or "openai"
        ).split("#")[0].strip().lower()

        model_variables = {
            "openai": "OPENAI_MODEL",
            "opencode": "OPENCODE_MODEL",
            "antigravity": "ANTIGRAVITY_MODEL",
        }
        if self.llm_provider not in model_variables:
            raise ValueError(f"Unsupported LLM_PROVIDER: {self.llm_provider!r}")
        provider_model = _clean_model(os.environ.get(model_variables[self.llm_provider]))
        requested_model = _clean_model(self.model)
        # Baseline selection happens before cleaning, matching the original behavior.
        self.model = _clean_model(
            self.model or os.environ.get(model_variables[self.llm_provider])
        )

        role_prefix = model_variables[self.llm_provider].removesuffix("_MODEL")
        self.generator_model = (
            _clean_model(self.generator_model)
            or requested_model
            or _clean_model(os.environ.get(f"{role_prefix}_MODEL_GENERATOR"))
            or provider_model
        )
        self.critic_model = _clean_model(
            self.critic_model or os.environ.get(f"{role_prefix}_MODEL_CRITIC")
        )
        self.mona_executable = (
            self.mona_executable or os.environ.get("MONA_EXECUTABLE") or "mona"
        )

        self.embedding_endpoint = (self.embedding_endpoint or "").strip()
        self.embedding_model = (self.embedding_model or "").strip()
        self.embedding_revision = (self.embedding_revision or "").strip()
        self.embedding_context = self.embedding_context or ""
        if self.embeddings:
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

        if not self.task_critic and not self.rm_critic:
            print_warn(
                "Both critics are disabled: every compiler result is accepted without review."
            )
