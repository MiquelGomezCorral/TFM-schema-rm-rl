"""External proposal engines."""

from .errors import (
    CriticValidationError,
    ImmediateEngineError,
    ProposalValidationError,
    RetryableEngineError,
)
from .generic_engine import GenericEngine
from .provider_engines import AntigravityEngine, OpenAIEngine, OpenCodeEngine
from .structured import CriticResult, ProposalSelection

__all__ = [
    "GenericEngine",
    "OpenAIEngine",
    "OpenCodeEngine",
    "AntigravityEngine",
    "ProposalSelection",
    "ProposalValidationError",
    "CriticResult",
    "CriticValidationError",
    "RetryableEngineError",
    "ImmediateEngineError",
]
