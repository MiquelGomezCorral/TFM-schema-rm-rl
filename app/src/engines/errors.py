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


class RunCancelled(Exception):  # noqa: N818  the pipeline names this signal, not an error
    """Report a run the client stopped; it ends both provider retry loops.

    It lives here because the engine's retry loop raises it, and ``src.engines``
    cannot import ``src.utils`` without a circular import.
    """


def classify_provider_error(error: Exception) -> Exception:
    """Map public OpenAI SDK failures to the application retry policy."""
    if isinstance(error, (ProposalValidationError, CriticValidationError)):
        return error  # a content failure stays one, so its feedback reaches the generator
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
