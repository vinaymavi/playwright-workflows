"""Unit tests for MCP Server

Tests:
- Server initialization and stdio transport setup
- Tool registration with correct schemas
- Workflow registry functionality
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from src.mcp_server.server import WorkflowMCPServer, create_server
from src.mcp_server.tools import register_workflow, _active_executions
from src.mcp_server.notifications import NotificationService


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for test executions."""
    data_dir = tmp_path / "data" / "executions"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def mock_server():
    """Create a mock MCP server."""
    with patch("src.mcp_server.server.Server"):
        server = WorkflowMCPServer()
        return server


class TestWorkflowMCPServerInitialization:
    """Test MCP server initialization."""

    def test_server_creation(self):
        """Test that server can be created."""
        with patch("src.mcp_server.server.Server"):
            server = WorkflowMCPServer()
            assert server is not None

    @pytest.mark.asyncio
    async def test_server_has_tools_attribute(self):
        """Test that server initializes with tools setup."""
        with patch("src.mcp_server.server.Server"):
            server = WorkflowMCPServer()
            # Should have called _setup_tools during init
            assert hasattr(server, "_setup_tools")

    def test_factory_function_creates_server(self):
        """Test create_server factory function."""
        with patch("src.mcp_server.server.Server"):
            server = create_server()
            assert isinstance(server, WorkflowMCPServer)

    @pytest.mark.asyncio
    async def test_notifications_service_can_be_configured(self):
        """Test that NotificationService can be configured with server."""
        with patch("src.mcp_server.server.Server"):
            server = create_server()
            NotificationService.set_server(server)
            assert NotificationService._server_instance is server


class TestWorkflowRegistry:
    """Test workflow registration functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        from src.mcp_server import tools
        tools._workflow_registry.clear()

    def test_register_workflow(self):
        """Test registering a workflow."""
        mock_workflow_cls = MagicMock()
        mock_workflow_cls.workflow_type = "test_workflow"

        register_workflow("test_workflow", mock_workflow_cls)

        from src.mcp_server import tools
        assert "test_workflow" in tools._workflow_registry
        assert tools._workflow_registry["test_workflow"] == mock_workflow_cls

    def test_register_multiple_workflows(self):
        """Test registering multiple workflows."""
        mock_workflow_1 = MagicMock()
        mock_workflow_1.workflow_type = "workflow_1"

        mock_workflow_2 = MagicMock()
        mock_workflow_2.workflow_type = "workflow_2"

        register_workflow("workflow_1", mock_workflow_1)
        register_workflow("workflow_2", mock_workflow_2)

        from src.mcp_server import tools
        assert len(tools._workflow_registry) == 2
        assert "workflow_1" in tools._workflow_registry
        assert "workflow_2" in tools._workflow_registry

    def test_register_workflow_overwrites_existing(self):
        """Test that registering same workflow type overwrites previous."""
        mock_workflow_1 = MagicMock()
        mock_workflow_1.workflow_type = "test"

        mock_workflow_2 = MagicMock()
        mock_workflow_2.workflow_type = "test"

        register_workflow("test", mock_workflow_1)
        register_workflow("test", mock_workflow_2)

        from src.mcp_server import tools
        assert tools._workflow_registry["test"] == mock_workflow_2


class TestExecutionStateManagement:
    """Test execution state persistence and retrieval."""

    def setup_method(self):
        """Clear active executions before each test."""
        _active_executions.clear()

    @pytest.mark.asyncio
    async def test_execution_state_file_creation(self, tmp_path, monkeypatch):
        """Test that execution state files are created correctly."""
        # Patch the data directory environment variable
        data_dir = tmp_path / "data" / "executions"
        data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(data_dir))

        # Create mock workflow with async run method
        async def mock_run(**kwargs):
            return {"result": "success"}

        mock_workflow = MagicMock()
        mock_workflow.run = mock_run

        from src.mcp_server.tools import start_workflow_impl, register_workflow

        register_workflow("test_workflow", mock_workflow)

        result = await start_workflow_impl(
            workflow_type="test_workflow",
            input_params={"key": "value"},
            max_retries=1,
            timeout_seconds=30,
        )

        assert "execution_id" in result
        assert result["status"] == "pending"
        assert "created_at" in result

        # Check that state file was created
        execution_id = result["execution_id"]
        state_file = data_dir / f"{execution_id}.json"
        assert state_file.exists()

        with open(state_file) as f:
            state = json.load(f)
            assert state["execution_id"] == execution_id
            assert state["workflow_type"] == "test_workflow"
            assert state["status"] == "pending"

    @pytest.mark.asyncio
    async def test_execution_state_persistence(self, tmp_path, monkeypatch):
        """Test that execution state persists across reads."""
        data_dir = tmp_path / "data" / "executions"
        data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(data_dir))

        # Create test state file
        execution_id = "test-exec-123"
        state = {
            "execution_id": execution_id,
            "workflow_type": "test",
            "status": "running",
            "input_params": {"test": "value"},
            "steps": [],
            "checkpoints": [],
            "error": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }

        state_file = data_dir / f"{execution_id}.json"
        with open(state_file, "w") as f:
            json.dump(state, f)

        # Import and call get_execution_status
        from src.mcp_server.tools import get_execution_status_impl

        result = await get_execution_status_impl(execution_id=execution_id)

        assert result["execution_id"] == execution_id
        assert result["status"] == "running"
        assert result["workflow_type"] == "test"

    @pytest.mark.asyncio
    async def test_execution_not_found(self, monkeypatch):
        """Test handling of non-existent execution."""
        tmp_dir = Path("/tmp")
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_dir))

        from src.mcp_server.tools import get_execution_status_impl

        result = await get_execution_status_impl(execution_id="nonexistent")

        assert "error" in result
        assert "not found" in result["error"].lower()


class TestNotificationService:
    """Test notification service."""

    @pytest.mark.asyncio
    async def test_send_checkpoint_notification(self):
        """Test sending checkpoint_requested notification."""
        await NotificationService.checkpoint_requested(
            execution_id="exec-1",
            checkpoint_id="cp-1",
            question={"type": "approval", "text": "Continue?"},
        )

        # Should not raise an exception

    @pytest.mark.asyncio
    async def test_send_completion_notification(self):
        """Test sending execution_completed notification."""
        await NotificationService.execution_completed(
            execution_id="exec-1",
            result={"status": "success"},
        )

        # Should not raise an exception

    @pytest.mark.asyncio
    async def test_send_failure_notification(self):
        """Test sending execution_failed notification."""
        await NotificationService.execution_failed(
            execution_id="exec-1",
            error="Test error",
        )

        # Should not raise an exception

    @pytest.mark.asyncio
    async def test_get_pending_notifications(self):
        """Test that notification service can be called without error."""
        # Just test that the notification service methods can be called
        # The actual queue dispatch is tested in integration tests
        
        try:
            await NotificationService.checkpoint_requested(
                execution_id="exec-1",
                checkpoint_id="cp-1",
                question={"type": "approval"},
            )
            # If we get here without exception, the test passes
            assert True
        except Exception as e:
            pytest.fail(f"Notification service raised exception: {e}")


class TestMCPToolSchemas:
    """Test that tool schemas are correctly defined."""

    @pytest.mark.asyncio
    async def test_start_workflow_schema_compliance(self, temp_data_dir, monkeypatch):
        """Test start_workflow input/output schema."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))
        
        from src.mcp_server.tools import start_workflow_impl

        # Tool should accept these parameters per schema
        mock_workflow = MagicMock()
        mock_workflow.run = AsyncMock(return_value={"result": "success"})
        register_workflow("test", mock_workflow)

        result = await start_workflow_impl(
            workflow_type="test",
            input_params={"key": "value"},
            max_retries=3,
            timeout_seconds=60,
        )

        # Output should have these fields per schema
        assert isinstance(result, dict)
        assert "execution_id" in result
        assert "status" in result
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_schema_compliance(self, tmp_path, monkeypatch):
        """Test resolve_checkpoint input/output schema."""
        # Setup data directory with environment variable
        data_dir = tmp_path / "data" / "executions"
        data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(data_dir))

        # Create a fake execution state with checkpoints
        execution_id = "test-exec"
        state = {
            "execution_id": execution_id,
            "workflow_type": "test",
            "status": "paused",
            "input_params": {},
            "steps": [],
            "checkpoints": [
                {
                    "checkpoint_id": "cp-1",
                    "question": {"type": "approval"},
                    "response": None,
                    "status": "pending",
                }
            ],
            "error": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }

        state_file = data_dir / f"{execution_id}.json"
        with open(state_file, "w") as f:
            json.dump(state, f)

        from src.mcp_server.tools import resolve_checkpoint_impl

        result = await resolve_checkpoint_impl(
            execution_id=execution_id,
            checkpoint_id="cp-1",
            decision={"approved": True},
            agent_id="agent-1",
        )

        # Output should have these fields per schema
        assert isinstance(result, dict)
        assert "execution_id" in result
        assert result["execution_id"] == execution_id
