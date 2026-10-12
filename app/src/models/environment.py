"""Environment Markdown parsing."""

import re
from dataclasses import dataclass
from pathlib import Path

PROPOSITION_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
PROPOSITION_BULLET = re.compile(r"^- `([^`]+)`:\s+(.+?)\s*$")
SECTION_END = re.compile(r"^#{1,2}\s+")
LABELING_API_HEADING = "## Labeling API"
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
    labeling_api: str | None = None

    def require_labeling_api(self) -> str:
        """Return the declared labeling API, the only surface labeling code may read.

        Labeling and training paths call this; plain Reward Machine generation does not need
        the section.

        Raises:
            EnvironmentValidationError: If the environment declares no ``## Labeling API``.
        """
        if self.labeling_api is None:
            raise EnvironmentValidationError(
                f"{self.source}: labeling and training need a '{LABELING_API_HEADING}' section "
                "listing what the labeling code may read from the live environment"
            )
        return self.labeling_api

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
        """Validate Markdown with one strict propositions section and an optional labeling API."""
        source_path = Path(source)
        lines = markdown.splitlines()
        section_line = _propositions_section_line(lines, source_path)
        propositions = _parse_propositions(lines, section_line, source_path)
        if not propositions:
            raise EnvironmentValidationError(
                f"{source_path}:{section_line}: propositions section must declare at least one proposition"
            )
        labeling_api = _labeling_api(lines, source_path)
        return cls(source_path, _title(lines, source_path), markdown, propositions, labeling_api)


def _propositions_section_line(lines: list[str], source_path: Path) -> int:
    """Return the 1-based line of the single ``## Propositions`` heading."""
    section_lines = [
        index for index, line in enumerate(lines, start=1) if line.strip() == "## Propositions"
    ]
    if not section_lines:
        raise EnvironmentValidationError(
            f"{source_path}: missing required '## Propositions' section"
        )
    if len(section_lines) > 1:
        raise EnvironmentValidationError(
            f"{source_path}:{section_lines[1]}: duplicate '## Propositions' section"
        )
    return section_lines[0]


def _parse_propositions(
    lines: list[str], section_line: int, source_path: Path
) -> tuple[Proposition, ...]:
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
                f"{source_path}:{line_number}: proposition identifier '{identifier}' is reserved"
            )
        if identifier in first_seen:
            raise EnvironmentValidationError(
                f"{source_path}:{line_number}: duplicate proposition '{identifier}' "
                f"(first declared on line {first_seen[identifier]})"
            )
        first_seen[identifier] = line_number
        propositions.append(Proposition(identifier, description, line_number))
    return tuple(propositions)


def _labeling_api(lines: list[str], source_path: Path) -> str | None:
    """Return the body of the optional ``## Labeling API`` section, or None when absent."""
    section_lines = [
        index for index, line in enumerate(lines, start=1) if line.strip() == LABELING_API_HEADING
    ]
    if not section_lines:
        return None
    if len(section_lines) > 1:
        raise EnvironmentValidationError(
            f"{source_path}:{section_lines[1]}: duplicate '{LABELING_API_HEADING}' section"
        )

    body: list[str] = []
    for line in lines[section_lines[0] :]:
        if SECTION_END.match(line):
            break
        body.append(line)
    text = "\n".join(body).strip()
    if not text:
        raise EnvironmentValidationError(
            f"{source_path}:{section_lines[0]}: '{LABELING_API_HEADING}' section must not be empty"
        )
    return text


def _title(lines: list[str], source_path: Path) -> str:
    """Return the first level-one heading, falling back to the file stem."""
    title = source_path.stem
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip() or title
    return title
