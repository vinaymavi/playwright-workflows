"""E2E integration tests for Agent ↔ MCP ↔ Workflow communication.

Tests the complete flow of:
1. Agent starts workflow via MCP
2. Workflow pauses at checkpoint
3. Agent lists paused executions
4. Agent resolves checkpoint
5. Workflow resumes and completes
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp_server.tools import (
    list_executions_impl,
    register_workflow,
    resolve_checkpoint_impl,
    start_workflow_impl,
)


# Simple test workflow for E2E testing
class SimpleTestWorkflow:
    """Minimal workflow for E2E testing."""

    def __init__(self):
        self._execution = None
        self.logger = MagicMock()

    def set_execution(self, execution):
        self._execution = execution

    async def run(self, **kwargs):
        """Execute workflow with built-in checkpoint."""
        from src.framework.checkpoint import CheckpointQuestion, CheckpointRequest

        # Simulate step 1
        self.logger.info("Step 1: Starting")
        await asyncio.sleep(0.01)

        # Pause at checkpoint
        self.logger.info("Step 1.5: Checkpoint")
        question = CheckpointQuestion(
            question_type="yes_no",
            question_text="Continue to step 2?"
        )
        checkpoint_req = CheckpointRequest(
            checkpoint_id="cp-1",
            execution_id=self._execution.execution_id,
            workflow_name="simple_test",
            step_name="step_1",
            question=question
        )

        # Mock the checkpoint wait (for testing, we'll skip this)
        # In real scenario, workflow would wait for agent decision here

        # Simulate step 2
        self.logger.info("Step 2: Completing")
        await asyncio.sleep(0.01)

        return {"success": True, "message": "Workflow completed"}


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for execution states."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(autouse=True)
def setup_workflow_registry():
    """Register test workflow."""
    register_workflow("simple_test", SimpleTestWorkflow)
    yield
    # Cleanup not needed for simple_test as it's a test-only workflow


class TestE2EAgentMCPWorkflow:
    """End-to-end tests for Agent ↔ MCP ↔ Workflow integration."""

    @pytest.mark.asyncio
    async def test_start_workflow_creates_execution(self, temp_data_dir, monkeypatch):
        """Test that starting workflow creates execution state."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Start workflow
        result = await start_workflow_impl(
            workflow_type="simple_test",
            input_params={"url": "http://example.com"},
            max_retries=2,
            timeout_seconds=300
        )

        # Verify execution was created
        assert "execution_id" in result
        assert result["workflow_type"] == "simple_test"
        assert result["status"] == "pending"

        # Verify execution state file exists
        execution_id = result["execution_id"]
        execution_file = temp_data_dir / f"{execution_id}.json"
        assert execution_file.exists()

        # Verify state file contents
        state = json.loads(execution_file.read_text())
        assert state["execution_id"] == execution_id
        assert state["workflow_type"] == "simple_test"
        assert state["status"] == "pending"
        assert state["input_params"] == {"url": "http://example.com"}

    @pytest.mark.asyncio
    async def test_list_executions_returns_all_when_no_filter(self, temp_data_dir, monkeypatch):
        """Test listing all executions without status filter."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create multiple executions
        exec1 = await start_workflow_impl("simple_test", {"id": 1})
        exec2 = await start_workflow_impl("simple_test", {"id": 2})

        # List all executions
        result = await list_executions_impl(status=None, limit=50, offset=0)

        assert result["total"] == 2
        assert result["returned"] == 2
        assert len(result["executions"]) == 2

    @pytest.mark.asyncio
    async def test_list_executions_filters_by_status(self, temp_data_dir, monkeypatch):
        """Test filtering executions by status."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create executions with different statuses
        exec1 = await start_workflow_impl("simple_test", {"id": 1})
        exec2 = await start_workflow_impl("simple_test", {"id": 2})

        # Update one to running status
        exec1_file = temp_data_dir / f"{exec1['execution_id']}.json"
        exec1_state = json.loads(exec1_file.read_text())
        exec1_state["status"] = "running"
        exec1_file.write_text(json.dumps(exec1_state))

        # Filter for pending only
        result = await list_executions_impl(status="pending", limit=50, offset=0)

        assert result["total"] == 2
        assert result["returned"] == 1
        assert result["executions"][0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_updates_execution_status(self, temp_data_dir, monkeypatch):
        """Test that resolving checkpoint updates execution state."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create execution
        exec_result = await start_workflow_impl("simple_test")
        execution_id = exec_result["execution_id"]

        # Add checkpoint to execution
        exec_file = temp_data_dir / f"{execution_id}.json"
        exec_state = json.loads(exec_file.read_text())
        exec_state["status"] = "paused"
        exec_state["checkpoints"] = [
            {
                "checkpoint_id": "cp-1",
                "question": {"question_text": "Continue?", "question_type": "yes_no"},
                "response": None
            }
        ]
        exec_file.write_text(json.dumps(exec_state))

        # Resolve checkpoint
        decision = {"confirmed": True, "value": "proceed"}
        result = await resolve_checkpoint_impl(
            execution_id=execution_id,
            checkpoint_id="cp-1",
            decision=decision,
            agent_id="test-agent"
        )

        # Verify resolution
        assert result["status"] == "running"
        assert result["execution_id"] == execution_id

        # Verify checkpoint was updated in state file
        updated_state = json.loads(exec_file.read_text())
        checkpoint = updated_state["checkpoints"][0]
        assert checkpoint["response"] == decision
        assert checkpoint["agent_id"] == "test-agent"
        assert "resolved_at" in checkpoint

    @pytest.mark.asyncio
    async def test_full_workflow_lifecycle(self, temp_data_dir, monkeypatch):
        """Test complete workflow lifecycle: create → pause → resume → complete.

        This is the core E2E test demonstrating:
        1. Agent calls start_workflow
        2. Workflow is created and execution state is saved
        3. Agent polls status to see "paused"
        4. Agent calls list_executions to find paused workflow
        5. Agent calls resolve_checkpoint to continue
        6. Execution state updates to reflect decision
        """
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Step 1: Agent starts workflow
        exec_result = await start_workflow_impl(
            workflow_type="simple_test",
            input_params={"url": "http://example.com", "username": "test"}
        )
        execution_id = exec_result["execution_id"]
        assert exec_result["status"] == "pending"

        # Step 2: Simulate workflow running and hitting checkpoint
        exec_file = temp_data_dir / f"{execution_id}.json"
        exec_state = json.loads(exec_file.read_text())
        exec_state["status"] = "paused"
        exec_state["current_step"] = "authenticate"
        exec_state["checkpoints"] = [
            {
                "checkpoint_id": "cp-1",
                "question": {
                    "question_text": "Is authentication successful?",
                    "question_type": "yes_no"
                },
                "response": None,
                "created_at": "2026-11-02T10:00:00Z"
            }
        ]
        exec_file.write_text(json.dumps(exec_state))

        # Step 3: Agent polls status
        from src.mcp_server.tools import get_execution_status_impl

        status = await get_execution_status_impl(execution_id)
        assert status["status"] == "paused"
        assert status["current_step_name"] == "authenticate"
        assert status["pending_checkpoint"] is not None
        assert status["pending_checkpoint"]["checkpoint_id"] == "cp-1"

        # Step 4: Agent lists paused executions
        paused_list = await list_executions_impl(status="paused", limit=50, offset=0)
        assert paused_list["returned"] == 1
        assert paused_list["executions"][0]["execution_id"] == execution_id
        assert paused_list["executions"][0]["pending_checkpoint"]["checkpoint_id"] == "cp-1"

        # Step 5: Agent resolves checkpoint
        decision = {"confirmed": True, "action": "continue"}
        resolve_result = await resolve_checkpoint_impl(
            execution_id=execution_id,
            checkpoint_id="cp-1",
            decision=decision,
            agent_id="claude"
        )
        assert resolve_result["status"] == "running"

        # Step 6: Verify execution state reflects decision
        updated_state = json.loads(exec_file.read_text())
        assert updated_state["status"] == "running"
        checkpoint = updated_state["checkpoints"][0]
        assert checkpoint["response"] == decision
        assert checkpoint["agent_id"] == "claude"
        assert "resolved_at" in checkpoint

    @pytest.mark.asyncio
    async def test_agent_can_reject_at_checkpoint(self, temp_data_dir, monkeypatch):
        """Test agent can reject action at checkpoint."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create paused execution
        exec_result = await start_workflow_impl("simple_test")
        execution_id = exec_result["execution_id"]

        exec_file = temp_data_dir / f"{execution_id}.json"
        exec_state = json.loads(exec_file.read_text())
        exec_state["status"] = "paused"
        exec_state["checkpoints"] = [
            {
                "checkpoint_id": "cp-1",
                "question": {
                    "question_text": "Fill form automatically?",
                    "question_type": "yes_no",
                    "options": ["yes", "no"]
                },
                "response": None
            }
        ]
        exec_file.write_text(json.dumps(exec_state))

        # Agent rejects with decision
        decision = {"confirmed": False, "reason": "Requires manual verification"}
        result = await resolve_checkpoint_impl(
            execution_id=execution_id,
            checkpoint_id="cp-1",
            decision=decision,
            agent_id="safety-agent"
        )

        # Verify rejection was recorded
        assert result["status"] == "running"
        updated_state = json.loads(exec_file.read_text())
        checkpoint = updated_state["checkpoints"][0]
        assert checkpoint["response"]["confirmed"] is False
        assert checkpoint["response"]["reason"] == "Requires manual verification"

    @pytest.mark.asyncio
    async def test_multiple_concurrent_checkpoints(self, temp_data_dir, monkeypatch):
        """Test handling multiple workflows paused at different checkpoints."""
        monkeypatch.setenv("WORKFLOW_DATA_DIR", str(temp_data_dir))

        # Create 3 paused executions
        execution_ids = []
        for i in range(3):
            exec_result = await start_workflow_impl("simple_test", {"id": i})
            execution_id = exec_result["execution_id"]
            execution_ids.append(execution_id)

            # Create paused state with checkpoint
            exec_file = temp_data_dir / f"{execution_id}.json"
            exec_state = json.loads(exec_file.read_text())
            exec_state["status"] = "paused"
            exec_state["current_step"] = f"step_{i}"
            exec_state["checkpoints"] = [
                {
                    "checkpoint_id": f"cp-{i}",
                    "question": {"question_text": f"Confirm step {i}?", "question_type": "yes_no"},
                    "response": None
                }
            ]
            exec_file.write_text(json.dumps(exec_state))

        # Agent lists all paused
        paused = await list_executions_impl(status="paused", limit=50, offset=0)
        assert paused["total"] == 3
        assert paused["returned"] == 3

        # Agent resolves all checkpoints concurrently
        tasks = [
            resolve_checkpoint_impl(
                execution_id=execution_ids[i],
                checkpoint_id=f"cp-{i}",
                decision={"confirmed": True, "index": i}
            )
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks)

        # Verify all resolved
        assert len(results) == 3
        assert all(r["status"] == "running" for r in results)

        # Verify all state files updated
        for i, execution_id in enumerate(execution_ids):
            exec_file = temp_data_dir / f"{execution_id}.json"
            state = json.loads(exec_file.read_text())
            assert state["status"] == "running"
            assert state["checkpoints"][0]["response"]["index"] == i
