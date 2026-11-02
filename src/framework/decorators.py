"""Decorators for workflow steps with retry, logging, and error handling."""

import asyncio
import functools
import time
from typing import Any, Callable, Optional, TypeVar

from .errors import PermanentError, TransientError, WorkflowError
from .retry_handler import RetryPolicy, with_retry, with_retry_sync
from ..utils.logging import setup_logger

logger = setup_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def step(
    name: Optional[str] = None,
    max_retries: int = 3,
    backoff_strategy: str = "exponential",
    retry_on_errors: Optional[list[str]] = None,
    fail_on_errors: Optional[list[str]] = None,
    timeout_ms: Optional[int] = None) -> Callable[[F], F]:
    """
    Decorator for workflow methods to enable retry, logging, and error classification.

    The decorator wraps method execution with:
    - Automatic structured logging
    - Retry logic for transient errors
    - Error classification (transient vs permanent)
    - Checkpoint escalation for permanent errors
    - Execution step tracking

    Usage:
        class MyWorkflow(Workflow):
            @step(
                name="login",
                max_retries=3,
                retry_on_errors=['TimeoutError', 'ConnectError'],
                fail_on_errors=['ValidationError']
            )
            async def login_step(self, username, password):
                await self.fill("#username", username)
                await self.fill("#password", password)
                await self.click("button[type='submit']")

    Args:
        name: Optional step name (defaults to function name)
        max_retries: Maximum number of retry attempts for transient errors
        backoff_strategy: Retry strategy ("exponential", "linear", or "constant")
        retry_on_errors: List of exception type names to treat as transient
        fail_on_errors: List of exception type names to treat as permanent
        timeout_ms: Optional timeout in milliseconds

    Raises:
        PermanentError: For permanent errors that require checkpoint intervention
        TransientError: For transient errors that exhausted retries
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        step_name = name or func.__name__
        is_async = asyncio.iscoroutinefunction(func)

        # Build retry policy based on decorator args
        retry_policy = RetryPolicy(
            max_retries=max_retries,
            initial_backoff_seconds=1.0,
            max_backoff_seconds=60.0,
            backoff_multiplier=2.0,
            jitter_enabled=True)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Extract workflow instance for logging and lifecycle hooks
                workflow = None
                if args and hasattr(args[0], "logger"):
                    workflow = args[0]

                if workflow:
                    workflow.logger.info(
                        f"Step started: {step_name}",
                        extra={"extra_fields": {"step_name": step_name}})
                    await workflow.on_step_start(step_name, 0)

                try:
                    # Execute with retry logic
                    result = await with_retry(
                        func,
                        *args,
                        policy=retry_policy,
                        step_name=step_name,
                        **kwargs)

                    if workflow:
                        workflow.logger.info(
                            f"Step completed: {step_name}",
                            extra={"extra_fields": {"step_name": step_name}})
                        await workflow.on_step_complete(step_name, result)

                    return result

                except PermanentError as e:
                    if workflow:
                        workflow.logger.error(
                            f"Step failed (permanent): {step_name}",
                            extra={"extra_fields": {"step_name": step_name}})
                        await workflow.on_step_error(step_name, e)
                    raise

                except TransientError as e:
                    if workflow:
                        workflow.logger.error(
                            f"Step failed (transient exhausted): {step_name}",
                            extra={"extra_fields": {"step_name": step_name}})
                        await workflow.on_step_error(step_name, e)
                    raise

                except Exception as e:
                    if workflow:
                        workflow.logger.error(
                            f"Step failed (unexpected): {step_name}",
                            extra={"extra_fields": {"step_name": step_name}})
                        await workflow.on_step_error(step_name, e)
                    raise WorkflowError(
                        f"Step {step_name} failed: {e}"
                    ) from e

            return async_wrapper  # type: ignore

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Extract workflow instance for logging and lifecycle hooks
                workflow = None
                if args and hasattr(args[0], "logger"):
                    workflow = args[0]

                if workflow:
                    workflow.logger.info(
                        f"Step started: {step_name}",
                        extra={"extra_fields": {"step_name": step_name}})

                try:
                    # Execute with retry logic
                    result = with_retry_sync(
                        func,
                        *args,
                        policy=retry_policy,
                        step_name=step_name,
                        **kwargs)

                    if workflow:
                        workflow.logger.info(
                            f"Step completed: {step_name}",
                            extra={"extra_fields": {"step_name": step_name}})

                    return result

                except PermanentError:
                    if workflow:
                        workflow.logger.error(
                            f"Step failed (permanent): {step_name}",
                            extra={"extra_fields": {"step_name": step_name}})
                    raise

                except TransientError:
                    if workflow:
                        workflow.logger.error(
                            f"Step failed (transient exhausted): {step_name}",
                            extra={"extra_fields": {"step_name": step_name}})
                    raise

                except Exception as e:
                    if workflow:
                        workflow.logger.error(
                            f"Step failed (unexpected): {step_name}",
                            extra={"extra_fields": {"step_name": step_name}})
                    raise WorkflowError(
                        f"Step {step_name} failed: {e}"
                    ) from e

            return sync_wrapper  # type: ignore

    return decorator


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay_seconds: float = 60.0,
    jitter_enabled: bool = True,
    on_retry: Optional[Callable[[int, Exception], None]] = None) -> Callable[[F], F]:
    """
    Simple retry decorator for any async or sync function.

    This is a lower-level decorator compared to @step. Use for functions
    that don't need full workflow integration.

    Args:
        max_attempts: Maximum number of attempts
        delay_seconds: Initial delay between retries
        backoff_multiplier: Exponential backoff multiplier
        max_delay_seconds: Maximum delay between retries
        jitter_enabled: Add random jitter to delays
        on_retry: Optional callback(attempt, exception) called on retry

    Example:
        @retry(max_attempts=3, delay_seconds=1.0)
        async def fetch_data(url):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    return await resp.json()
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        is_async = asyncio.iscoroutinefunction(func)

        retry_policy = RetryPolicy(
            max_retries=max_attempts - 1,  # Convert attempts to retries
            initial_backoff_seconds=delay_seconds,
            max_backoff_seconds=max_delay_seconds,
            backoff_multiplier=backoff_multiplier,
            jitter_enabled=jitter_enabled)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                attempt = 0
                last_error = None

                while attempt < max_attempts:
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        attempt += 1
                        last_error = e

                        if attempt >= max_attempts:
                            raise

                        if on_retry:
                            on_retry(attempt, e)

                        # Calculate backoff
                        backoff = retry_policy.calculate_backoff(attempt)
                        logger.warning(
                            f"{func.__name__} attempt {attempt} failed: {e}, "
                            f"retrying in {backoff}s"
                        )
                        await asyncio.sleep(backoff)

                raise last_error or Exception(f"{func.__name__} failed after {max_attempts} attempts")

            return async_wrapper  # type: ignore

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                attempt = 0
                last_error = None

                while attempt < max_attempts:
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        attempt += 1
                        last_error = e

                        if attempt >= max_attempts:
                            raise

                        if on_retry:
                            on_retry(attempt, e)

                        # Calculate backoff
                        backoff = retry_policy.calculate_backoff(attempt)
                        logger.warning(
                            f"{func.__name__} attempt {attempt} failed: {e}, "
                            f"retrying in {backoff}s"
                        )
                        time.sleep(backoff)

                raise last_error or Exception(f"{func.__name__} failed after {max_attempts} attempts")

            return sync_wrapper  # type: ignore

    return decorator
