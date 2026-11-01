"""Unit tests for errors module."""

import pytest

from src.framework.errors import (
    PermanentError,
    StepError,
    TransientError,
    WorkflowCancelled,
    WorkflowCheckpointRequired,
    WorkflowCheckpointTimeout,
    WorkflowError,
    WorkflowResourceExhausted,
    WorkflowSessionExpired,
    WorkflowStateError,
    WorkflowValidationError,
)


class TestWorkflowError:
    """Test base WorkflowError class."""

    def test_init_message(self):
        """Test basic error initialization with message."""
        error = WorkflowError("Test error")
        assert error.message == "Test error"
        assert error.cause is None

    def test_init_with_cause(self):
        """Test error initialization with cause."""
        cause = ValueError("Original error")
        error = WorkflowError("Test error", cause=cause)
        assert error.cause is cause

    def test_str_representation(self):
        """Test string representation."""
        error = WorkflowError("Test error")
        assert "Test error" in str(error)


class TestCheckpointErrors:
    """Test checkpoint-related exceptions."""

    def test_checkpoint_required(self):
        """Test WorkflowCheckpointRequired."""
        error = WorkflowCheckpointRequired("Awaiting user decision")
        assert isinstance(error, WorkflowError)
        assert "Awaiting user decision" in str(error)

    def test_checkpoint_timeout(self):
        """Test WorkflowCheckpointTimeout."""
        error = WorkflowCheckpointTimeout("Timeout waiting for decision")
        assert isinstance(error, WorkflowError)

    def test_checkpoint_cancel(self):
        """Test WorkflowCancelled."""
        error = WorkflowCancelled("User cancelled workflow")
        assert isinstance(error, WorkflowError)


class TestSessionErrors:
    """Test session-related exceptions."""

    def test_session_expired(self):
        """Test WorkflowSessionExpired."""
        error = WorkflowSessionExpired("Session invalid")
        assert isinstance(error, WorkflowError)

    def test_resource_exhausted(self):
        """Test WorkflowResourceExhausted."""
        error = WorkflowResourceExhausted("Too many browser pages")
        assert isinstance(error, WorkflowError)


class TestStepErrors:
    """Test step execution errors."""

    def test_step_error(self):
        """Test base StepError class."""
        error = StepError("my_step", "Step failed", error_type="transient")
        assert error.step_name == "my_step"
        assert error.error_type == "transient"
        assert "my_step" in str(error)

    def test_transient_error(self):
        """Test TransientError."""
        cause = TimeoutError("Connection timeout")
        error = TransientError("navigate_step", "Timeout occurred", cause=cause)
        assert error.step_name == "navigate_step"
        assert error.error_type == "transient"
        assert error.cause is cause

    def test_permanent_error(self):
        """Test PermanentError."""
        cause = ValueError("Invalid selector")
        error = PermanentError("click_step", "Invalid selector", cause=cause)
        assert error.step_name == "click_step"
        assert error.error_type == "permanent"
        assert error.cause is cause


class TestValidationErrors:
    """Test validation-related errors."""

    def test_validation_error(self):
        """Test WorkflowValidationError."""
        error = WorkflowValidationError("Invalid input parameters")
        assert isinstance(error, WorkflowError)


class TestStateErrors:
    """Test state machine errors."""

    def test_state_error(self):
        """Test WorkflowStateError."""
        error = WorkflowStateError(
            "Cannot pause non-running execution",
            current_state="paused",
            requested_state="paused",
        )
        assert error.current_state == "paused"
        assert error.requested_state == "paused"
        assert isinstance(error, WorkflowError)


class TestErrorInheritance:
    """Test error hierarchy and inheritance."""

    def test_all_errors_inherit_from_workflow_error(self):
        """Test that all custom errors inherit from WorkflowError."""
        errors = [
            WorkflowCheckpointRequired("message"),
            WorkflowCheckpointTimeout("message"),
            WorkflowCancelled("message"),
            WorkflowSessionExpired("message"),
            WorkflowResourceExhausted("message"),
            WorkflowValidationError("message"),
            StepError("step", "message"),
            TransientError("step", "message"),
            PermanentError("step", "message"),
            WorkflowStateError("message"),
        ]

        for error in errors:
            assert isinstance(error, WorkflowError)

    def test_step_errors_are_workflow_errors(self):
        """Test that step errors are workflow errors."""
        assert issubclass(StepError, WorkflowError)
        assert issubclass(TransientError, StepError)
        assert issubclass(PermanentError, StepError)
