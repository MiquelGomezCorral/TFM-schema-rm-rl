"""Proposal and approved Reward Machine compilation orchestration."""

from dataclasses import dataclass

from nl2ltl.declare.base import Template
from pylogics.syntax.base import Formula

from src.engines import OpenAIEngine
from src.models import EnvironmentDescription

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
    reward: float
    template: Template
    ltlf_ast: Formula
    ltlf_formula: str


@dataclass(frozen=True)
class CompilationResult:
    """Complete in-memory result of an approved compilation."""

    environment: EnvironmentDescription
    proposals: tuple[Proposal, ...]
    ltlf_formulas: tuple[str, ...]
    dfas: tuple[dict, ...]
    flat_reward_machine: dict
    reward_machine: RewardMachineStructure
    text: str


def propose_instructions(
    environment: EnvironmentDescription,
    instructions: list[str] | tuple[str, ...],
    engine: OpenAIEngine,
) -> tuple[Proposal, ...]:
    """Generate constrained proposals without compiling them."""
    normalized_instructions = tuple(instruction.strip() for instruction in instructions)
    if not normalized_instructions:
        raise ValueError("At least one instruction is required")
    if any(not instruction for instruction in normalized_instructions):
        raise ValueError("Instructions must be nonempty")
    if engine.environment != environment:
        raise ValueError("The OpenAI engine was configured for a different environment")

    proposals = []
    for instruction in normalized_instructions:
        selection = engine.propose(instruction)
        ltlf_ast = selection.template.to_ltlf()
        proposals.append(
            Proposal(
                instruction=instruction,
                pattern=selection.pattern,
                propositions=selection.propositions,
                reward=selection.reward,
                template=selection.template,
                ltlf_ast=ltlf_ast,
                ltlf_formula=to_flat_syntax(ltlf_ast),
            )
        )
    return tuple(proposals)


def compile_approved_proposals(
    environment: EnvironmentDescription,
    proposals: tuple[Proposal, ...] | list[Proposal],
    mona_executable: str = "mona",
) -> CompilationResult:
    """Compile proposals that the caller has already approved."""
    proposals = tuple(proposals)
    if not proposals:
        raise ValueError("At least one approved proposal is required")
    from flat_tool import compile_reward_machine

    formulas = tuple(proposal.ltlf_formula for proposal in proposals)
    rewards = tuple(proposal.reward for proposal in proposals)
    flat_result = compile_reward_machine(
        formulas,
        rewards,
        mona_executable=mona_executable,
    )
    reward_machine = normalize_reward_machine(
        flat_result["reward_machine"],
        environment.proposition_ids,
    )
    text = serialize_reward_machine(reward_machine)
    return CompilationResult(
        environment=environment,
        proposals=proposals,
        ltlf_formulas=formulas,
        dfas=tuple(flat_result["dfas"]),
        flat_reward_machine=flat_result["reward_machine"],
        reward_machine=reward_machine,
        text=text,
    )
