"""Project configuration from CLI arguments and environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from maikol_utils.file_utils import make_dirs

from src.models import PriorityLevel


@dataclass
class Configuration:
    """Configuration class for the project."""

    WORKSPACE_PATH: ClassVar[Path] = Path(__file__).resolve().parents[4]
    DATA_PATH: ClassVar[Path] = WORKSPACE_PATH / "data"
    OUTPUT_PATH: ClassVar[Path] = WORKSPACE_PATH / "outputs"
    MODELS_PATH: ClassVar[Path] = WORKSPACE_PATH / "models"

    environment: Path | None = None
    instructions: list[str] = field(default_factory=list)
    priorities: list[str] = field(default_factory=list)
    output: Path | None = None
    llm_provider: str | None = None
    model: str | None = None
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    mona_executable: str | None = None
    overwrite: bool = False
    seed: int = 42

    def __post_init__(self) -> None:
        """Normalize paths and resolve optional environment configuration."""
        make_dirs([self.DATA_PATH, self.OUTPUT_PATH, self.MODELS_PATH])

        if self.environment is not None:
            self.environment = Path(self.environment)
        if self.output is not None:
            self.output = Path(self.output)
            if self.output.name != str(self.output):
                raise ValueError("--output must be a file name without a directory")
        self.priorities = [priority.lower() for priority in (self.priorities or [])]
        priority_choices = {"infer", *(priority.value for priority in PriorityLevel)}
        invalid_priorities = set(self.priorities) - priority_choices
        if invalid_priorities:
            raise ValueError(
                f"Unsupported priority value(s): {', '.join(sorted(invalid_priorities))}"
            )
        if self.priorities and len(self.priorities) != len(self.instructions):
            raise ValueError(
                "When --priority is supplied, provide exactly one value per instruction"
            )
        self.llm_provider = (
            self.llm_provider or os.environ.get("LLM_PROVIDER") or "openai"
        ).lower()
        if self.llm_provider == "opencode":
            self.model = self.model or os.environ.get("OPENCODE_MODEL")
            self.api_key = self.api_key or os.environ.get("OPENCODE_API_KEY")
            self.base_url = self.base_url or os.environ.get("OPENCODE_BASE_URL")
        elif self.llm_provider == "openai":
            self.model = self.model or os.environ.get("OPENAI_MODEL")
            self.api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {self.llm_provider!r}")
        self.mona_executable = (
            self.mona_executable or os.environ.get("MONA_EXECUTABLE") or "mona"
        )
