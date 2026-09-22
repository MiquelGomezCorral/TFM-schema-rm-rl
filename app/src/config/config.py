"""Project configuration from CLI arguments and environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from maikol_utils.file_utils import make_dirs
from maikol_utils.print_utils import print_warn


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
    MODELS_PATH: ClassVar[Path] = WORKSPACE_PATH / "models"
    LOGS_PATH: ClassVar[Path] = WORKSPACE_PATH / "logs"

    # ============================== Runtime options ==============================

    environment: Path | None = None
    tasks: list[str] = field(default_factory=list)
    output: Path | None = None
    llm_provider: str | None = None
    model: str | None = None
    judge_model: str = "Qwen3-30B-A3B-Instruct-2507"
    mona_executable: str | None = None
    overwrite: bool = False
    task_critic: bool = True
    rm_critic: bool = True
    svg: bool = False
    svg_dir: Path | None = None
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
        make_dirs([self.DATA_PATH, self.OUTPUT_PATH, self.MODELS_PATH, self.LOGS_PATH])
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
        raw_model = self.model or os.environ.get(model_variables[self.llm_provider])
        self.model = raw_model.split("#")[0].strip() if raw_model else None
        self.mona_executable = (
            self.mona_executable or os.environ.get("MONA_EXECUTABLE") or "mona"
        )

        if not self.task_critic and not self.rm_critic:
            print_warn(
                "Both critics are disabled: every compiler result is accepted without review."
            )
