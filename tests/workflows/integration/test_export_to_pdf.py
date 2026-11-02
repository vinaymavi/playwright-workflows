"""Integration tests for export_to_pdf() method."""

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
async def test_export_to_pdf_creates_file(temp_workspace, mock_execution):
    """Test that export_to_pdf() creates a PDF file."""
    execution_id = mock_execution.execution_id
    
    mock_page = AsyncMock()
    async def pdf_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PDF_DATA_HEADER")
        return b"PDF_DATA_HEADER"
    
    mock_page.pdf = AsyncMock(side_effect=pdf_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    result = await workflow.export_to_pdf("export.pdf")
    
    expected_file = Path(f"data/artifacts/{execution_id}/export.pdf")
    assert expected_file.exists()
    assert expected_file.stat().st_size > 0
    assert result is not None
    assert result == expected_file


@pytest.mark.asyncio
async def test_export_to_pdf_with_print_media(temp_workspace, mock_execution):
    """Test that export_to_pdf() uses print media type."""
    execution_id = mock_execution.execution_id
    
    mock_page = AsyncMock()
    async def pdf_impl(path=None, **kwargs):
        # Verify print_background was used
        assert kwargs.get("print_background") is True
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PDF_DATA_HEADER")
        return b"PDF_DATA_HEADER"
    
    mock_page.pdf = AsyncMock(side_effect=pdf_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    result = await workflow.export_to_pdf("print.pdf")
    
    assert result is not None
    mock_page.pdf.assert_called_once()


@pytest.mark.asyncio
async def test_export_to_pdf_updates_state(temp_workspace, mock_execution):
    """Test that export_to_pdf() updates execution state."""
    execution_id = mock_execution.execution_id
    
    mock_page = AsyncMock()
    async def pdf_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PDF_DATA_HEADER")
        return b"PDF_DATA_HEADER"
    
    mock_page.pdf = AsyncMock(side_effect=pdf_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    await workflow.export_to_pdf("updated.pdf")
    
    assert len(mock_execution.state.resources) > 0
    resource = mock_execution.state.resources[0]
    assert resource["name"] == "updated.pdf"
    assert resource["resource_type"] == "pdf"


@pytest.mark.asyncio
async def test_export_to_pdf_handles_missing_page(temp_workspace, mock_execution):
    """Test that export_to_pdf() handles missing page."""
    execution_id = mock_execution.execution_id
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = None
    workflow._execution = mock_execution
    
    with pytest.raises(Exception):
        await workflow.export_to_pdf("export.pdf")


@pytest.mark.asyncio
async def test_export_to_pdf_with_custom_name(temp_workspace, mock_execution):
    """Test export_to_pdf() with custom file name."""
    execution_id = mock_execution.execution_id
    
    custom_name = "my_custom_export.pdf"
    
    mock_page = AsyncMock()
    async def pdf_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PDF_DATA_HEADER")
        return b"PDF_DATA_HEADER"
    
    mock_page.pdf = AsyncMock(side_effect=pdf_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    result = await workflow.export_to_pdf(custom_name)
    
    assert result is not None
    assert result.name == custom_name
    assert result.exists()


@pytest.mark.asyncio
async def test_export_to_pdf_resource_tracked(temp_workspace, mock_execution):
    """Test that exported PDF is tracked as a resource."""
    execution_id = mock_execution.execution_id
    
    mock_page = AsyncMock()
    async def pdf_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PDF_DATA_HEADER")
        return b"PDF_DATA_HEADER"
    
    mock_page.pdf = AsyncMock(side_effect=pdf_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    await workflow.export_to_pdf("tracked.pdf")
    
    resources = mock_execution.state.resources
    assert len(resources) > 0
    assert any(r["name"] == "tracked.pdf" for r in resources)


@pytest.mark.asyncio
async def test_export_to_pdf_returns_path(temp_workspace, mock_execution):
    """Test that export_to_pdf() returns the file path."""
    execution_id = mock_execution.execution_id
    
    mock_page = AsyncMock()
    async def pdf_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PDF_DATA_HEADER")
        return b"PDF_DATA_HEADER"
    
    mock_page.pdf = AsyncMock(side_effect=pdf_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    result = await workflow.export_to_pdf("returned.pdf")
    
    assert result is not None
    assert isinstance(result, Path)


@pytest.mark.asyncio
async def test_export_to_pdf_large_file(temp_workspace, mock_execution):
    """Test export_to_pdf() with larger file size."""
    execution_id = mock_execution.execution_id
    
    mock_page = AsyncMock()
    async def pdf_impl(path=None, **kwargs):
        file_path = Path(path) if path else None
        if file_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Write larger fake PDF data
            file_path.write_bytes(b"PDF_DATA_HEADER" * 10000)
        return b"PDF_DATA_HEADER" * 10000
    
    mock_page.pdf = AsyncMock(side_effect=pdf_impl)
    
    workflow = MockWorkflow(
        execution_id=execution_id,
        base_url="http://localhost:3000"
    )
    workflow._page = mock_page
    workflow._execution = mock_execution
    
    result = await workflow.export_to_pdf("large.pdf")
    
    assert result is not None
    assert result.exists()
    assert result.stat().st_size > 50000
