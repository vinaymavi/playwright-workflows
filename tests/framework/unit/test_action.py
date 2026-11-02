"""Unit tests for Action base class."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any, Dict

from src.framework.action import Action
from src.framework.errors import PermanentError, TransientError
from src.framework.execution import StepResult


class DummyAction(Action):
    """Dummy implementation of Action for testing."""

    async def execute(self, **kwargs) -> Dict[str, str]:
        return {"result": "success", **kwargs}


class FailingAction(Action):
    """Action that raises an error."""

    async def execute(self, error_type: str = "permanent", **kwargs) -> None:
        if error_type == "permanent":
            raise ValueError("Permanent error")
        else:
            raise TimeoutError("Transient error")


class SyncAction(Action):
    """Action with sync execute method."""

    def execute(self, **kwargs) -> Dict[str, str]:
        return {"result": "sync", **kwargs}


class TestActionInitialization:
    """Tests for Action initialization."""

    def test_init_with_workflow_context(self):
        """Test Action initialization with workflow context."""
        workflow = MagicMock()
        action = DummyAction(workflow)

        assert action.workflow_context is workflow
        assert action.name == "DummyAction"
        assert action.max_retries == 3
        assert action.requires == []

    def test_init_with_custom_name(self):
        """Test Action initialization with custom name."""
        workflow = MagicMock()
        action = DummyAction(workflow, name="custom_action")

        assert action.name == "custom_action"

    def test_init_with_requires(self):
        """Test Action initialization with dependencies."""
        workflow = MagicMock()
        requires = ["action1", "action2"]
        action = DummyAction(workflow, requires=requires)

        assert action.requires == requires

    def test_init_with_custom_max_retries(self):
        """Test Action initialization with custom max_retries."""
        workflow = MagicMock()
        action = DummyAction(workflow, max_retries=5)

        assert action.max_retries == 5

    def test_init_fails_with_none_context(self):
        """Test that Action raises error with None workflow_context."""
        with pytest.raises(ValueError, match="workflow_context cannot be None"):
            DummyAction(None)


@pytest.mark.asyncio
class TestActionExecution:
    """Tests for Action execution."""

    async def test_run_executes_async_action(self):
        """Test that run() executes async execute() method."""
        workflow = MagicMock()
        action = DummyAction(workflow)

        result = await action.run(key1="value1", key2="value2")

        assert result["result"] == "success"
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"

    async def test_run_executes_sync_action(self):
        """Test that run() executes sync execute() method."""
        workflow = MagicMock()
        action = SyncAction(workflow)

        result = await action.run(key="value")

        assert result["result"] == "sync"
        assert result["key"] == "value"

    async def test_run_with_empty_kwargs(self):
        """Test that run() works with no kwargs."""
        workflow = MagicMock()
        action = DummyAction(workflow)

        result = await action.run()

        assert result["result"] == "success"

    async def test_run_tracks_step_result(self):
        """Test that run() tracks step result in execution."""
        workflow = MagicMock()
        execution = MagicMock()
        workflow._execution = execution

        action = DummyAction(workflow, name="test_action")
        await action.run()

        # Verify add_step_result was called
        execution.add_step_result.assert_called_once()
        step_result = execution.add_step_result.call_args[0][0]
        assert step_result.name == "test_action"
        assert step_result.status == "success"

    @pytest.mark.asyncio
    async def test_run_handles_permanent_error(self):
        """Test that run() handles permanent errors correctly."""
        workflow = MagicMock()
        execution = MagicMock()
        workflow._execution = execution

        action = FailingAction(workflow, name="fail_action", max_retries=2)

        with pytest.raises(PermanentError):
            await action.run(error_type="permanent")

        # Verify error was tracked
        execution.add_step_result.assert_called()

    @pytest.mark.asyncio
    async def test_run_handles_transient_error(self):
        """Test that run() handles transient errors by exhausting retries and raising PermanentError."""
        workflow = MagicMock()
        execution = MagicMock()
        workflow._execution = execution

        action = FailingAction(workflow, name="fail_action", max_retries=1)

        # After retries are exhausted, transient errors become permanent
        with pytest.raises(PermanentError):
            await action.run(error_type="transient")

        # Verify error was tracked
        execution.add_step_result.assert_called()


class TestActionDependencies:
    """Tests for Action dependencies."""

    def test_get_dependencies(self):
        """Test get_dependencies() method."""
        workflow = MagicMock()
        requires = ["step1", "step2"]
        action = DummyAction(workflow, requires=requires)

        deps = action.get_dependencies()

        assert deps == requires

    def test_get_dependencies_empty(self):
        """Test get_dependencies() with no dependencies."""
        workflow = MagicMock()
        action = DummyAction(workflow)

        deps = action.get_dependencies()

        assert deps == []

    def test_has_dependency_true(self):
        """Test has_dependency() returns True when dependent."""
        workflow = MagicMock()
        action = DummyAction(workflow, requires=["step1", "step2"])

        assert action.has_dependency("step1")
        assert action.has_dependency("step2")

    def test_has_dependency_false(self):
        """Test has_dependency() returns False when not dependent."""
        workflow = MagicMock()
        action = DummyAction(workflow, requires=["step1"])

        assert not action.has_dependency("step2")
        assert not action.has_dependency("step3")


class TestActionRepresentation:
    """Tests for Action string representation."""

    def test_repr(self):
        """Test __repr__() method."""
        workflow = MagicMock()
        action = DummyAction(workflow, name="my_action", requires=["dep1"])

        repr_str = repr(action)

        assert "DummyAction" in repr_str
        assert "my_action" in repr_str
        assert "dep1" in repr_str


class TestAbstractMethods:
    """Tests for abstract methods."""

    def test_cannot_instantiate_abstract_action(self):
        """Test that abstract Action cannot be instantiated."""

        class IncompleteAction(Action):
            pass

        workflow = MagicMock()

        with pytest.raises(TypeError):
            IncompleteAction(workflow)


class TestActionLogging:
    """Tests for Action logging."""

    @pytest.mark.asyncio
    async def test_logging_on_execution(self):
        """Test that execution is logged."""
        workflow = MagicMock()
        action = DummyAction(workflow, name="logged_action")

        with patch("src.framework.action.logger") as mock_logger:
            await action.run()

            # Verify logging was called
            assert mock_logger.debug.called

    @pytest.mark.asyncio
    async def test_logging_on_error(self):
        """Test that errors are logged."""
        workflow = MagicMock()
        action = FailingAction(workflow, name="error_action", max_retries=0)

        with patch("src.framework.action.logger") as mock_logger:
            with pytest.raises(PermanentError):
                await action.run(error_type="permanent")

            # Verify error logging was called
            assert mock_logger.error.called
