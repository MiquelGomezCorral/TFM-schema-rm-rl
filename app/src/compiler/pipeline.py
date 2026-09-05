"""Task proposal and deterministic Reward Machine compilation."""

from collections.abc import Sequence
from dataclasses import dataclass

from nl2ltl.declare.base import Template
from pylogics.syntax.base import And, Formula, Not
from pylogics.syntax.ltl import Atomic, Eventually, Next, Until
from flat_tool import compile_dfa

from src.engines import GenericEngine
from src.engines.structured import ProposalSelection
from src.models import (
    EnvironmentDescription,
    MAX_TASK_CLAUSES,
    PriorityLevel,
    describe_reward_behavior,
)

from .ltlf import to_flat_syntax
from .reward_machine import (
    RewardMachineStructure,
    compose_reward_machines,
    normalize_reward_machine,
    serialize_reward_machine,
)


@dataclass(frozen=True)
class ClauseProposal:
    """One critic-validated atomic requirement from normalized language through LTLf."""

    normalized_clause: str
    pattern: str
    propositions: tuple[str, ...]
    priority: PriorityLevel
    reward_behavior: str
    template: Template
    ltlf_ast: Formula
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
    dfas: tuple[dict, ...]
    reward_machine: RewardMachineStructure
    text: str


def propose_task(
    environment: EnvironmentDescription,
    task: str,
    engine: GenericEngine,
    history: str = "",
) -> Proposal:
    """Generate one constrained proposal without compiling it."""
    task = task.strip()
    if not task:
        raise ValueError("Tasks must be nonempty")
    if engine.environment != environment:
        raise ValueError("The engine was configured for a different environment")
    selections = engine.propose_task(task, history=history)
    if not 1 <= len(selections) <= MAX_TASK_CLAUSES:
        raise ValueError(f"A task must contain between 1 and {MAX_TASK_CLAUSES} clauses")
    return materialize_proposal(environment, task, selections)


def materialize_proposal(
    environment: EnvironmentDescription,
    task: str,
    selections: Sequence[ProposalSelection],
) -> Proposal:
    """Build deterministic DECLARE and LTLf clauses from validated selections."""
    task = task.strip()
    if not task:
        raise ValueError("Tasks must be nonempty")
    if not 1 <= len(selections) <= MAX_TASK_CLAUSES:
        raise ValueError(f"A task must contain between 1 and {MAX_TASK_CLAUSES} clauses")

    clauses = []
    for selection in selections:
        ltlf_ast = _build_ltlf_formula(selection.pattern, selection.propositions, selection.priority, selection.template)
        clauses.append(ClauseProposal(
            normalized_clause=selection.normalized_clause, pattern=selection.pattern,
            propositions=selection.propositions, priority=selection.priority,
            reward_behavior=describe_reward_behavior(selection.pattern, selection.priority),
            template=selection.template, ltlf_ast=ltlf_ast, ltlf_formula=to_flat_syntax(ltlf_ast),
        ))
    return Proposal(task=task, clauses=tuple(clauses))


def _build_ltlf_formula(
    pattern: str,
    propositions: tuple[str, ...],
    priority: PriorityLevel,
    template: Template,
) -> Formula:
    if pattern in {"Existence", "ExistenceTwo"}:
        return template.to_ltlf()
    if pattern != "Precedence":
        raise ValueError(f"Unsupported executable DECLARE pattern: {pattern!r}")

    preferred, second = (Atomic(proposition) for proposition in propositions)
    if priority is PriorityLevel.HARD:
        return Until(
            Not(second),
            And(preferred, Not(second), Next(Eventually(second))),
        )
    return And(Eventually(preferred), Eventually(second))


def compile_proposal(
    environment: EnvironmentDescription,
    proposal: Proposal,
    mona_executable: str = "mona",
) -> CompilationResult:
    """Compile one proposal deterministically."""
    dfas = compile_dfas(proposal, mona_executable=mona_executable)
    return build_compilation_result(environment, proposal, dfas)


def compile_dfas(
    proposal: Proposal,
    mona_executable: str = "mona",
) -> tuple[dict, ...]:
    """Compile each accepted LTLf clause into one FL-AT/MONA DFA."""
    return tuple(
        compile_dfa(clause.ltlf_formula, mona_executable=mona_executable)
        for clause in proposal.clauses
    )


def build_compilation_result(
    environment: EnvironmentDescription,
    proposal: Proposal,
    dfas: Sequence[dict],
) -> CompilationResult:
    """Build and serialize a task-specific Reward Machine from compiled DFAs."""
    clause_machines = tuple((normalize_reward_machine(dfa, clause.pattern, clause.propositions, clause.priority), clause.propositions) for clause, dfa in zip(proposal.clauses, dfas, strict=True))
    reward_machine = compose_reward_machines(clause_machines)
    return CompilationResult(environment=environment, proposal=proposal, dfas=tuple(dfas),
                             reward_machine=reward_machine, text=serialize_reward_machine(reward_machine))
