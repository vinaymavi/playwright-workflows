"""Unit tests for Workflow base class."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json

from src.framework.workflow import Workflow
from src.framework.errors import WorkflowError
from src.framework.checkpoint import CheckpointQuestion, CheckpointRequest


class SimpleWorkflow(Workflow):
    """Test workflow implementation."""

    workflow_type = "test_workflow"
    version = "1.0.0"
    description = "Test workflow"

    async def run(self, test_param: str = "default") -> dict:
        """Simple test run method."""
        await self.navigate("https://example.com")
        state_val = self.get_state("test_key")
        self.set_state("test_key", f"{test_param}_processed")
        return {"status": "completed", "param": test_param}


@pytest.fixture
def temp_state_dir():
    """Create temporary state directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def workflow(temp_state_dir):
    """Create workflow instance."""
    return SimpleWorkflow(
        execution_id="test-exec-123",
        base_url="https://example.com",
        max_retries=3,
        timeout_seconds=60,
        state_file=f"{temp_state_dir}/state.json"
    )


class TestWorkflowInitialization:
    """Test Workflow initialization."""

    def test_workflow_init_with_defaults(self, workflow):
        """Test workflow initialization with defaults."""
        assert workflow.execution_id == "test-exec-123"
        assert workflow.base_url == "https://example.com"
        assert workflow.max_retries == 3
        assert workflow.timeout_seconds == 60
        assert workflow.workflow_type == "test_workflow"
        assert workflow.version == "1.0.0"

    def test_workflow_init_sets_logger(self, workflow):
        """Test workflow initializes logger."""
        assert workflow.logger is not None

    def test_workflow_has_page_property(self, workflow):
        """Test workflow has _page property."""
        assert hasattr(workflow, "_page")
        assert workflow._page is None


class TestWorkflowStateManagement:
    """Test Workflow state management."""

    def test_get_state_returns_none_for_missing_key(self, workflow):
        """Test get_state returns None for missing key."""
        assert workflow.get_state("missing_key") is None

    def test_set_and_get_state(self, workflow):
        """Test set_state and get_state."""
        workflow.set_state("test_key", "test_value")
        assert workflow.get_state("test_key") == "test_value"

    def test_get_all_state(self, workflow):
        """Test get_all_state returns all state."""
        workflow.set_state("key1", "value1")
        workflow.set_state("key2", "value2")
        state = workflow.get_all_state()
        assert state["key1"] == "value1"
        assert state["key2"] == "value2"

    def test_set_state_overwrites_previous(self, workflow):
        """Test set_state overwrites previous value."""
        workflow.set_state("key", "value1")
        workflow.set_state("key", "value2")
        assert workflow.get_state("key") == "value2"


class TestWorkflowPlaywrightAPI:
    """Test Workflow Playwright API wrappers."""

    @pytest.mark.asyncio
    async def test_navigate_requires_page(self, workflow):
        """Test navigate raises error without page."""
        with pytest.raises(WorkflowError):
            await workflow.navigate("https://example.com")

    @pytest.mark.asyncio
    async def test_navigate_calls_page_goto(self, workflow):
        """Test navigate calls page.goto."""
        mock_page = AsyncMock()
        workflow.set_page(mock_page)
        
        await workflow.navigate("https://example.com", timeout_ms=5000)
        
        # The actual implementation passes wait_until='load'
        mock_page.goto.assert_called_once_with("https://example.com", timeout=5000, wait_until='load')

    @pytest.mark.asyncio
    async def test_click_requires_page(self, workflow):
        """Test click raises error without page."""
        with pytest.raises(WorkflowError):
            await workflow.click("button")

    @pytest.mark.asyncio
    async def test_click_calls_page_click(self, workflow):
        """Test click calls page.click."""
        mock_page = AsyncMock()
        workflow.set_page(mock_page)
        
        await workflow.click("button[type='submit']")
        
        mock_page.click.assert_called_once_with("button[type='submit']", timeout=10000)

    @pytest.mark.asyncio
    async def test_fill_requires_page(self, workflow):
        """Test fill raises error without page."""
        with pytest.raises(WorkflowError):
            await workflow.fill("#username", "user123")

    @pytest.mark.asyncio
    async def test_fill_calls_page_fill(self, workflow):
        """Test fill calls page.fill."""
        mock_page = AsyncMock()
        workflow.set_page(mock_page)
        
        await workflow.fill("#username", "user123")
        
        mock_page.fill.assert_called_once_with("#username", "user123", timeout=10000)

    @pytest.mark.asyncio
    async def test_wait_for_selector_calls_page_wait_for_selector(self, workflow):
        """Test wait_for_selector calls page.wait_for_selector."""
        mock_page = AsyncMock()
        workflow.set_page(mock_page)
        
        await workflow.wait_for_selector(".dashboard", timeout_ms=10000)
        
        mock_page.wait_for_selector.assert_called_once_with(".dashboard", timeout=10000)

    @pytest.mark.asyncio
    async def test_get_text_calls_page_inner_text(self, workflow):
        """Test get_text calls page.text_content."""
        mock_page = AsyncMock()
        mock_page.text_content = AsyncMock(return_value="Hello World")
        workflow.set_page(mock_page)
        
        result = await workflow.get_text(".message")
        
        assert result == "Hello World"
        mock_page.text_content.assert_called_once_with(".message", timeout=10000)

    @pytest.mark.asyncio
    async def test_get_attribute_calls_page_get_attribute(self, workflow):
        """Test get_attribute calls page.get_attribute."""
        mock_page = AsyncMock()
        mock_page.get_attribute = AsyncMock(return_value="attr_value")
        workflow.set_page(mock_page)
        
        result = await workflow.get_attribute("input", "placeholder")
        
        assert result == "attr_value"
        mock_page.get_attribute.assert_called_once_with("input", "placeholder", timeout=10000)


class TestWorkflowCheckpoint:
    """Test Workflow checkpoint functionality."""

    @pytest.mark.asyncio
    async def test_checkpoint_creates_request(self, workflow):
        """Test checkpoint creates CheckpointRequest and returns response."""
        question = CheckpointQuestion(
            question_text="Proceed?",
            question_type="yes_no",
            options=["yes", "no"]
        )
        
        # Initialize execution
        mock_execution = AsyncMock()
        workflow.set_execution(mock_execution)
        
        result = await workflow.checkpoint(
            question=question,
            timeout_seconds=60
        )
        
        # Check that result is a CheckpointResponse with expected structure
        assert result is not None
        assert hasattr(result, "checkpoint_id")
        assert hasattr(result, "decision")
        assert hasattr(result, "execution_id")
        assert result.decision.confirmed is True  # Default response


class TestWorkflowLifecycleHooks:
    """Test Workflow lifecycle hooks."""

    def test_on_start_is_callable(self, workflow):
        """Test on_start hook is defined."""
        assert callable(workflow.on_start)

    def test_on_step_start_is_callable(self, workflow):
        """Test on_step_start hook is defined."""
        assert callable(workflow.on_step_start)

    def test_on_step_complete_is_callable(self, workflow):
        """Test on_step_complete hook is defined."""
        assert callable(workflow.on_step_complete)

    def test_on_step_error_is_callable(self, workflow):
        """Test on_step_error hook is defined."""
        assert callable(workflow.on_step_error)

    def test_on_checkpoint_is_callable(self, workflow):
        """Test on_checkpoint hook is defined."""
        assert callable(workflow.on_checkpoint)

    def test_on_complete_is_callable(self, workflow):
        """Test on_complete hook is defined."""
        assert callable(workflow.on_complete)

    def test_on_error_is_callable(self, workflow):
        """Test on_error hook is defined."""
        assert callable(workflow.on_error)


class TestWorkflowMutators:
    """Test Workflow internal mutator methods."""

    def test_set_page(self, workflow):
        """Test set_page method."""
        mock_page = MagicMock()
        workflow.set_page(mock_page)
        assert workflow._page is mock_page

    def test_set_browser_context(self, workflow):
        """Test set_browser_context method."""
        mock_context = MagicMock()
        workflow.set_browser_context(mock_context)
        assert workflow._context is mock_context

    def test_set_browser(self, workflow):
        """Test set_browser method."""
        mock_browser = MagicMock()
        workflow.set_browser(mock_browser)
        assert workflow._browser is mock_browser

    def test_set_execution(self, workflow):
        """Test set_execution method."""
        mock_execution = MagicMock()
        workflow.set_execution(mock_execution)
        assert workflow._execution is mock_execution
