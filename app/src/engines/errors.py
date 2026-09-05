"""Engine errors and provider retry classification."""

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)


class ProposalValidationError(ValueError):
    """Report a refused or invalid model proposal."""


class CriticValidationError(ValueError):
    """Report malformed critic output."""


class RetryableEngineError(RuntimeError):
    """A provider or candidate error that consumes one refinement attempt."""


class ImmediateEngineError(RuntimeError):
    """A provider or configuration error that must not be retried."""


def classify_provider_error(error: Exception) -> Exception:
    """Map public OpenAI SDK failures to the application retry policy."""
    if isinstance(error, (ProposalValidationError, CriticValidationError)):
        return RetryableEngineError(str(error))
    if isinstance(error, (RateLimitError, APIConnectionError, APITimeoutError)):
        return RetryableEngineError(str(error))
    if isinstance(error, APIStatusError):
        error_type = RetryableEngineError if error.status_code >= 500 else ImmediateEngineError
        return error_type(str(error))
    if isinstance(error, (AuthenticationError, BadRequestError, PermissionDeniedError)):
        return ImmediateEngineError(str(error))
    if isinstance(error, (RetryableEngineError, ImmediateEngineError)):
        return error
    return ImmediateEngineError(str(error))
