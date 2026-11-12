"""Engine errors and provider retry classification."""

from collections.abc import Callable

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)

from src.config import Configuration


class ProposalValidationError(ValueError):
    """Report a refused or invalid model proposal."""


class CriticValidationError(ValueError):
    """Report malformed critic output."""


class RetryableEngineError(RuntimeError):
    """A provider or candidate error that consumes one refinement attempt."""


class ImmediateEngineError(RuntimeError):
    """A provider or configuration error that must not be retried."""


class CriticUnavailableError(ImmediateEngineError):
    """The critic failed every request on one candidate; the run ends without a new candidate."""


class RunCancelled(Exception):  # noqa: N818  the pipeline names this signal, not an error
    """Report a run the client stopped; it ends both provider retry loops.

    It lives here because the engine's retry loop raises it, and ``src.engines``
    cannot import ``src.utils`` without a circular import.
    """


def retry_critic[T](request: Callable[[], T], warn: Callable[[str], None] | None = None) -> T:
    """Repeat a failed critic request on the same candidate; it uses no candidate attempt.

    A provider outage or critic output that cannot be parsed repeats the request, at most
    ``Configuration.UNCOUNTED_RETRIES`` times. Any verdict, a rejection included, returns at once.

    Raises:
        CriticUnavailableError: Every request failed; the message names the last cause.
    """
    requests = Configuration.UNCOUNTED_RETRIES + 1
    for number in range(1, requests + 1):
        try:
            return request()
        except (RetryableEngineError, CriticValidationError) as error:
            last_error = error
            if warn is not None:
                warn(f"request {number}/{requests} failed: {error}")
    raise CriticUnavailableError(
        f"Critic failed {requests} requests in a row on the same candidate. "
        f"Last error: {last_error}"
    ) from last_error


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
