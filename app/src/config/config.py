"""Project configuration from CLI arguments and environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from maikol_utils.file_utils import make_dirs


# ================================ Prompt defaults ================================

PROMPT_NAMES = {
    "creator": "reward-ltlf-creator",
    "ltlf_reviewer": "reward-ltlf-reviewer",
    "rm_reviewer": "reward-machine-reviewer",
}


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

    PROMPTS: dict[str, str] = field(default_factory=PROMPT_NAMES.copy)

    environment: Path | None = None
    tasks: list[str] = field(default_factory=list)
    output: Path | None = None
    llm_provider: str | None = None
    model: str | None = None
    mona_executable: str | None = None
    overwrite: bool = False
    task_critic: bool = True
    rm_critic: bool = True
    seed: int = 42

    def __post_init__(self) -> None:
        """Normalize paths and resolve optional environment configuration."""
        make_dirs([self.DATA_PATH, self.OUTPUT_PATH, self.MODELS_PATH, self.LOGS_PATH])
        if self.environment is not None:
            self.environment = Path(self.environment)
        if self.output is not None:
            self.output = Path(self.output)
            if self.output.name != str(self.output):
                raise ValueError("--output must be a file name without a directory")

        self.llm_provider = (
            self.llm_provider or os.environ.get("LLM_PROVIDER") or "openai"
        ).lower()

        model_variables = {
            "openai": "OPENAI_MODEL",
            "opencode": "OPENCODE_MODEL",
        }
        if self.llm_provider not in model_variables:
            raise ValueError(f"Unsupported LLM_PROVIDER: {self.llm_provider!r}")
        self.model = self.model or os.environ.get(model_variables[self.llm_provider])
        self.mona_executable = (
            self.mona_executable or os.environ.get("MONA_EXECUTABLE") or "mona"
        )

        if not self.task_critic and not self.rm_critic:
            raise ValueError("At least one critic must be enabled")
