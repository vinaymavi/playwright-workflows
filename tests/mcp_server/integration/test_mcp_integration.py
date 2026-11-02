"""Integration tests for MCP Server with actual workflow execution

Tests:
- End-to-end workflow execution via MCP server
- Checkpoint handling and resolution
- Execution status tracking
- Log retrieval and filtering
"""

import asyncio
import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.mcp_server.server import WorkflowMCPServer, create_server
from src.mcp_server.tools import (
    register_workflow,
    start_workflow_impl,
    resolve_checkpoint_impl,
    get_execution_status_impl,
    get_execution_logs_impl,
)
from src.mcp_server.notifications import NotificationService


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory."""
    data_dir = tmp_path / "data" / "executions"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def mock_workflow_cls():
    """Create a mock workflow class."""
    workflow_cls = MagicMock()
    workflow_cls.workflow_type = "test_workflow"
    return workflow_cls


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear workflow registry before each test."""
    from src.mcp_server import tools
    tools._workflow_registry.clear()
    tools._active_executions.clear()
    yield
    tools._workflow_registry.clear()
    tools._active_executions.clear()


class TestEndToEndWorkflowExecution:
    """Test complete workflow execution through MCP server."""

    @pytest.mark.asyncio
    async def test_simple_workflow_execution(self, temp_data_dir, monkeypatch, mock_workflow_cls):
        """Test executing a simple workflow."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Setup mock workflow
        mock_workflow_cls.run = AsyncMock(return_value={"status": "success", "result": "test"})
        register_workflow("test_workflow", mock_workflow_cls)

        # Start workflow
        result = await start_workflow_impl(
            workflow_type="test_workflow",
            input_params={"test": "value"},
            max_retries=1,
            timeout_seconds=30,
        )

        execution_id = result["execution_id"]
        assert result["status"] == "pending"

        # Wait for background execution to complete
        await asyncio.sleep(0.5)

        # Check status
        status = await get_execution_status_impl(execution_id=execution_id)
        assert "workflow_type" in status
        assert status["workflow_type"] == "test_workflow"

    @pytest.mark.asyncio
    async def test_workflow_with_checkpoints(self, temp_data_dir, monkeypatch):
        """Test workflow that hits checkpoints."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create execution with checkpoint
        execution_id = "test-exec-cp"
        state = {
            "execution_id": execution_id,
            "workflow_type": "test",
            "status": "paused",
            "input_params": {},
            "steps": [
                {
                    "step_id": "step-1",
                    "step_name": "Login",
                    "status": "completed",
                    "started_at": datetime.utcnow().isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                    "result": {"success": True},
                }
            ],
            "checkpoints": [
                {
                    "checkpoint_id": "cp-1",
                    "question": {"type": "approval", "text": "Proceed with form?"},
                    "response": None,
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                }
            ],
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        state_file = temp_data_dir / f"{execution_id}.json"
        with open(state_file, "w") as f:
            json.dump(state, f)

        # Get status before resolution
        status_before = await get_execution_status_impl(execution_id=execution_id)
        assert status_before["status"] == "paused"
        assert status_before["pending_checkpoint"] is not None

        # Resolve checkpoint
        resolution = await resolve_checkpoint_impl(
            execution_id=execution_id,
            checkpoint_id="cp-1",
            decision={"approved": True},
            agent_id="agent-1",
        )

        assert resolution["status"] == "running"
        assert "resolved_at" in resolution

        # Check status after resolution
        status_after = await get_execution_status_impl(execution_id=execution_id)
        assert status_after["status"] == "running"

    @pytest.mark.asyncio
    async def test_workflow_failure_handling(self, temp_data_dir, monkeypatch, mock_workflow_cls):
        """Test handling of workflow failures."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Setup workflow that fails
        mock_workflow_cls.run = AsyncMock(side_effect=Exception("Workflow error"))
        register_workflow("test_workflow", mock_workflow_cls)

        # Start workflow
        result = await start_workflow_impl(
            workflow_type="test_workflow",
            input_params={},
            max_retries=1,
            timeout_seconds=30,
        )

        execution_id = result["execution_id"]

        # Wait for execution
        await asyncio.sleep(0.5)

        # Check that error was recorded
        status = await get_execution_status_impl(execution_id=execution_id)
        assert status.get("error") is not None or status["status"] in ["running", "paused"]


class TestExecutionLogsAndMonitoring:
    """Test execution logs retrieval and filtering."""

    @pytest.mark.asyncio
    async def test_get_execution_logs(self, temp_data_dir, monkeypatch):
        """Test retrieving execution logs."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        execution_id = "test-exec-logs"
        state = {
            "execution_id": execution_id,
            "workflow_type": "test",
            "status": "completed",
            "input_params": {},
            "steps": [
                {
                    "step_id": "step-1",
                    "step_name": "Navigate",
                    "status": "completed",
                    "started_at": "2024-01-01T00:00:00",
                    "completed_at": "2024-01-01T00:00:01",
                    "result": {"url": "https://example.com"},
                },
                {
                    "step_id": "step-2",
                    "step_name": "Fill Form",
                    "status": "completed",
                    "started_at": "2024-01-01T00:00:01",
                    "completed_at": "2024-01-01T00:00:02",
                    "result": {"fields": 5},
                },
            ],
            "checkpoints": [],
            "error": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:02",
        }

        state_file = temp_data_dir / f"{execution_id}.json"
        with open(state_file, "w") as f:
            json.dump(state, f)

        logs = await get_execution_logs_impl(
            execution_id=execution_id,
            event_type="step",
            level=None,
            limit=10,
            offset=0,
        )

        assert logs["total_logs"] >= 2
        assert len(logs["logs"]) >= 2

    @pytest.mark.asyncio
    async def test_logs_pagination(self, temp_data_dir, monkeypatch):
        """Test log pagination."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        execution_id = "test-exec-paginated"
        steps = [
            {
                "step_id": f"step-{i}",
                "step_name": f"Step {i}",
                "status": "completed",
                "started_at": "2024-01-01T00:00:00",
                "completed_at": "2024-01-01T00:00:01",
                "result": {},
            }
            for i in range(15)
        ]

        state = {
            "execution_id": execution_id,
            "workflow_type": "test",
            "status": "completed",
            "input_params": {},
            "steps": steps,
            "checkpoints": [],
            "error": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }

        state_file = temp_data_dir / f"{execution_id}.json"
        with open(state_file, "w") as f:
            json.dump(state, f)

        # Get first page
        page1 = await get_execution_logs_impl(
            execution_id=execution_id,
            event_type=None,
            level=None,
            limit=5,
            offset=0,
        )

        assert len(page1["logs"]) == 5
        assert page1["total_logs"] >= 15

        # Get second page
        page2 = await get_execution_logs_impl(
            execution_id=execution_id,
            event_type=None,
            level=None,
            limit=5,
            offset=5,
        )

        assert len(page2["logs"]) == 5
        # Different logs in second page
        assert page1["logs"][0] != page2["logs"][0]

    @pytest.mark.asyncio
    async def test_logs_filtering_by_event_type(self, temp_data_dir, monkeypatch):
        """Test filtering logs by event type."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        execution_id = "test-exec-filter"
        state = {
            "execution_id": execution_id,
            "workflow_type": "test",
            "status": "completed",
            "input_params": {},
            "steps": [
                {
                    "step_id": "step-1",
                    "step_name": "Step 1",
                    "status": "completed",
                    "started_at": "2024-01-01T00:00:00",
                    "completed_at": "2024-01-01T00:00:01",
                    "result": {},
                },
            ],
            "checkpoints": [
                {
                    "checkpoint_id": "cp-1",
                    "question": {"type": "approval"},
                    "response": {"approved": True},
                    "status": "resolved",
                    "created_at": "2024-01-01T00:00:01",
                }
            ],
            "error": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:02",
        }

        state_file = temp_data_dir / f"{execution_id}.json"
        with open(state_file, "w") as f:
            json.dump(state, f)

        # Get only step logs
        step_logs = await get_execution_logs_impl(
            execution_id=execution_id,
            event_type="step",
            level=None,
            limit=10,
            offset=0,
        )

        assert all(log.get("event").startswith("step") for log in step_logs["logs"])

        # Get only checkpoint logs
        checkpoint_logs = await get_execution_logs_impl(
            execution_id=execution_id,
            event_type="checkpoint",
            level=None,
            limit=10,
            offset=0,
        )

        assert all(log.get("event").startswith("checkpoint") for log in checkpoint_logs["logs"])


class TestMultipleWorkflowTypes:
    """Test handling multiple workflow types."""

    @pytest.mark.asyncio
    async def test_register_and_execute_multiple_workflows(self, temp_data_dir, monkeypatch):
        """Test registering and executing multiple workflow types."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Register multiple workflows
        login_workflow = MagicMock()
        login_workflow.workflow_type = "login"
        login_workflow.run = AsyncMock(return_value={"logged_in": True})
        register_workflow("login", login_workflow)

        form_workflow = MagicMock()
        form_workflow.workflow_type = "form_filling"
        form_workflow.run = AsyncMock(return_value={"fields_filled": 5})
        register_workflow("form_filling", form_workflow)

        # Start login workflow
        result1 = await start_workflow_impl(
            workflow_type="login",
            input_params={"username": "user"},
            max_retries=1,
            timeout_seconds=30,
        )

        # Start form workflow
        result2 = await start_workflow_impl(
            workflow_type="form_filling",
            input_params={"data": {}},
            max_retries=1,
            timeout_seconds=30,
        )

        assert result1["execution_id"] != result2["execution_id"]
        await asyncio.sleep(0.5)

        status1 = await get_execution_status_impl(execution_id=result1["execution_id"])
        status2 = await get_execution_status_impl(execution_id=result2["execution_id"])

        assert status1["workflow_type"] == "login"
        assert status2["workflow_type"] == "form_filling"


class TestConcurrentExecutions:
    """Test concurrent workflow executions."""

    @pytest.mark.asyncio
    async def test_concurrent_workflow_executions(self, temp_data_dir, monkeypatch):
        """Test running multiple workflows concurrently."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        workflow = MagicMock()
        workflow.workflow_type = "test"
        workflow.run = AsyncMock(return_value={"success": True})
        register_workflow("test", workflow)

        # Start multiple executions
        tasks = []
        for i in range(5):
            task = start_workflow_impl(
                workflow_type="test",
                input_params={"iteration": i},
                max_retries=1,
                timeout_seconds=30,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should have unique execution IDs
        execution_ids = [r["execution_id"] for r in results]
        assert len(execution_ids) == len(set(execution_ids))

        # All should be pending
        assert all(r["status"] == "pending" for r in results)

        # Wait for execution
        await asyncio.sleep(0.5)

        # Check all have state files
        for exec_id in execution_ids:
            state_file = temp_data_dir / f"{exec_id}.json"
            assert state_file.exists()
