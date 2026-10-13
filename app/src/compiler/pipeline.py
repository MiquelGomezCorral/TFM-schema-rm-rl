"""Task proposal and deterministic Reward Machine compilation."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from flat_tool import compile_dfa
from nl2ltl.declare.base import Template
from pylogics.syntax.base import And, Formula, Not
from pylogics.syntax.ltl import Atomic, Eventually, Next, Until

from src.config import Configuration, PriorityLevel
from src.engines.structured import ProposalSelection
from src.models import EnvironmentDescription

from .ltlf import to_flat_syntax
from .reward_layer import RewardLayerResult, build_reward_machine
from .reward_machine import RewardMachineStructure
from .rm_format import serialize_reward_machine


@dataclass(frozen=True)
class ClauseProposal:
    """One critic-validated atomic requirement from normalized language through LTLf."""

    normalized_clause: str
    pattern: str
    propositions: tuple[str, ...]
    priority: PriorityLevel
    ltlf_formula: str


@dataclass(frozen=True)
class Proposal:
    """One natural-language task and its conjunctive clause proposals."""

    task: str
    clauses: tuple[ClauseProposal, ...]


@dataclass(frozen=True)
class CompilationResult:
    """Complete in-memory result of a critic-accepted compilation."""

    environment: EnvironmentDescription
    proposal: Proposal
    reward_machine: RewardMachineStructure
    text: str
    warnings: tuple[str, ...] = ()
    state_descriptions: tuple[str, ...] = ()
    labeling_source: str = ""
    labeling_attempts: tuple[dict[str, object], ...] = ()
    embeddings: dict[str, list[float]] = field(default_factory=dict)
    embedding_settings: dict[str, object] = field(default_factory=dict)
    embedding_texts: dict[str, str] = field(default_factory=dict)
    embedding_path: Path | None = None
    bundle_path: Path | None = None


def materialize_proposal(task: str, selections: Sequence[ProposalSelection]) -> Proposal:
    """Build deterministic DECLARE and LTLf clauses from validated selections."""
    clauses = []
    for selection in selections:
        ltlf_ast = _build_ltlf_formula(
            selection.pattern,
            selection.propositions,
            selection.priority,
            selection.template,
        )
        clauses.append(
            ClauseProposal(
                normalized_clause=selection.normalized_clause,
                pattern=selection.pattern,
                propositions=selection.propositions,
                priority=selection.priority,
                ltlf_formula=to_flat_syntax(ltlf_ast),
            )
        )
    return Proposal(task=task.strip(), clauses=tuple(clauses))


def _build_ltlf_formula(
    pattern: str,
    propositions: tuple[str, ...],
    priority: PriorityLevel,
    template: Template,
) -> Formula:
    if pattern != "Precedence":
        return template.to_ltlf()

    preferred, second = (Atomic(proposition) for proposition in propositions)
    if priority is PriorityLevel.HARD:
        return Until(
            Not(second),
            And(preferred, Not(second), Next(Eventually(second))),
        )
    return And(Eventually(preferred), Eventually(second))


def compile_dfas(proposal: Proposal, CONFIG: Configuration) -> tuple[dict, ...]:
    """Compile each accepted LTLf clause into one FL-AT/MONA DFA."""
    return tuple(
        compile_dfa(clause.ltlf_formula, mona_executable=CONFIG.mona_executable)
        for clause in proposal.clauses
    )


def build_compilation_result(
    environment: EnvironmentDescription,
    proposal: Proposal,
    dfas: Sequence[dict],
) -> CompilationResult:
    """Build and serialize a task-specific Reward Machine from compiled DFAs."""
    # NONE (Existence, ExistenceTwo) counts as hard until the engine schema is hard | soft.
    soft = [clause.priority is PriorityLevel.SOFT for clause in proposal.clauses]
    layer = build_reward_machine(dfas, soft)
    return CompilationResult(
        environment=environment,
        proposal=proposal,
        reward_machine=layer.reward_machine,
        text=serialize_reward_machine(layer.reward_machine),
        warnings=_warnings(proposal, layer),
    )


def _warnings(proposal: Proposal, layer: RewardLayerResult) -> tuple[str, ...]:
    """Name what the user should know about: no hard goal, and soft clauses that pay nothing."""
    warnings = []
    if not layer.hard_goal:
        warnings.append(
            "Rule-only task: no hard goal clause, so the machine has no final state; "
            "episodes end on a well, the environment's end, or the time limit"
        )
    for index in layer.inert_soft_clauses:
        clause = proposal.clauses[index]
        name = f"{clause.pattern}({', '.join(clause.propositions)})"
        warnings.append(f"Soft clause {name} has no reward effect")
    return tuple(warnings)
