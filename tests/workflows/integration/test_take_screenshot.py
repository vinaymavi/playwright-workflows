"""Integration tests for take_screenshot() method."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.framework.execution import Execution, ExecutionState, ExecutionStateData
from src.framework.workflow import Workflow


# Concrete implementation for testing
class MockWorkflow(Workflow):
    """Concrete workflow for testing."""

    async def run(self):
        """Dummy run implementation."""
        pass


@pytest.fixture
def temp_workspace(monkeypatch):
    """Create temporary workspace directory and change to it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.chdir(tmpdir)
        yield Path(tmpdir)


@pytest.fixture
def mock_execution(temp_workspace):
    """Create mock execution with state."""
    execution_id = str(uuid4())
    
    state = ExecutionStateData(
        execution_id=execution_id,
        state=ExecutionState.RUNNING,
        base_url="http://localhost:3000",
        resources=[],
    )
    
    execution = Execution(
        execution_id=execution_id, 
        base_url="http://localhost:3000",
        data_dir=temp_workspace / "executions"
    )
    execution.state = state
    
    # Mock save as async method
    async def mock_save():
        pass
    execution.save = mock_save
    
    return execution


@pytest.mark.asyncio
async def test_take_screenshot_creates_png_file(temp_workspace, mock_execution):
    """Test that take_screenshot() creates a PNG file."""
    execution_id = mock_execution.execution_id
    
    # Create mock page that writes actual file
    mock_page = AsyncMock()
    
    async def screenshot_impl(path=None, **kwargs):
        # Create file path and parent directories
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PNG_DATA_HEADER")
        return b"PNG_DATA_HEADER"
    
    mock_page.screenshot = AsyncMock(side_effect=screenshot_impl)
    
    # Create workflow
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    # Take screenshot
    result = await workflow.take_screenshot("test_screenshot.png")
    
    # Verify file was created
    expected_file = Path(f"data/artifacts/{execution_id}/test_screenshot.png")
    assert expected_file.exists()
    assert expected_file.stat().st_size > 0
    assert result is not None
    assert result == expected_file


@pytest.mark.asyncio
async def test_take_screenshot_updates_execution_state(temp_workspace, mock_execution):
    """Test that take_screenshot() updates execution state."""
    execution_id = mock_execution.execution_id
    
    mock_page = AsyncMock()
    async def screenshot_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PNG_DATA_HEADER")
        return b"PNG_DATA_HEADER"
    
    mock_page.screenshot = AsyncMock(side_effect=screenshot_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    # Take screenshot
    await workflow.take_screenshot("screenshot.png")
    
    # Verify state was updated
    assert len(mock_execution.state.resources) > 0
    resource = mock_execution.state.resources[0]
    assert resource["name"] == "screenshot.png"
    assert resource["resource_type"] == "screenshot"


@pytest.mark.asyncio
async def test_take_screenshot_handles_missing_page(temp_workspace, mock_execution):
    """Test that take_screenshot() handles missing page."""
    execution_id = mock_execution.execution_id
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = None
    workflow._execution = mock_execution
    
    # Should raise error when page is missing
    with pytest.raises(Exception):
        await workflow.take_screenshot("screenshot.png")


@pytest.mark.asyncio
async def test_take_screenshot_with_custom_name(temp_workspace, mock_execution):
    """Test take_screenshot() with custom file name."""
    execution_id = mock_execution.execution_id
    
    custom_name = "my_custom_screenshot.png"
    
    mock_page = AsyncMock()
    async def screenshot_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PNG_DATA_HEADER")
        return b"PNG_DATA_HEADER"
    
    mock_page.screenshot = AsyncMock(side_effect=screenshot_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    result = await workflow.take_screenshot(custom_name)
    
    assert result is not None
    assert result.name == custom_name
    assert result.exists()


@pytest.mark.asyncio
async def test_take_screenshot_resource_tracked(temp_workspace, mock_execution):
    """Test that taken screenshot is tracked as a resource."""
    execution_id = mock_execution.execution_id
    
    mock_page = AsyncMock()
    async def screenshot_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PNG_DATA_HEADER")
        return b"PNG_DATA_HEADER"
    
    mock_page.screenshot = AsyncMock(side_effect=screenshot_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    await workflow.take_screenshot("tracked.png")
    
    # Verify resource was tracked
    resources = mock_execution.state.resources
    assert len(resources) > 0
    assert any(r["name"] == "tracked.png" for r in resources)


@pytest.mark.asyncio
async def test_take_screenshot_returns_path(temp_workspace, mock_execution):
    """Test that take_screenshot() returns the file path."""
    execution_id = mock_execution.execution_id
    
    mock_page = AsyncMock()
    async def screenshot_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PNG_DATA_HEADER")
        return b"PNG_DATA_HEADER"
    
    mock_page.screenshot = AsyncMock(side_effect=screenshot_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    result = await workflow.take_screenshot("returned.png")
    
    assert result is not None
    assert isinstance(result, Path)
