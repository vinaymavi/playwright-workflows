"""
Tests for MCP checkpoint notifications and execution listing.

Tests Phase A.1 - Checkpoint Notifications
Tests Phase A.2 - Execution Context in Checkpoint
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.framework.checkpoint import CheckpointRequest, CheckpointQuestion
from src.mcp_server.notifications import NotificationService
from src.mcp_server.tools import list_executions_impl, resolve_checkpoint_impl


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for executions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_notifications():
    """Mock NotificationService."""
    with patch("src.framework.workflow.NotificationService") as mock:
        yield mock


class TestCheckpointNotifications:
    """Tests for checkpoint notification delivery."""

    @pytest.mark.asyncio
    async def test_notification_service_checkpoint_requested(self):
        """Test that NotificationService.checkpoint_requested can be called."""
        # Just verify the method exists and doesn't error
        from src.mcp_server.notifications import NotificationService
        
        # This should not raise an error
        await NotificationService.checkpoint_requested(
            execution_id="test-123",
            checkpoint_id="cp-123",
            question={"type": "test", "text": "Test question"}
        )

    @pytest.mark.asyncio
    async def test_notification_service_execution_completed(self):
        """Test execution_completed notification."""
        from src.mcp_server.notifications import NotificationService
        
        await NotificationService.execution_completed(
            execution_id="exec-123",
            result={"success": True}
        )

    @pytest.mark.asyncio
    async def test_notification_service_execution_failed(self):
        """Test execution_failed notification."""
        from src.mcp_server.notifications import NotificationService
        
        await NotificationService.execution_failed(
            execution_id="exec-123",
            error="Test error"
        )


class TestListExecutions:
    """Tests for list_executions MCP tool."""

    @pytest.mark.asyncio
    async def test_list_executions_all(self, temp_data_dir, monkeypatch):
        """Test listing all executions without filter."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create test executions
        exec1 = {
            "execution_id": "exec-1",
            "workflow_type": "login",
            "status": "completed",
            "created_at": "2026-11-01T10:00:00Z",
            "started_at": "2026-11-01T10:00:01Z",
            "current_step": None,
            "checkpoints": []
        }
        exec2 = {
            "execution_id": "exec-2",
            "workflow_type": "form_fill",
            "status": "running",
            "created_at": "2026-11-01T10:05:00Z",
            "started_at": "2026-11-01T10:05:01Z",
            "current_step": "fill_form",
            "checkpoints": []
        }

        (temp_data_dir / "exec-1.json").write_text(json.dumps(exec1))
        (temp_data_dir / "exec-2.json").write_text(json.dumps(exec2))

        # List all
        result = await list_executions_impl(status=None, limit=50, offset=0)

        assert result["total"] == 2
        assert result["returned"] == 2
        assert len(result["executions"]) == 2
        assert result["executions"][0]["execution_id"] in ["exec-1", "exec-2"]

    @pytest.mark.asyncio
    async def test_list_executions_with_status_filter(self, temp_data_dir, monkeypatch):
        """Test filtering executions by status."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create test executions with different statuses
        exec1 = {
            "execution_id": "exec-1",
            "workflow_type": "login",
            "status": "completed",
            "created_at": "2026-11-01T10:00:00Z",
            "started_at": None,
            "current_step": None,
            "checkpoints": []
        }
        exec2 = {
            "execution_id": "exec-2",
            "workflow_type": "form_fill",
            "status": "running",
            "created_at": "2026-11-01T10:05:00Z",
            "started_at": "2026-11-01T10:05:01Z",
            "current_step": None,
            "checkpoints": []
        }
        exec3 = {
            "execution_id": "exec-3",
            "workflow_type": "screenshot",
            "status": "running",
            "created_at": "2026-11-01T10:10:00Z",
            "started_at": "2026-11-01T10:10:01Z",
            "current_step": None,
            "checkpoints": []
        }

        (temp_data_dir / "exec-1.json").write_text(json.dumps(exec1))
        (temp_data_dir / "exec-2.json").write_text(json.dumps(exec2))
        (temp_data_dir / "exec-3.json").write_text(json.dumps(exec3))

        # Filter for running only
        result = await list_executions_impl(status="running", limit=50, offset=0)

        assert result["total"] == 3
        assert result["returned"] == 2
        assert len(result["executions"]) == 2
        for exec_data in result["executions"]:
            assert exec_data["status"] == "running"

    @pytest.mark.asyncio
    async def test_list_executions_with_pending_checkpoint(self, temp_data_dir, monkeypatch):
        """Test that executions with pending checkpoints are included in listing."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create execution with pending checkpoint
        exec_data = {
            "execution_id": "exec-pause",
            "workflow_type": "login",
            "status": "paused",
            "created_at": "2026-11-01T10:00:00Z",
            "started_at": "2026-11-01T10:00:01Z",
            "current_step": "fill_username",
            "checkpoints": [
                {
                    "checkpoint_id": "cp-1",
                    "question": {
                        "type": "confirm",
                        "message": "Proceed?"
                    },
                    "response": None  # No response yet
                }
            ]
        }

        (temp_data_dir / "exec-pause.json").write_text(json.dumps(exec_data))

        # List all
        result = await list_executions_impl(status=None, limit=50, offset=0)

        assert result["returned"] == 1
        exec_info = result["executions"][0]
        assert exec_info["execution_id"] == "exec-pause"
        assert exec_info["pending_checkpoint"] is not None
        assert exec_info["pending_checkpoint"]["checkpoint_id"] == "cp-1"
        assert exec_info["pending_checkpoint"]["question"]["message"] == "Proceed?"

    @pytest.mark.asyncio
    async def test_list_executions_pagination(self, temp_data_dir, monkeypatch):
        """Test pagination of execution listing."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create 5 test executions
        for i in range(5):
            exec_data = {
                "execution_id": f"exec-{i}",
                "workflow_type": "test",
                "status": "completed",
                "created_at": f"2026-11-01T{10+i:02d}:00:00Z",
                "started_at": None,
                "current_step": None,
                "checkpoints": []
            }
            (temp_data_dir / f"exec-{i}.json").write_text(json.dumps(exec_data))

        # List first page (limit 2, offset 0)
        result = await list_executions_impl(status=None, limit=2, offset=0)
        assert result["total"] == 5
        assert result["returned"] == 2
        assert result["offset"] == 0

        # List second page (limit 2, offset 2)
        result = await list_executions_impl(status=None, limit=2, offset=2)
        assert result["total"] == 5
        assert result["returned"] == 2
        assert result["offset"] == 2

        # List beyond end
        result = await list_executions_impl(status=None, limit=2, offset=4)
        assert result["total"] == 5
        assert result["returned"] == 1
        assert result["offset"] == 4

    @pytest.mark.asyncio
    async def test_list_executions_handles_corrupt_files(self, temp_data_dir, monkeypatch):
        """Test that corrupt execution files don't crash list_executions."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create valid execution
        valid_exec = {
            "execution_id": "exec-1",
            "workflow_type": "test",
            "status": "completed",
            "created_at": "2026-11-01T10:00:00Z",
            "started_at": None,
            "current_step": None,
            "checkpoints": []
        }
        (temp_data_dir / "exec-1.json").write_text(json.dumps(valid_exec))

        # Create corrupt execution file
        (temp_data_dir / "exec-corrupt.json").write_text("{invalid json")

        # List should skip corrupt file and return valid one
        result = await list_executions_impl(status=None, limit=50, offset=0)

        assert result["returned"] == 1
        assert result["executions"][0]["execution_id"] == "exec-1"


class TestResolveCheckpointWithNotification:
    """Tests for resolve_checkpoint triggering workflow resumption."""

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_validates_execution(self, temp_data_dir, monkeypatch):
        """Test that resolve_checkpoint validates execution exists."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Try to resolve checkpoint for non-existent execution
        result = await resolve_checkpoint_impl(
            execution_id="non-existent",
            checkpoint_id="cp-123",
            decision={"confirmed": True}
        )

        assert "error" in result
        assert "Execution not found" in result["error"]

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_validates_checkpoint(self, temp_data_dir, monkeypatch):
        """Test that resolve_checkpoint validates checkpoint exists."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        execution_id = "test-exec"

        # Create execution state file
        exec_state = {
            "execution_id": execution_id,
            "workflow_type": "test",
            "status": "paused",
            "created_at": "2026-11-01T10:00:00Z",
            "started_at": "2026-11-01T10:00:01Z",
            "checkpoints": []
        }
        (temp_data_dir / f"{execution_id}.json").write_text(json.dumps(exec_state))

        # Try to resolve non-existent checkpoint
        result = await resolve_checkpoint_impl(
            execution_id=execution_id,
            checkpoint_id="non-existent",
            decision={"confirmed": True}
        )

        assert "error" in result
        assert "Checkpoint not found" in result["error"]
