"""Action Base Class for Reusable Workflow Steps

Provides the Action base class that encapsulates reusable workflow logic.
Actions inherit logging, error handling, and retry behavior from the framework.
"""

import asyncio
import inspect
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..utils.logging import setup_logger
from .errors import PermanentError, TransientError
from .execution import Execution, StepResult
from .retry_handler import ErrorClassifier, RetryPolicy, with_retry, with_retry_sync

logger = setup_logger(__name__)


class Action(ABC):
    """Base class for reusable workflow actions.

    An Action encapsulates a reusable step that can be executed by multiple workflows.
    Actions support:
    - Automatic logging and error handling
    - Retry logic with exponential backoff
    - Dependency management (actions that must complete before this one)
    - Step result tracking for execution history

    Subclasses must implement the execute() method.

    Example:
        class FillFormAction(Action):
            async def execute(self, form_data: Dict[str, str]) -> Dict[str, Any]:
                '''Fill form fields with provided data.'''
                page = self.workflow_context.page
                for selector, value in form_data.items():
                    await page.fill(selector, value)
                return {"status": "success"}
    """

    def __init__(
        self,
        workflow_context: Any,
        name: Optional[str] = None,
        max_retries: int = 3,
        requires: Optional[List[str]] = None,
    ):
        """Initialize an action with workflow context and configuration.

        Args:
            workflow_context: Reference to parent workflow instance
            name: Action name for logging (defaults to class name)
            max_retries: Maximum retry attempts for transient errors
            requires: List of action names that must complete before this action

        Raises:
            ValueError: If workflow_context is None
        """
        if workflow_context is None:
            raise ValueError("workflow_context cannot be None")

        self.workflow_context = workflow_context
        self.name = name or self.__class__.__name__
        self.max_retries = max_retries
        self.requires = requires or []
        self._retry_policy = RetryPolicy(max_retries=max_retries)

        logger.debug(f"Initialized action: {self.name}")

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the action.

        Subclasses must implement this method with async or sync code.
        The framework will wrap it with retry, logging, and error handling.

        Args:
            **kwargs: Action-specific keyword arguments

        Returns:
            Result of the action execution

        Raises:
            PermanentError: For errors that should not be retried
            TransientError: For temporary errors that should be retried
        """
        pass

    async def run(self, **kwargs) -> Any:
        """Execute the action with retry logic, logging, and error handling.

        This is the public interface to execute the action. It wraps the
        execute() method with automatic retry, structured logging, and
        error classification.

        Args:
            **kwargs: Action-specific keyword arguments

        Returns:
            Result of the action execution

        Raises:
            PermanentError: For permanent errors (already retried)
            TransientError: For transient errors (already retried)
        """
        logger.debug(f"Running action: {self.name}")

        try:
            if inspect.iscoroutinefunction(self.execute):
                result = await with_retry(
                    self.execute,
                    policy=self._retry_policy,
                    step_name=self.name,
                    **kwargs,
                )
            else:
                result = with_retry_sync(
                    self.execute,
                    policy=self._retry_policy,
                    step_name=self.name,
                    **kwargs,
                )

            logger.debug(f"Action succeeded: {self.name}")

            # Create step result for execution tracking
            step_result = StepResult(
                name=self.name,
                status="success",
                output=result if not inspect.iscoroutine(result) else None,
            )

            # Track result if execution tracking is available
            self._track_step_result(step_result)

            return result

        except Exception as e:
            # Classify error
            is_transient = ErrorClassifier.is_transient(e)

            # Create step result with error
            step_result = StepResult(
                name=self.name,
                status="failed",
                error=str(e),
                retry_count=self.max_retries if not is_transient else 0,
            )

            # Track result if execution tracking is available
            self._track_step_result(step_result)

            if is_transient:
                logger.error(
                    f"Transient error in action '{self.name}' (exhausted retries): {e}",
                    extra={
                        "action": self.name,
                        "error_type": type(e).__name__,
                        "max_retries": self.max_retries,
                    },
                )
                raise TransientError(self.name, str(e), cause=e)
            else:
                logger.error(
                    f"Permanent error in action '{self.name}': {e}",
                    extra={"action": self.name, "error_type": type(e).__name__},
                )
                raise PermanentError(self.name, str(e), cause=e)

    def _track_step_result(self, step_result: StepResult) -> None:
        """Track step result in execution if available.

        Args:
            step_result: The step result to track
        """
        if hasattr(self.workflow_context, "_execution") and self.workflow_context._execution:
            self.workflow_context._execution.add_step_result(step_result)

    def get_dependencies(self) -> List[str]:
        """Get list of action names this action depends on.

        Returns:
            List of required action names
        """
        return self.requires

    def has_dependency(self, action_name: str) -> bool:
        """Check if this action depends on another action.

        Args:
            action_name: Name of the action to check

        Returns:
            True if this action depends on the given action
        """
        return action_name in self.requires

    def __repr__(self) -> str:
        """String representation of the action."""
        return f"{self.__class__.__name__}(name={self.name}, requires={self.requires})"
