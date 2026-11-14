"""Environment Markdown parsing."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

PROPOSITION_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
PROPOSITION_BULLET = re.compile(r"^- `([^`]+)`:\s+(.+?)\s*$")
SECTION_END = re.compile(r"^#{1,2}\s+")
LABELING_API_HEADING = "## Labeling API"
CODE_FILE_NAME = "environment-code.md"
RESERVED_IDENTIFIERS = {"true", "false"}
# A row of the facts page's semantics table: ``| `id` | kind | true when ... |``.
SEMANTICS_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|[^|]*\|(.*)$")
BACKTICKED = re.compile(r"`([^`]+)`")


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
                f"in {CODE_FILE_NAME}, next to the facts file, listing what the labeling code "
                "may read from the live environment"
            )
        return self.labeling_api

    @property
    def proposition_ids(self) -> tuple[str, ...]:
        """Return proposition identifiers in document order."""
        return tuple(proposition.identifier for proposition in self.propositions)

    def reads(self) -> dict[str, tuple[str, ...]]:
        """Per proposition, the other declared propositions its semantics-table row names.

        The facts page owns these definitions: ``key_lost`` is true when ``has_door_key`` was true
        at the previous step and ``door_open`` is false now, so its labeling reads both.
        """
        declared = set(self.proposition_ids)
        reads: dict[str, tuple[str, ...]] = {}
        for line in self.markdown.splitlines():
            row = SEMANTICS_ROW.match(line)
            if row is not None and row.group(1) in declared:
                # Other tables repeat the id as a first cell; their rows add, never erase.
                named = dict.fromkeys(
                    (*reads.get(row.group(1), ()), *BACKTICKED.findall(row.group(2)))
                )
                reads[row.group(1)] = tuple(
                    name for name in named if name in declared and name != row.group(1)
                )
        return reads

    def labeling_propositions(self, used: Iterable[str]) -> tuple[str, ...]:
        """The propositions a labeling covers: ``used`` plus, transitively, what their definitions read.

        Declared order. The one vocabulary every labeling step (generation, check, runtime,
        replay) works on.
        """
        reads = self.reads()
        needed: set[str] = set()
        pending = list(used)
        while pending:
            name = pending.pop()
            if name not in needed:
                needed.add(name)
                pending.extend(reads.get(name, ()))
        return tuple(name for name in self.proposition_ids if name in needed)

    @classmethod
    def from_file(cls, path: str | Path, *, code: bool = False) -> "EnvironmentDescription":
        """Load and validate an environment Markdown file.

        Args:
            path (str | Path): The facts file, ``environment.md``.
            code (bool): Append the sibling ``environment-code.md`` after a blank line when it
                exists. Steps that write code (labeling) set it; the clause generator and the
                critic load the facts alone.
        """
        source = Path(path)
        markdown = _read_text(source)
        code_file = source.with_name(CODE_FILE_NAME)
        if code and code_file.exists():
            markdown += "\n\n" + _read_text(code_file)
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


def _read_text(path: Path) -> str:
    """Read one environment file, naming that file when it cannot be read."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise EnvironmentValidationError(
            f"Could not read environment file '{path}': {error}"
        ) from error


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
