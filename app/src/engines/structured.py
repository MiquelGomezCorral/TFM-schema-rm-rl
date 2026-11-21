"""Schemas and validation for structured engine responses."""

import json
from collections.abc import Sequence
from dataclasses import dataclass

from nl2ltl.declare.base import Template
from nl2ltl.declare.declare import (
    Absence,
    ChainResponse,
    Existence,
    ExistenceTwo,
    NotCoExistence,
    Precedence,
    RespondedExistence,
    Response,
)
from pylogics.syntax.ltl import Atomic

from src.config import Configuration, PriorityLevel
from src.models import EnvironmentDescription

from .errors import CriticValidationError, ProposalValidationError, RetryableEngineError

# ======================================================================================
#                                   STRUCTURED TYPES
# ======================================================================================

_ACCEPTED_PREFIX = "NO CHANGES NEEDED"
_REJECTED_PREFIX = "CHANGES REQUIRED"

# IBM nl2ltl's DECLARE templates by name, with the number of propositions each takes.
SUPPORTED_TEMPLATES: dict[str, tuple[type[Template], int]] = {
    "Existence": (Existence, 1),
    "ExistenceTwo": (ExistenceTwo, 1),
    "Absence": (Absence, 1),
    "RespondedExistence": (RespondedExistence, 2),
    "Response": (Response, 2),
    "Precedence": (Precedence, 2),
    "ChainResponse": (ChainResponse, 2),
    "NotCoExistence": (NotCoExistence, 2),
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

    # One clause shape per arity: the pattern enum and the proposition count go together.
    clause_schemas = [
        {
            "type": "object",
            "properties": {
                "normalized_clause": {"type": "string", "minLength": 1},
                "pattern": {"type": "string", "enum": _patterns_with_arity(arity)},
                "propositions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": list(environment.proposition_ids),
                    },
                    "minItems": arity,
                    "maxItems": arity,
                },
                "priority": {"type": "string", "enum": [level.value for level in PriorityLevel]},
            },
            "required": ["normalized_clause", "pattern", "propositions", "priority"],
            "additionalProperties": False,
        }
        for arity in sorted({size for _, size in SUPPORTED_TEMPLATES.values()})
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


def _patterns_with_arity(arity: int) -> list[str]:
    return [name for name, (_, size) in SUPPORTED_TEMPLATES.items() if size == arity]


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


def state_descriptions_schema(states: Sequence[str]) -> dict:
    """One description per state, keyed by its identifier: no other key, none left out."""
    return {
        "type": "object",
        "properties": {state: {"type": "string", "minLength": 1} for state in states},
        "required": list(states),
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
    feedback = feedback.strip()
    # Only the opening words count; a verdict that contradicts its own boolean is malformed.
    opening = feedback[:20].upper()
    if not output["accepted"] and opening.startswith(_ACCEPTED_PREFIX):
        raise CriticValidationError(f"Critic rejected the candidate but wrote: {feedback[:60]}")
    if output["accepted"] and opening.startswith(_REJECTED_PREFIX):
        raise CriticValidationError(f"Critic accepted the candidate but wrote: {feedback[:60]}")
    return CriticResult(output["accepted"], feedback)


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


# The roles the tagger reads beside each state (`tag_states`); a reply echoing one is no description.
STATE_FINAL, STATE_REJECTING, STATE_IN_PROGRESS = "final", "rejecting", "in progress"
_STATE_ROLES = frozenset({STATE_FINAL, STATE_REJECTING, STATE_IN_PROGRESS})


def parse_state_descriptions(
    response_text: str,
    nodes: Sequence[str],
) -> tuple[str, ...]:
    """Validate one nonempty description per node from a JSON object keyed by node, in node order.

    A text must name its state: a missing, repeated or unknown key is refused, never matched
    by position.
    """
    try:
        output = json.loads(response_text, object_pairs_hook=_refuse_repeated_keys)
    except (TypeError, json.JSONDecodeError) as error:
        raise RetryableEngineError(f"State tagger returned malformed JSON: {error}") from error
    if not isinstance(output, dict):
        raise RetryableEngineError("State tagger must return a JSON object keyed by state")
    missing = [node for node in nodes if node not in output]
    unknown = sorted(set(output) - set(nodes))
    if missing or unknown:
        raise RetryableEngineError(
            f"State tagger keys differ from the states: missing {missing}, unknown {unknown}"
        )

    descriptions = []
    for node in nodes:
        text = output[node]
        if not isinstance(text, str) or not text.strip():
            raise RetryableEngineError("State descriptions must be nonempty strings")
        if text.strip().lower() in _STATE_ROLES:
            raise RetryableEngineError(f"State tagger copied a role as the description of {node}")
        descriptions.append(text.strip())
    return tuple(descriptions)


def _refuse_repeated_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object, refusing a key given twice (``json.loads`` keeps the last)."""
    keys = [key for key, _ in pairs]
    if repeated := sorted({key for key in keys if keys.count(key) > 1}):
        raise RetryableEngineError(f"State tagger described a state twice: {repeated}")
    return dict(pairs)


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
    template_class, arity = SUPPORTED_TEMPLATES[pattern]
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

    template = template_class(*(Atomic(symbol) for symbol in symbols))
    return ProposalSelection(
        normalized_clause=normalized_clause.strip(),
        pattern=pattern,
        propositions=tuple(symbols),
        priority=priority,
        template=template,
    )
