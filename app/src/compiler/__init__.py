"""Formal Reward Machine compilation pipeline."""

from .pipeline import (
    ClauseProposal,
    CompilationResult,
    Proposal,
    build_compilation_result,
    compile_dfas,
    materialize_proposal,
)
from .reward_layer import RewardSwitches
from .reward_machine import evaluate_boolean_guard, parse_boolean_guard
from .rm_format import (
    PaperRewardMachine,
    RuntimeTransition,
    RuntimeValidationError,
    compiler_machine_to_paper,
    machine_too_large,
    machine_view,
    machine_view_note,
    paper_to_structure,
    parse_paper_reward_machine,
    parse_reward_machine,
    serialize_paper_reward_machine,
    serialize_reward_machine,
)
