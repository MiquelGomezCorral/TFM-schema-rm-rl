"""Environment Markdown parsing."""

import re
from dataclasses import dataclass
from pathlib import Path


PROPOSITION_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
PROPOSITION_BULLET = re.compile(r"^- `([^`]+)`:\s+(.+?)\s*$")
SECTION_END = re.compile(r"^#{1,2}\s+")
RESERVED_IDENTIFIERS = {"true", "false"}


class EnvironmentValidationError(ValueError):
    """Report invalid environment Markdown."""


@dataclass(frozen=True)
class Proposition:
    """One declared environment proposition."""

    identifier: str
    description: str
    line: int


@dataclass(frozen=True)
class EnvironmentDescription:
    """Validated environment prose and proposition metadata."""

    source: Path
    title: str
    markdown: str
    propositions: tuple[Proposition, ...]

    @property
    def proposition_ids(self) -> tuple[str, ...]:
        """Return proposition identifiers in document order."""
        return tuple(proposition.identifier for proposition in self.propositions)

    @classmethod
    def from_file(cls, path: str | Path) -> "EnvironmentDescription":
        """Load and validate an environment Markdown file."""
        source = Path(path)
        try:
            markdown = source.read_text(encoding="utf-8")
        except OSError as error:
            raise EnvironmentValidationError(
                f"Could not read environment file '{source}': {error}"
            ) from error
        return cls.from_markdown(markdown, source=source)

    @classmethod
    def from_markdown(
        cls,
        markdown: str,
        source: str | Path = "<memory>",
    ) -> "EnvironmentDescription":
        """Validate Markdown containing one strict propositions section."""
        source_path = Path(source)
        lines = markdown.splitlines()
        section_lines = [
            index
            for index, line in enumerate(lines, start=1)
            if line.strip() == "## Propositions"
        ]
        if not section_lines:
            raise EnvironmentValidationError(
                f"{source_path}: missing required '## Propositions' section"
            )
        if len(section_lines) > 1:
            raise EnvironmentValidationError(
                f"{source_path}:{section_lines[1]}: duplicate '## Propositions' section"
            )

        section_line = section_lines[0]
        propositions: list[Proposition] = []
        first_seen: dict[str, int] = {}
        for line_number in range(section_line + 1, len(lines) + 1):
            line = lines[line_number - 1]
            if SECTION_END.match(line):
                break
            if not line.strip():
                continue

            match = PROPOSITION_BULLET.fullmatch(line)
            if match is None:
                raise EnvironmentValidationError(
                    f"{source_path}:{line_number}: expected '- `identifier`: description'"
                )
            identifier, description = match.groups()
            if PROPOSITION_IDENTIFIER.fullmatch(identifier) is None:
                raise EnvironmentValidationError(
                    f"{source_path}:{line_number}: invalid proposition identifier "
                    f"'{identifier}'; expected ^[a-z_][a-z0-9_]*$"
                )
            if identifier in RESERVED_IDENTIFIERS:
                raise EnvironmentValidationError(
                    f"{source_path}:{line_number}: proposition identifier "
                    f"'{identifier}' is reserved"
                )
            if identifier in first_seen:
                raise EnvironmentValidationError(
                    f"{source_path}:{line_number}: duplicate proposition '{identifier}' "
                    f"(first declared on line {first_seen[identifier]})"
                )
            first_seen[identifier] = line_number
            propositions.append(Proposition(identifier, description, line_number))

        if not propositions:
            raise EnvironmentValidationError(
                f"{source_path}:{section_line}: propositions section must declare at least one proposition"
            )

        title = source_path.stem
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip() or title
                break
        return cls(source_path, title, markdown, tuple(propositions))
