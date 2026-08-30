"""Proposal and approved Reward Machine compilation orchestration."""

from dataclasses import dataclass

from nl2ltl.declare.base import Template
from pylogics.syntax.base import And, Formula, Not
from pylogics.syntax.ltl import Atomic, Eventually, Next, Until

from src.engines import OpenAIEngine
from src.models import (
    EnvironmentDescription,
    PriorityLevel,
    describe_reward_behavior,
)

from .ltlf import to_flat_syntax
from .reward_machine import (
    RewardMachineStructure,
    normalize_reward_machine,
    serialize_reward_machine,
)


@dataclass(frozen=True)
class Proposal:
    """One reviewed unit from instruction through LTLf."""

    instruction: str
    pattern: str
    propositions: tuple[str, ...]
    priority: PriorityLevel
    reward_behavior: str
    template: Template
    ltlf_ast: Formula
    ltlf_formula: str


@dataclass(frozen=True)
class CompilationResult:
    """Complete in-memory result of an approved compilation."""

    environment: EnvironmentDescription
    proposal: Proposal
    dfa: dict
    reward_machine: RewardMachineStructure
    text: str


def propose_instructions(
    environment: EnvironmentDescription,
    instructions: list[str] | tuple[str, ...],
    engine: OpenAIEngine,
    priorities: list[str] | tuple[str, ...] | None = None,
) -> tuple[Proposal, ...]:
    """Generate constrained proposals without compiling them."""
    normalized_instructions = tuple(instruction.strip() for instruction in instructions)
    if not normalized_instructions:
        raise ValueError("At least one instruction is required")
    if any(not instruction for instruction in normalized_instructions):
        raise ValueError("Instructions must be nonempty")
    if engine.environment != environment:
        raise ValueError("The OpenAI engine was configured for a different environment")
    priority_overrides = tuple(priorities or ())
    if priority_overrides and len(priority_overrides) != len(normalized_instructions):
        raise ValueError("Provide exactly one priority value per instruction")
    if not priority_overrides:
        priority_overrides = ("infer",) * len(normalized_instructions)

    proposals = []
    for instruction, priority_override in zip(
        normalized_instructions,
        priority_overrides,
        strict=True,
    ):
        selection = engine.propose(instruction, priority_override)
        ltlf_ast = _build_ltlf_formula(
            selection.pattern,
            selection.propositions,
            selection.priority,
            selection.template,
        )
        proposals.append(
            Proposal(
                instruction=instruction,
                pattern=selection.pattern,
                propositions=selection.propositions,
                priority=selection.priority,
                reward_behavior=describe_reward_behavior(
                    selection.pattern,
                    selection.priority,
                ),
                template=selection.template,
                ltlf_ast=ltlf_ast,
                ltlf_formula=to_flat_syntax(ltlf_ast),
            )
        )
    return tuple(proposals)


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


def compile_approved_proposals(
    environment: EnvironmentDescription,
    proposals: tuple[Proposal, ...] | list[Proposal],
    mona_executable: str = "mona",
) -> tuple[CompilationResult, ...]:
    """Compile each proposal independently after caller approval."""
    proposals = tuple(proposals)
    if not proposals:
        raise ValueError("At least one approved proposal is required")
    from flat_tool import compile_dfa

    results = []
    for proposal in proposals:
        dfa = compile_dfa(
            proposal.ltlf_formula,
            mona_executable=mona_executable,
        )
        reward_machine = normalize_reward_machine(
            dfa,
            proposal.pattern,
            proposal.propositions,
            proposal.priority,
        )
        results.append(
            CompilationResult(
                environment=environment,
                proposal=proposal,
                dfa=dfa,
                reward_machine=reward_machine,
                text=serialize_reward_machine(reward_machine),
            )
        )
    return tuple(results)
