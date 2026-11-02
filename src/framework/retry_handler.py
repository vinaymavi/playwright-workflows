"""Error Classification and Retry Logic

Classifies errors as transient (auto-retry eligible) or permanent (escalate to checkpoint).
Implements exponential backoff retry strategy with configurable thresholds.
"""

import time
from typing import Any, Awaitable, Callable, Optional, TypeVar, 

from .errors import PermanentError, TransientError
from ..utils.logging import setup_logger

logger = setup_logger(__name__)

T = TypeVar("T")


class RetryPolicy:
    """Configuration for automatic retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter_enabled: bool = True):
        """Initialize retry policy.

        Args:
            max_retries: Maximum retry attempts
            initial_backoff_seconds: Starting backoff duration
            max_backoff_seconds: Cap on backoff duration
            backoff_multiplier: Exponential backoff multiplier
            jitter_enabled: Add randomness to prevent thundering herd
        """
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.backoff_multiplier = backoff_multiplier
        self.jitter_enabled = jitter_enabled

    def calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff duration for given attempt number.

        Args:
            attempt: Attempt number (1-based: 1 = first retry, 2 = second retry, etc.)

        Returns:
            Backoff duration in seconds
        """
        backoff = self.initial_backoff_seconds * (self.backoff_multiplier ** (attempt - 1))
        backoff = min(backoff, self.max_backoff_seconds)

        if self.jitter_enabled:
            import random

            jitter = random.uniform(0, backoff)
            backoff = jitter

        return backoff


class ErrorClassifier:
    """Classifies exceptions as transient or permanent."""

    # HTTP status codes that indicate transient errors
    TRANSIENT_HTTP_STATUS = {408, 429, 500, 502, 503, 504}

    # Exception types that are always transient
    TRANSIENT_EXCEPTIONS = (
        TimeoutError,
        ConnectionError,
        BrokenPipeError,
        ConnectionAbortedError,
        ConnectionResetError,
        EOFError,
        asyncio.TimeoutError)

    # Exception types that are always permanent
    PERMANENT_EXCEPTIONS = (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        AssertionError)

    @classmethod
    def is_transient(cls, exception: Exception) -> bool:
        """Determine if exception represents transient error eligible for retry.

        Args:
            exception: The exception to classify

        Returns:
            True if transient (should retry), False if permanent (escalate)
        """
        # Check exception type inheritance
        if isinstance(exception, cls.TRANSIENT_EXCEPTIONS):
            return True

        if isinstance(exception, cls.PERMANENT_EXCEPTIONS):
            return False

        # Check for HTTP-related errors via exception attributes
        if hasattr(exception, "status_code"):
            status = getattr(exception, "status_code")
            if status in cls.TRANSIENT_HTTP_STATUS:
                return True
            if 400 <= status < 500:
                return False
            if status >= 500:
                return True

        # Check exception message for common patterns
        message = str(exception).lower()
        transient_keywords = [
            "timeout",
            "temporary",
            "unavailable",
            "rate limit",
            "connection reset",
            "connection refused",
            "econnreset",
            "econnrefused",
        ]
        for keyword in transient_keywords:
            if keyword in message:
                return True

        permanent_keywords = [
            "invalid",
            "not found",
            "unauthorized",
            "forbidden",
            "assertion",
            "type error",
            "key error",
        ]
        for keyword in permanent_keywords:
            if keyword in message:
                return False

        # Default: treat unknown errors as permanent (fail fast)
        return False

    @classmethod
    def should_retry(
        cls,
        exception: Exception,
        attempt: int,
        max_retries: int) -> bool:
        """Determine if should retry given exception and attempt count.

        Args:
            exception: The exception that occurred
            attempt: Current attempt number (0-based)
            max_retries: Maximum allowed retries

        Returns:
            True if should retry, False if should fail
        """
        if attempt >= max_retries:
            return False

        return cls.is_transient(exception)


async def with_retry(
    func: Callable[..., Awaitable[T]],
    *args,
    policy: Optional[RetryPolicy] = None,
    step_name: str = "unknown",
    **kwargs) -> T:
    """Execute async function with automatic retry on transient errors.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        policy: Retry policy (uses default if not provided)
        step_name: Name of step for logging
        **kwargs: Keyword arguments for func

    Returns:
        Result of func execution

    Raises:
        TransientError: If all retries exhausted for transient error
        PermanentError: If permanent error occurs
    """
    if policy is None:
        policy = RetryPolicy()

    last_exception = None
    is_last_transient = False

    for attempt in range(policy.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            is_last_transient = ErrorClassifier.is_transient(e)

            # Check if retries exhausted
            if attempt >= policy.max_retries:
                logger.error(
                    f"Exhausted retries for step '{step_name}' after {attempt + 1} attempts",
                    extra={
                        "step": step_name,
                        "attempts": attempt + 1,
                        "error_type": type(e).__name__,
                    })
                # Wrap based on error type
                if is_last_transient:
                    raise TransientError(step_name, str(e), e)
                else:
                    raise PermanentError(step_name, str(e), e)

            # Check if error is transient
            if not is_last_transient:
                logger.error(
                    f"Permanent error in step '{step_name}' (attempt {attempt + 1}): {e}",
                    extra={
                        "step": step_name,
                        "attempt": attempt + 1,
                        "error_type": type(e).__name__,
                    })
                raise PermanentError(step_name, str(e), e)

            # Calculate and wait for backoff
            backoff = policy.calculate_backoff(attempt + 1)
            logger.warning(
                f"Transient error in step '{step_name}' (attempt {attempt + 1}/{policy.max_retries + 1}): {e}. "
                f"Retrying after {backoff:.2f}s",
                extra={
                    "step": step_name,
                    "attempt": attempt + 1,
                    "error_type": type(e).__name__,
                    "backoff_seconds": backoff,
                })
            await asyncio.sleep(backoff)

    # Should never reach here
    if last_exception:
        if is_last_transient:
            raise TransientError(step_name, str(last_exception), last_exception)
        else:
            raise PermanentError(step_name, str(last_exception), last_exception)


def with_retry_sync(
    func: Callable[..., T],
    *args,
    policy: Optional[RetryPolicy] = None,
    step_name: str = "unknown",
    **kwargs) -> T:
    """Execute sync function with automatic retry on transient errors.

    Args:
        func: Sync function to execute
        *args: Positional arguments for func
        policy: Retry policy (uses default if not provided)
        step_name: Name of step for logging
        **kwargs: Keyword arguments for func

    Returns:
        Result of func execution

    Raises:
        TransientError: If all retries exhausted for transient error
        PermanentError: If permanent error occurs
    """
    if policy is None:
        policy = RetryPolicy()

    last_exception = None
    is_last_transient = False

    for attempt in range(policy.max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            is_last_transient = ErrorClassifier.is_transient(e)

            # Check if retries exhausted
            if attempt >= policy.max_retries:
                logger.error(
                    f"Exhausted retries for step '{step_name}' after {attempt + 1} attempts",
                    extra={
                        "step": step_name,
                        "attempts": attempt + 1,
                        "error_type": type(e).__name__,
                    })
                # Wrap based on error type
                if is_last_transient:
                    raise TransientError(step_name, str(e), e)
                else:
                    raise PermanentError(step_name, str(e), e)

            # Check if error is transient
            if not is_last_transient:
                logger.error(
                    f"Permanent error in step '{step_name}' (attempt {attempt + 1}): {e}",
                    extra={
                        "step": step_name,
                        "attempt": attempt + 1,
                        "error_type": type(e).__name__,
                    })
                raise PermanentError(step_name, str(e), e)

            # Calculate and wait for backoff
            backoff = policy.calculate_backoff(attempt + 1)
            logger.warning(
                f"Transient error in step '{step_name}' (attempt {attempt + 1}/{policy.max_retries + 1}): {e}. "
                f"Retrying after {backoff:.2f}s",
                extra={
                    "step": step_name,
                    "attempt": attempt + 1,
                    "error_type": type(e).__name__,
                    "backoff_seconds": backoff,
                })
            time.sleep(backoff)

    # Should never reach here
    if last_exception:
        if is_last_transient:
            raise TransientError(step_name, str(last_exception), last_exception)
        else:
            raise PermanentError(step_name, str(last_exception), last_exception)
