"""External proposal engines."""

from .errors import (
    CriticUnavailableError,
    CriticValidationError,
    ImmediateEngineError,
    ProposalValidationError,
    RetryableEngineError,
    RunCancelled,
    retry_critic,
)
from .generic_engine import GenericEngine
from .provider_engines import AntigravityEngine, OpenAIEngine, OpenCodeEngine
from .structured import CriticResult, ProposalSelection
