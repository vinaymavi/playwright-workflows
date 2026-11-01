"""Workflow framework exception hierarchy."""

from typing import Optional


class WorkflowError(Exception):
    """Base exception for all workflow-related errors."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        """
        Initialize workflow error.

        Args:
            message: Error message
            cause: Optional underlying exception
        """
        self.message = message
        self.cause = cause
        super().__init__(message)


class WorkflowCheckpointRequired(WorkflowError):
    """Raised when workflow needs agent decision before continuing."""

    pass


class WorkflowCheckpointTimeout(WorkflowError):
    """Raised when checkpoint decision not received within timeout."""

    pass


class WorkflowCancelled(WorkflowError):
    """Raised when agent/user cancels workflow at checkpoint."""

    pass


class WorkflowSessionExpired(WorkflowError):
    """Raised when browser session is invalid (401/403 Unauthorized/Forbidden)."""

    pass


class WorkflowResourceExhausted(WorkflowError):
    """Raised when execution exceeds resource quota (memory, browser pages, etc)."""

    pass


class WorkflowValidationError(WorkflowError):
    """Raised when workflow input or state validation fails."""

    pass


class StepError(WorkflowError):
    """Base error for step execution failures."""

    def __init__(
        self,
        step_name: str,
        message: str,
        error_type: str = "unknown",
        cause: Optional[Exception] = None,
    ):
        """
        Initialize step error.

        Args:
            step_name: Name of step that failed
            message: Error message
            error_type: Classification (transient, permanent, etc)
            cause: Underlying exception
        """
        self.step_name = step_name
        self.error_type = error_type
        super().__init__(f"Step '{step_name}' failed: {message}", cause=cause)


class TransientError(StepError):
    """Step failed with transient error (eligible for retry)."""

    def __init__(self, step_name: str, message: str, cause: Optional[Exception] = None):
        """Initialize transient error."""
        super().__init__(step_name, message, "transient", cause)


class PermanentError(StepError):
    """Step failed with permanent error (requires agent decision)."""

    def __init__(self, step_name: str, message: str, cause: Optional[Exception] = None):
        """Initialize permanent error."""
        super().__init__(step_name, message, "permanent", cause)


class WorkflowStateError(WorkflowError):
    """Raised when workflow state machine encounters invalid transition."""

    def __init__(
        self,
        message: str = "Invalid state transition",
        current_state: Optional[str] = None,
        requested_state: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize state error.

        Args:
            message: Description of invalid transition
            current_state: Current execution state
            requested_state: State transition that was attempted
            cause: Underlying exception
        """
        self.current_state = current_state
        self.requested_state = requested_state
        super().__init__(message, cause=cause)
