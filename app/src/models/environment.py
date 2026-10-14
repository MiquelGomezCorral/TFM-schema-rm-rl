"""Environment Markdown parsing."""

import re
from dataclasses import astuple, dataclass
from pathlib import Path

PROPOSITION_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
PROPOSITION_BULLET = re.compile(r"^- `([^`]+)`:\s+(.+?)\s*$")
SECTION_END = re.compile(r"^#{1,2}\s+")
LABELING_API_HEADING = "## Labeling API"
CONSTRAINTS_HEADING = "## Constraints"
_NAME = r"`([^`]+)`"
_REASON = r"(?::\s.*)?"
ORDER_BULLET = re.compile(rf"^- {_NAME} cannot become true before {_NAME}{_REASON}$")
EXCLUSIVE_BULLET = re.compile(rf"^- {_NAME} and {_NAME} never hold together{_REASON}$")
LATCH_BULLET = re.compile(rf"^- {_NAME} cannot become false once true{_REASON}$")
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
class OrderConstraint:
    """``later`` cannot become true before ``earlier`` has been true (the same step counts)."""

    later: str
    earlier: str


@dataclass(frozen=True)
class ExclusiveConstraint:
    """``first`` and ``second`` are never true in the same step."""

    first: str
    second: str


@dataclass(frozen=True)
class LatchConstraint:
    """``name`` stays true in every step after it was first true."""

    name: str


Constraint = OrderConstraint | ExclusiveConstraint | LatchConstraint


@dataclass(frozen=True)
class EnvironmentDescription:
    """Validated environment prose and proposition metadata."""

    source: Path
    title: str
    markdown: str
    propositions: tuple[Proposition, ...]
    labeling_api: str | None = None
    constraints: tuple[Constraint, ...] = ()

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
        """Validate Markdown with one strict propositions section and optional constraints and API."""
        source_path = Path(source)
        lines = markdown.splitlines()
        section_line = _propositions_section_line(lines, source_path)
        propositions = _parse_propositions(lines, section_line, source_path)
        if not propositions:
            raise EnvironmentValidationError(
                f"{source_path}:{section_line}: propositions section must declare at least one proposition"
            )
        labeling_api = _labeling_api(lines, source_path)
        constraints = _parse_constraints(lines, propositions, source_path)
        return cls(
            source_path,
            _title(lines, source_path),
            markdown,
            propositions,
            labeling_api,
            constraints,
        )


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


def _optional_section_line(lines: list[str], heading: str, source_path: Path) -> int | None:
    """Return the 1-based line of the optional ``heading``, or None when absent."""
    section_lines = [index for index, line in enumerate(lines, start=1) if line.strip() == heading]
    if len(section_lines) > 1:
        raise EnvironmentValidationError(
            f"{source_path}:{section_lines[1]}: duplicate '{heading}' section"
        )
    return section_lines[0] if section_lines else None


def _labeling_api(lines: list[str], source_path: Path) -> str | None:
    """Return the body of the optional ``## Labeling API`` section, or None when absent."""
    section_line = _optional_section_line(lines, LABELING_API_HEADING, source_path)
    if section_line is None:
        return None

    body: list[str] = []
    for line in lines[section_line:]:
        if SECTION_END.match(line):
            break
        body.append(line)
    text = "\n".join(body).strip()
    if not text:
        raise EnvironmentValidationError(
            f"{source_path}:{section_line}: '{LABELING_API_HEADING}' section must not be empty"
        )
    return text


def _parse_constraints(
    lines: list[str], propositions: tuple[Proposition, ...], source_path: Path
) -> tuple[Constraint, ...]:
    """Parse the optional ``## Constraints`` section: one bullet per constraint, three shapes."""
    section_line = _optional_section_line(lines, CONSTRAINTS_HEADING, source_path)
    if section_line is None:
        return ()

    declared = {proposition.identifier for proposition in propositions}
    constraints: list[Constraint] = []
    for line_number in range(section_line + 1, len(lines) + 1):
        line = lines[line_number - 1]
        if SECTION_END.match(line):
            break
        if not line.strip():
            continue

        constraint = _constraint_from_bullet(line.rstrip())
        if constraint is None:
            raise EnvironmentValidationError(
                f"{source_path}:{line_number}: expected '- `b` cannot become true before `a`', "
                "'- `a` and `b` never hold together' or '- `a` cannot become false once true'"
            )
        names = astuple(constraint)
        for name in names:
            if name not in declared:
                raise EnvironmentValidationError(
                    f"{source_path}:{line_number}: constraint uses undeclared proposition '{name}'"
                )
        if len(set(names)) != len(names):
            raise EnvironmentValidationError(
                f"{source_path}:{line_number}: constraint names the same proposition twice"
            )
        constraints.append(constraint)
    return tuple(constraints)


def _constraint_from_bullet(line: str) -> Constraint | None:
    """Return the constraint a bullet states, or None when it fits none of the three shapes."""
    if match := ORDER_BULLET.fullmatch(line):
        later, earlier = match.groups()
        return OrderConstraint(later, earlier)
    if match := EXCLUSIVE_BULLET.fullmatch(line):
        return ExclusiveConstraint(*match.groups())
    if match := LATCH_BULLET.fullmatch(line):
        return LatchConstraint(*match.groups())
    return None


def _title(lines: list[str], source_path: Path) -> str:
    """Return the first level-one heading, falling back to the file stem."""
    title = source_path.stem
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip() or title
    return title
