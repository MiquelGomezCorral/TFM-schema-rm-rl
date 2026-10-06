"""Schemas and validation for structured engine responses."""

import json
from collections.abc import Sequence
from dataclasses import dataclass

from nl2ltl.declare.base import Template
from nl2ltl.declare.declare import Existence, ExistenceTwo, Precedence
from pylogics.syntax.ltl import Atomic

from src.config import Configuration, PriorityLevel
from src.models import EnvironmentDescription

from .errors import CriticValidationError, ProposalValidationError, RetryableEngineError

# ======================================================================================
#                                   STRUCTURED TYPES
# ======================================================================================

SUPPORTED_TEMPLATES: dict[str, tuple[type[Template], int, tuple[PriorityLevel, ...]]] = {
    "Existence": (Existence, 1, (PriorityLevel.NONE,)),
    "ExistenceTwo": (ExistenceTwo, 1, (PriorityLevel.NONE,)),
    "Precedence": (Precedence, 2, (PriorityLevel.SOFT, PriorityLevel.HARD)),
}


@dataclass(frozen=True)
class CriticResult:
    accepted: bool
    feedback: str


@dataclass(frozen=True)
class ProposalSelection:
    """One validated task-clause selection returned by the model."""

    normalized_clause: str
    pattern: str
    propositions: tuple[str, ...]
    priority: PriorityLevel
    template: Template


# ======================================================================================
#                                        SCHEMAS
# ======================================================================================


def proposal_schema(task: str, environment: EnvironmentDescription) -> dict:
    """Build the constrained schema for one nonempty task."""
    if not task.strip():
        raise ValueError("Tasks must be nonempty")

    clause_schemas = [
        {
            "type": "object",
            "properties": {
                "normalized_clause": {"type": "string", "minLength": 1},
                "pattern": {"type": "string", "enum": [pattern]},
                "propositions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": list(environment.proposition_ids),
                    },
                    "minItems": arity,
                    "maxItems": arity,
                },
                "priority": {
                    "type": "string",
                    "enum": [priority.value for priority in priorities],
                },
            },
            "required": ["normalized_clause", "pattern", "propositions", "priority"],
            "additionalProperties": False,
        }
        for pattern, (_, arity, priorities) in SUPPORTED_TEMPLATES.items()
    ]
    return {
        "type": "object",
        "properties": {
            "clauses": {
                "type": "array",
                "items": {"anyOf": clause_schemas},
                "minItems": 1,
                "maxItems": Configuration.MAX_TASK_CLAUSES,
            }
        },
        "required": ["clauses"],
        "additionalProperties": False,
    }


def critic_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "accepted": {"type": "boolean"},
            "feedback": {"type": "string", "minLength": 1},
        },
        "required": ["accepted", "feedback"],
        "additionalProperties": False,
    }


# ======================================================================================
#                                PARSING AND VALIDATION
# ======================================================================================


def parse_critic(response_text: str) -> CriticResult:
    try:
        output = json.loads(response_text)
    except (TypeError, json.JSONDecodeError) as error:
        raise CriticValidationError(
            f"Critic returned malformed structured output: {error}"
        ) from error
    if not isinstance(output, dict) or set(output) != {"accepted", "feedback"}:
        raise CriticValidationError("Critic output has unexpected fields")
    if not isinstance(output["accepted"], bool):
        raise CriticValidationError("Critic accepted value must be boolean")
    feedback = output["feedback"]
    if not isinstance(feedback, str) or not feedback.strip():
        raise CriticValidationError("Critic feedback must be nonempty")
    return CriticResult(output["accepted"], feedback.strip())


def parse_proposal(
    response_text: str,
    environment: EnvironmentDescription,
    provider_name: str,
) -> tuple[ProposalSelection, ...]:
    try:
        output = json.loads(response_text)
    except (TypeError, json.JSONDecodeError) as error:
        raise ProposalValidationError(
            f"{provider_name} returned malformed structured output: {error}"
        ) from error
    return _validate_proposal(output, environment)


def parse_state_descriptions(
    response_text: str,
    nodes: Sequence[str],
) -> tuple[str, ...]:
    """Validate one nonempty description per node from a bare JSON array."""
    try:
        output = json.loads(response_text)
    except (TypeError, json.JSONDecodeError) as error:
        raise RetryableEngineError(f"State tagger returned malformed JSON: {error}") from error
    if not isinstance(output, list):
        raise RetryableEngineError("State tagger must return a JSON array of descriptions")
    if len(output) != len(nodes):
        raise RetryableEngineError(
            f"State tagger returned {len(output)} description(s) for {len(nodes)} node(s)"
        )

    descriptions = []
    for item in output:
        if not isinstance(item, str) or not item.strip():
            raise RetryableEngineError("State descriptions must be nonempty strings")
        descriptions.append(item.strip())
    return tuple(descriptions)


def responses_text(response) -> str:
    response_text = getattr(response, "output_text", "")
    if response_text:
        return response_text
    for item in getattr(response, "output", ()):
        for content in getattr(item, "content", ()):
            refusal = getattr(content, "refusal", None)
            if refusal:
                raise ProposalValidationError(f"OpenAI refused the task: {refusal}")
    raise ProposalValidationError("OpenAI returned no structured proposal")


def completion_text(response) -> str:
    if not response.choices:
        raise ProposalValidationError("OpenCode returned no structured proposal")
    message = response.choices[0].message
    if refusal := getattr(message, "refusal", None):
        raise ProposalValidationError(f"OpenCode refused the task: {refusal}")
    if message.content:
        return message.content
    raise ProposalValidationError("OpenCode returned no structured proposal")


def _validate_proposal(
    output: object,
    environment: EnvironmentDescription,
) -> tuple[ProposalSelection, ...]:
    if not isinstance(output, dict) or set(output) != {"clauses"}:
        raise ProposalValidationError("Structured output has unexpected fields")
    clauses = output["clauses"]
    if not isinstance(clauses, list) or not 1 <= len(clauses) <= Configuration.MAX_TASK_CLAUSES:
        raise ProposalValidationError(
            f"A task must contain between 1 and {Configuration.MAX_TASK_CLAUSES} clauses"
        )
    return tuple(_validate_clause(clause, environment) for clause in clauses)


def _validate_clause(
    clause: object,
    environment: EnvironmentDescription,
) -> ProposalSelection:
    expected_fields = {"normalized_clause", "pattern", "propositions", "priority"}
    if not isinstance(clause, dict) or set(clause) != expected_fields:
        raise ProposalValidationError("A clause has unexpected fields")

    normalized_clause = clause["normalized_clause"]
    if not isinstance(normalized_clause, str) or not normalized_clause.strip():
        raise ProposalValidationError("Normalized clauses must be nonempty strings")

    pattern = clause["pattern"]
    if not isinstance(pattern, str) or pattern not in SUPPORTED_TEMPLATES:
        raise ProposalValidationError(f"Unsupported DECLARE pattern: {pattern!r}")
    symbols = clause["propositions"]
    if not isinstance(symbols, list) or any(not isinstance(symbol, str) for symbol in symbols):
        raise ProposalValidationError("Propositions must be a list of identifiers")
    template_class, arity, priorities = SUPPORTED_TEMPLATES[pattern]
    if len(symbols) != arity:
        raise ProposalValidationError(
            f"{pattern} requires {arity} proposition(s), received {len(symbols)}"
        )
    if len(set(symbols)) != len(symbols):
        raise ProposalValidationError("A proposal cannot repeat a proposition identifier")
    if unknown_symbols := set(symbols) - set(environment.proposition_ids):
        raise ProposalValidationError(
            f"Proposal invented proposition(s): {', '.join(sorted(unknown_symbols))}"
        )

    try:
        priority = PriorityLevel(clause["priority"])
    except (TypeError, ValueError) as error:
        raise ProposalValidationError(f"Unsupported priority: {clause['priority']!r}") from error
    if priority not in priorities:
        allowed = " or ".join(repr(value.value) for value in priorities)
        raise ProposalValidationError(f"{pattern} requires priority {allowed}")

    template = template_class(*(Atomic(symbol) for symbol in symbols))
    return ProposalSelection(
        normalized_clause=normalized_clause.strip(),
        pattern=pattern,
        propositions=tuple(symbols),
        priority=priority,
        template=template,
    )
