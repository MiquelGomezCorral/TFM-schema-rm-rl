"""Project configuration from CLI arguments and environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Configuration:
    """Configuration class for the project."""

    environment: Path | None = None
    instructions: list[str] = field(default_factory=list)
    output: Path | None = None
    model: str | None = None
    api_key: str | None = field(default=None, repr=False)
    mona_executable: str | None = None
    overwrite: bool = False
    seed: int = 42

    def __post_init__(self) -> None:
        """Normalize paths and resolve optional environment configuration."""
        if self.environment is not None:
            self.environment = Path(self.environment)
        if self.output is not None:
            self.output = Path(self.output)
        self.model = self.model or os.environ.get("OPENAI_MODEL")
        self.api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        self.mona_executable = (
            self.mona_executable or os.environ.get("MONA_EXECUTABLE") or "mona"
        )
