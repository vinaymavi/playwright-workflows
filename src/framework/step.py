"""Step Decorator for Workflow Steps

Provides @step decorator that wraps step methods with:
- Automatic error classification (transient vs permanent)
- Retry logic with exponential backoff
- Structured logging
- Step result tracking
"""

import functools
import inspect
from typing import Any, Callable, Optional, TypeVar

from ..utils.logging import setup_logger
from .errors import PermanentError, TransientError, WorkflowCheckpointRequired
from .execution import StepResult
from .retry_handler import ErrorClassifier, RetryPolicy, with_retry, with_retry_sync

logger = setup_logger(__name__)

T = TypeVar("T")


def step(
    func: Optional[Callable] = None,
    *,
    max_retries: int = 3,
    timeout_seconds: Optional[int] = None,
    description: Optional[str] = None,
):
    """Decorator for workflow step methods.

    Wraps step execution with:
    - Error classification (transient vs permanent)
    - Automatic retry with exponential backoff
    - Structured logging
    - Execution tracking

    Usage:
        @step(max_retries=3, timeout_seconds=30)
        async def fill_form(self, form_data):
            # step implementation
            pass

        @step()
        def validate_data(self, data):
            # step implementation
            pass

    Args:
        func: The step function (passed by decorator)
        max_retries: Maximum retry attempts for transient errors
        timeout_seconds: Optional timeout for the step
        description: Optional description for logging

    Returns:
        Decorated function that wraps step with error handling
    """

    def decorator(f: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(f)
        step_name = description or f.__name__
        retry_policy = RetryPolicy(max_retries=max_retries)

        if is_async:

            @functools.wraps(f)
            async def async_wrapper(self, *args, **kwargs) -> Any:
                """Async step wrapper with retry and error handling."""
                logger.debug(f"Starting step: {step_name}")

                try:
                    result = await with_retry(
                        f,
                        self,
                        *args,
                        policy=retry_policy,
                        step_name=step_name,
                        **kwargs,
                    )

                    logger.debug(f"Step succeeded: {step_name}")

                    # Create step result
                    step_result = StepResult(
                        name=step_name,
                        status="success",
                        output=result if not inspect.iscoroutine(result) else None,
                    )

                    # Track result if execution tracking is available
                    if hasattr(self, "_execution") and self._execution:
                        self._execution.add_step_result(step_result)

                    return result

                except WorkflowCheckpointRequired:
                    # Checkpoints are not errors—re-raise to trigger pause
                    logger.info(f"Step paused at checkpoint: {step_name}")
                    raise

                except Exception as e:
                    # Classify error
                    is_transient = ErrorClassifier.is_transient(e)

                    # Create step result with error
                    step_result = StepResult(
                        name=step_name,
                        status="failed",
                        error=str(e),
                        retry_count=retry_policy.max_retries if not is_transient else 0,
                    )

                    # Track result if execution tracking is available
                    if hasattr(self, "_execution") and self._execution:
                        self._execution.add_step_result(step_result)

                    if is_transient:
                        logger.error(
                            f"Transient error in step '{step_name}' (exhausted retries): {e}",
                            extra={
                                "step": step_name,
                                "error_type": type(e).__name__,
                                "max_retries": max_retries,
                            },
                        )
                        raise TransientError(step_name, str(e), cause=e)
                    else:
                        logger.error(
                            f"Permanent error in step '{step_name}': {e}",
                            extra={"step": step_name, "error_type": type(e).__name__},
                        )
                        raise PermanentError(step_name, str(e), cause=e)

            return async_wrapper

        else:

            @functools.wraps(f)
            def sync_wrapper(self, *args, **kwargs) -> Any:
                """Sync step wrapper with retry and error handling."""
                logger.debug(f"Starting step: {step_name}")

                try:
                    result = with_retry_sync(
                        f,
                        self,
                        *args,
                        policy=retry_policy,
                        step_name=step_name,
                        **kwargs,
                    )

                    logger.debug(f"Step succeeded: {step_name}")

                    # Create step result
                    step_result = StepResult(
                        name=step_name,
                        status="success",
                        output=result,
                    )

                    # Track result if execution tracking is available
                    if hasattr(self, "_execution") and self._execution:
                        self._execution.add_step_result(step_result)

                    return result

                except WorkflowCheckpointRequired:
                    # Checkpoints are not errors—re-raise to trigger pause
                    logger.info(f"Step paused at checkpoint: {step_name}")
                    raise

                except Exception as e:
                    # Classify error
                    is_transient = ErrorClassifier.is_transient(e)

                    # Create step result with error
                    step_result = StepResult(
                        name=step_name,
                        status="failed",
                        error=str(e),
                        retry_count=retry_policy.max_retries if not is_transient else 0,
                    )

                    # Track result if execution tracking is available
                    if hasattr(self, "_execution") and self._execution:
                        self._execution.add_step_result(step_result)

                    if is_transient:
                        logger.error(
                            f"Transient error in step '{step_name}' (exhausted retries): {e}",
                            extra={
                                "step": step_name,
                                "error_type": type(e).__name__,
                                "max_retries": max_retries,
                            },
                        )
                        raise TransientError(step_name, str(e), cause=e)
                    else:
                        logger.error(
                            f"Permanent error in step '{step_name}': {e}",
                            extra={"step": step_name, "error_type": type(e).__name__},
                        )
                        raise PermanentError(step_name, str(e), cause=e)

            return sync_wrapper

    # Handle being called with or without parentheses
    if func is None:
        return decorator
    else:
        return decorator(func)
