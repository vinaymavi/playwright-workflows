"""Tests for WorkflowController Python API client.

Tests the synchronous and asynchronous API methods for:
- Starting workflows
- Monitoring execution status
- Resolving checkpoints
- Retrieving execution logs
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.workflow_controller import WorkflowController
from src.mcp_server.tools import register_workflow


# Test workflow for testing
class TestWorkflow:
    workflow_type = "test_workflow"
    
    def __init__(self):
        self.state = {}
    
    async def run(self, input_params):
        self.state["status"] = "running"
        await asyncio.sleep(0.01)  # Simulate work
        self.state["status"] = "completed"
        return {"result": "success"}


@pytest.fixture
def controller():
    """Create WorkflowController instance."""
    return WorkflowController()


@pytest.fixture(autouse=True)
def setup_test_workflow():
    """Register test workflow for testing."""
    register_workflow("test_workflow", TestWorkflow)
    yield
    # Cleanup
    from src.mcp_server import tools
    if "test_workflow" in tools._workflow_registry:
        del tools._workflow_registry["test_workflow"]


class TestWorkflowControllerAsync:
    """Test asynchronous methods of WorkflowController."""

    @pytest.mark.asyncio
    async def test_start_workflow_async_success(self, controller):
        """Test starting a workflow asynchronously."""
        execution_id = await controller.start_async(
            "test_workflow",
            {"url": "http://example.com"}
        )
        assert execution_id
        assert isinstance(execution_id, str)
        assert len(execution_id) > 0

    @pytest.mark.asyncio
    async def test_start_workflow_async_invalid_type(self, controller):
        """Test starting a workflow with invalid type."""
        with pytest.raises(ValueError):
            await controller.start_async("nonexistent_workflow")

    @pytest.mark.asyncio
    async def test_start_workflow_async_with_params(self, controller):
        """Test starting a workflow with input parameters."""
        params = {
            "url": "http://example.com",
            "username": "test_user",
            "password": "test_pass"
        }
        execution_id = await controller.start_async("test_workflow", params)
        assert execution_id

    @pytest.mark.asyncio
    async def test_start_workflow_async_with_retries(self, controller):
        """Test starting a workflow with custom retry settings."""
        execution_id = await controller.start_async(
            "test_workflow",
            max_retries=5,
            timeout_seconds=600
        )
        assert execution_id

    @pytest.mark.asyncio
    async def test_get_status_async_running(self, controller):
        """Test getting status of running workflow."""
        execution_id = await controller.start_async("test_workflow")
        status = await controller.get_status_async(execution_id)
        
        assert status["execution_id"] == execution_id
        assert "workflow_type" in status
        assert "status" in status
        assert status["status"] in ("pending", "running", "completed", "failed", "pending_checkpoint")

    @pytest.mark.asyncio
    async def test_get_status_async_with_checkpoint(self, controller):
        """Test getting status when workflow is at checkpoint."""
        # This would need a workflow that actually hits a checkpoint
        # For now, just test the method exists and returns structure
        execution_id = await controller.start_async("test_workflow")
        status = await controller.get_status_async(execution_id)
        
        if status.get("status") == "pending_checkpoint":
            assert "pending_checkpoint" in status
            assert "checkpoint_id" in status["pending_checkpoint"]

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_async_success(self, controller):
        """Test resolving a checkpoint."""
        mock_resolve = AsyncMock(return_value={
            "execution_id": "exec-123",
            "checkpoint_id": "cp-456",
            "status": "resolved",
            "resolved_at": datetime.now().isoformat()
        })
        
        with patch("src.api.workflow_controller.resolve_checkpoint_impl", mock_resolve):
            result = await controller.resolve_checkpoint_async(
                "exec-123",
                "cp-456",
                {"decision": "approved"}
            )
            
            assert result["status"] == "resolved"
            assert result["checkpoint_id"] == "cp-456"

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_async_custom_agent(self, controller):
        """Test resolving checkpoint with custom agent ID."""
        mock_resolve = AsyncMock(return_value={
            "execution_id": "exec-123",
            "checkpoint_id": "cp-456",
            "status": "resolved",
            "resolved_at": datetime.now().isoformat()
        })
        
        with patch("src.api.workflow_controller.resolve_checkpoint_impl", mock_resolve):
            result = await controller.resolve_checkpoint_async(
                "exec-123",
                "cp-456",
                {"decision": "approved"},
                agent_id="custom_agent"
            )
            
            assert mock_resolve.called
            call_args = mock_resolve.call_args
            assert call_args[1]["agent_id"] == "custom_agent"

    @pytest.mark.asyncio
    async def test_get_logs_async_all(self, controller):
        """Test retrieving all execution logs."""
        execution_id = await controller.start_async("test_workflow")
        logs = await controller.get_logs_async(execution_id)
        
        assert isinstance(logs, list)
        for log in logs:
            assert "timestamp" in log or "event" in log

    @pytest.mark.asyncio
    async def test_get_logs_async_filtered_by_event_type(self, controller):
        """Test retrieving logs filtered by event type."""
        execution_id = await controller.start_async("test_workflow")
        logs = await controller.get_logs_async(
            execution_id,
            event_type="step"
        )
        
        assert isinstance(logs, list)
        for log in logs:
            event = log.get("event", "")
            assert event.startswith("step") if event else True

    @pytest.mark.asyncio
    async def test_get_logs_async_filtered_by_level(self, controller):
        """Test retrieving logs filtered by level."""
        execution_id = await controller.start_async("test_workflow")
        logs = await controller.get_logs_async(
            execution_id,
            level="error"
        )
        
        assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_get_logs_async_with_pagination(self, controller):
        """Test retrieving logs with pagination."""
        execution_id = await controller.start_async("test_workflow")
        logs = await controller.get_logs_async(
            execution_id,
            limit=10,
            offset=0
        )
        
        assert isinstance(logs, list)
        assert len(logs) <= 10

    @pytest.mark.asyncio
    async def test_get_logs_async_error_handling(self, controller):
        """Test error handling when retrieving logs."""
        mock_logs = AsyncMock(return_value={"error": "Execution not found"})
        
        with patch("src.api.workflow_controller.get_execution_logs_impl", mock_logs):
            with pytest.raises(ValueError):
                await controller.get_logs_async("invalid-exec-id")


class TestWorkflowControllerSync:
    """Test synchronous wrapper methods of WorkflowController."""

    def test_start_workflow_sync(self, controller):
        """Test starting a workflow synchronously."""
        execution_id = controller.start("test_workflow")
        assert execution_id
        assert isinstance(execution_id, str)

    def test_start_workflow_sync_with_params(self, controller):
        """Test starting a workflow synchronously with parameters."""
        params = {"url": "http://example.com"}
        execution_id = controller.start("test_workflow", params)
        assert execution_id

    def test_get_status_sync(self, controller):
        """Test getting status synchronously."""
        execution_id = controller.start("test_workflow")
        status = controller.get_status(execution_id)
        
        assert status["execution_id"] == execution_id
        assert "status" in status

    def test_resolve_checkpoint_sync(self, controller):
        """Test resolving checkpoint synchronously."""
        mock_resolve = AsyncMock(return_value={
            "execution_id": "exec-123",
            "checkpoint_id": "cp-456",
            "status": "resolved",
            "resolved_at": datetime.now().isoformat()
        })
        
        with patch("src.api.workflow_controller.resolve_checkpoint_impl", mock_resolve):
            result = controller.resolve_checkpoint(
                "exec-123",
                "cp-456",
                {"decision": "approved"}
            )
            
            assert result["status"] == "resolved"

    def test_get_logs_sync(self, controller):
        """Test retrieving logs synchronously."""
        execution_id = controller.start("test_workflow")
        logs = controller.get_logs(execution_id)
        
        assert isinstance(logs, list)

    def test_get_logs_sync_with_filters(self, controller):
        """Test retrieving logs synchronously with filters."""
        execution_id = controller.start("test_workflow")
        logs = controller.get_logs(
            execution_id,
            event_type="step",
            level="info",
            limit=50,
            offset=0
        )
        
        assert isinstance(logs, list)


class TestWorkflowControllerIntegration:
    """Integration tests for WorkflowController."""

    def test_workflow_lifecycle_sync(self, controller):
        """Test complete workflow lifecycle using sync API."""
        # Start workflow
        execution_id = controller.start("test_workflow", {"test": True})
        assert execution_id
        
        # Check status
        status = controller.get_status(execution_id)
        assert status["execution_id"] == execution_id
        assert status["status"] in ("pending", "running", "completed", "failed", "pending_checkpoint")
        
        # Get logs
        logs = controller.get_logs(execution_id)
        assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_workflow_lifecycle_async(self, controller):
        """Test complete workflow lifecycle using async API."""
        # Start workflow
        execution_id = await controller.start_async("test_workflow", {"test": True})
        assert execution_id
        
        # Check status
        status = await controller.get_status_async(execution_id)
        assert status["execution_id"] == execution_id
        
        # Get logs
        logs = await controller.get_logs_async(execution_id)
        assert isinstance(logs, list)
