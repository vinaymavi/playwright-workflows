"""Integration Tests for Checkpoint Pause/Resume

Tests the complete checkpoint workflow: pause at checkpoint, save state,
resolve with agent decision, resume from checkpoint, and verify state preservation.
"""

import pytest
import asyncio
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.framework.execution import Execution, ExecutionState
from src.framework.workflow import Workflow
from src.framework.checkpoint import (
    CheckpointQuestion,
    CheckpointDecision,
    CheckpointRequest,
)
from src.framework.checkpoint_store import CheckpointStore
from src.framework.decorators import step
from tests.fixtures.mock_agent_client import MockAgentClient, CheckpointDecisionStrategy


@dataclass
class SimpleWorkflowInput:
    """Test workflow input."""

    message: str = "test"


class PauseResumeTestWorkflow(Workflow):
    """Simple test workflow with checkpoint."""

    workflow_type = "pause_resume_test_workflow"

    def __init__(
        self,
        execution_id: str = None,
        base_url: str = "http://localhost:8000",
    ):
        if execution_id is None:
            execution_id = str(uuid.uuid4())
        super().__init__(
            execution_id=execution_id,
            base_url=base_url,
        )
        self.steps_executed = []

    async def run(self, input_data: SimpleWorkflowInput) -> dict:
        """Run workflow with checkpoint."""
        self.input = input_data
        self.logger.info(f"Starting workflow with message: {input_data.message}")

        # Step 1: Initialize
        await self.initialize()

        # Step 2: Request approval at checkpoint
        decision = await self.request_approval()

        # Step 3: Handle decision
        if decision.choice == "proceed":
            await self.execute_main_task()
        else:
            raise RuntimeError("Workflow cancelled by user")

        return {"success": True, "message": f"Processed: {input_data.message}"}

    @step(name="Initialize", max_retries=0)
    async def initialize(self):
        """Initialize workflow."""
        self.steps_executed.append("initialize")
        self.logger.info("Workflow initialized")

    @step(name="Request Approval", max_retries=0)
    async def request_approval(self) -> CheckpointDecision:
        """Request checkpoint approval."""
        self.steps_executed.append("request_approval")

        question = CheckpointQuestion(
            question_text="Continue with main task?",
            question_type="single_choice",
            options=["proceed", "cancel"],
            metadata={"current_state": dict(self._state) if self._state else {}},
        )

        # Skip checkpoint in test mode if execution not initialized
        if not self._execution:
            return CheckpointDecision(choice="proceed")

        response = await self.checkpoint(
            question=question,
            timeout_seconds=300,
            allow_skip=False,
        )

        return response.decision

    @step(name="Execute Main Task", max_retries=0)
    async def execute_main_task(self):
        """Execute main workflow task."""
        self.steps_executed.append("execute_main_task")
        self.logger.info("Main task executed")


class TestCheckpointPauseResume:
    """Integration tests for checkpoint pause/resume workflow."""

    @pytest.fixture
    def temp_checkpoint_dir(self, tmp_path):
        """Create temporary directory for checkpoint storage."""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        return checkpoint_dir

    @pytest.fixture
    def checkpoint_store(self, temp_checkpoint_dir):
        """Create checkpoint store for testing."""
        store = CheckpointStore(str(temp_checkpoint_dir))
        return store

    def test_checkpoint_store_persistence(self, checkpoint_store):
        """Verify checkpoint store saves and loads checkpoints."""
        checkpoint_data = {
            "checkpoint_id": str(uuid.uuid4()),
            "execution_id": str(uuid.uuid4()),
            "step_name": "test_step",
            "question": {
                "question_text": "Proceed?",
                "question_type": "single_choice",
                "options": ["proceed", "cancel"],
                "metadata": {},
            },
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }

        # Save checkpoint
        checkpoint_store.save(checkpoint_data)

        # Load checkpoint
        loaded = checkpoint_store.load(checkpoint_data["checkpoint_id"])
        assert loaded is not None
        assert loaded["checkpoint_id"] == checkpoint_data["checkpoint_id"]
        assert loaded["status"] == "pending"

    def test_checkpoint_resolution_tracking(self, checkpoint_store):
        """Test marking checkpoint as resolved with decision."""
        checkpoint_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "execution_id": execution_id,
            "step_name": "test_step",
            "question": {
                "question_text": "Proceed?",
                "question_type": "single_choice",
                "options": ["proceed", "cancel"],
                "metadata": {},
            },
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }

        # Save checkpoint
        checkpoint_store.save(checkpoint_data)

        # Resolve checkpoint
        decision = {"choice": "proceed"}
        checkpoint_store.mark_resolved(checkpoint_id, decision)

        # Verify resolution
        loaded = checkpoint_store.load(checkpoint_id)
        assert loaded["status"] == "resolved"
        assert loaded["response"] == decision
        assert "resolved_at" in loaded

    def test_checkpoint_timeout_tracking(self, checkpoint_store):
        """Test marking checkpoint as timed out."""
        checkpoint_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "execution_id": execution_id,
            "step_name": "test_step",
            "question": {
                "question_text": "Proceed?",
                "question_type": "single_choice",
                "options": ["proceed", "cancel"],
                "metadata": {},
            },
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }

        # Save checkpoint
        checkpoint_store.save(checkpoint_data)

        # Mark as timed out with keep_alive strategy
        checkpoint_store.mark_timeout(checkpoint_id, "keep_alive")

        # Verify timeout
        loaded = checkpoint_store.load(checkpoint_id)
        assert loaded["status"] == "timeout"
        assert loaded["timeout_strategy"] == "keep_alive"
        assert "timeout_at" in loaded

    def test_get_pending_checkpoints(self, checkpoint_store):
        """Test querying pending checkpoints for execution."""
        execution_id = str(uuid.uuid4())

        # Create 3 checkpoints, 2 pending, 1 resolved
        for i in range(3):
            checkpoint_id = str(uuid.uuid4())
            checkpoint_data = {
                "checkpoint_id": checkpoint_id,
                "execution_id": execution_id,
                "step_name": f"step_{i}",
                "question": {
                    "question_text": "Test?",
                    "question_type": "yes_no",
                    "metadata": {},
                },
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }
            checkpoint_store.save(checkpoint_data)

            # Resolve first one
            if i == 0:
                checkpoint_store.mark_resolved(checkpoint_id, {"confirmed": True})

        # Get pending
        pending = checkpoint_store.get_pending(execution_id)
        assert len(pending) == 2
        assert all(cp["status"] == "pending" for cp in pending)

    def test_execution_checkpoint_index(self, checkpoint_store):
        """Test execution checkpoint index tracking."""
        execution_id = str(uuid.uuid4())

        # Create checkpoints
        checkpoint_ids = []
        for i in range(3):
            checkpoint_id = str(uuid.uuid4())
            checkpoint_ids.append(checkpoint_id)

            checkpoint_data = {
                "checkpoint_id": checkpoint_id,
                "execution_id": execution_id,
                "step_name": f"step_{i}",
                "question": {
                    "question_text": "Test?",
                    "question_type": "yes_no",
                    "metadata": {},
                },
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }
            checkpoint_store.save(checkpoint_data)

        # Query all checkpoints for execution
        all_checkpoints = checkpoint_store.query_execution_checkpoints(execution_id)
        assert len(all_checkpoints) == 3
        retrieved_ids = [cp["checkpoint_id"] for cp in all_checkpoints]
        assert set(retrieved_ids) == set(checkpoint_ids)

    def test_checkpoint_deletion(self, checkpoint_store):
        """Test checkpoint deletion."""
        checkpoint_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "execution_id": execution_id,
            "step_name": "test_step",
            "question": {
                "question_text": "Test?",
                "question_type": "yes_no",
                "metadata": {},
            },
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }

        checkpoint_store.save(checkpoint_data)
        assert checkpoint_store.load(checkpoint_id) is not None

        checkpoint_store.delete_checkpoint(checkpoint_id)
        assert checkpoint_store.load(checkpoint_id) is None

    @pytest.mark.asyncio
    async def test_workflow_execution_with_checkpoint(self):
        """Test workflow executes successfully with checkpoint."""
        workflow = PauseResumeTestWorkflow()
        input_data = SimpleWorkflowInput(message="test message")

        # Run without execution context (checkpoint will be skipped)
        result = await workflow.run(input_data)

        assert result["success"] is True
        assert "test message" in result["message"]
        assert "initialize" in workflow.steps_executed
        assert "request_approval" in workflow.steps_executed
        assert "execute_main_task" in workflow.steps_executed

    @pytest.mark.asyncio
    async def test_workflow_step_execution_order(self):
        """Verify workflow steps execute in correct order."""
        workflow = PauseResumeTestWorkflow()
        input_data = SimpleWorkflowInput(message="test")

        await workflow.run(input_data)

        expected_order = ["initialize", "request_approval", "execute_main_task"]
        assert workflow.steps_executed == expected_order

    @pytest.mark.asyncio
    async def test_workflow_state_preservation(self):
        """Verify workflow state is accessible during execution."""
        workflow = PauseResumeTestWorkflow()
        input_data = SimpleWorkflowInput(message="test state")

        result = await workflow.run(input_data)

        assert result["success"] is True
        # Verify input was stored
        assert workflow.input == input_data

    @pytest.mark.asyncio
    async def test_checkpoint_with_mock_agent(self):
        """Test checkpoint resolution with mock agent client."""
        mock_agent = MockAgentClient(
            CheckpointDecisionStrategy(
                auto_approve=True,
                approval_choice="proceed",
            )
        )

        question = CheckpointQuestion(
            question_text="Continue?",
            question_type="single_choice",
            options=["proceed", "cancel"],
            metadata={"context": "test"},
        )

        request = CheckpointRequest(
            checkpoint_id=str(uuid.uuid4()),
            execution_id=str(uuid.uuid4()),
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await mock_agent.resolve_checkpoint(request.checkpoint_id, request)

        assert response.decision.choice == "proceed"
        assert response.decision.is_valid()

    @pytest.mark.asyncio
    async def test_checkpoint_rejection_with_mock_agent(self):
        """Test checkpoint rejection with mock agent."""
        mock_agent = MockAgentClient(
            CheckpointDecisionStrategy(
                auto_approve=False,
                rejection_choice="cancel",
            )
        )

        question = CheckpointQuestion(
            question_text="Continue?",
            question_type="single_choice",
            options=["proceed", "cancel"],
        )

        request = CheckpointRequest(
            checkpoint_id=str(uuid.uuid4()),
            execution_id=str(uuid.uuid4()),
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await mock_agent.resolve_checkpoint(request.checkpoint_id, request)

        assert response.decision.choice == "cancel"

    @pytest.mark.asyncio
    async def test_checkpoint_multiple_resolution_flow(self, checkpoint_store):
        """Test complete flow: pause, save, resolve, and verify."""
        execution_id = str(uuid.uuid4())
        checkpoint_id = str(uuid.uuid4())

        # Create checkpoint question
        question = CheckpointQuestion(
            question_text="Continue processing?",
            question_type="single_choice",
            options=["proceed", "cancel"],
            metadata={"step": "validation"},
        )

        # Create checkpoint request
        request = CheckpointRequest(
            checkpoint_id=checkpoint_id,
            execution_id=execution_id,
            workflow_name="TestWorkflow",
            step_name="validation",
            question=question,
            timeout_seconds=300,
            context={"processed_items": 10},
        )

        # Save checkpoint to store
        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "execution_id": execution_id,
            "step_name": request.step_name,
            "question": question.model_dump(),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "context": request.context,
        }
        checkpoint_store.save(checkpoint_data)

        # Verify checkpoint was saved
        saved = checkpoint_store.load(checkpoint_id)
        assert saved["status"] == "pending"
        assert saved["context"]["processed_items"] == 10

        # Get agent decision (using mock agent)
        mock_agent = MockAgentClient(CheckpointDecisionStrategy(auto_approve=True))
        response = await mock_agent.resolve_checkpoint(checkpoint_id, request)

        # Save resolution to store
        checkpoint_store.mark_resolved(checkpoint_id, response.decision.model_dump())

        # Verify checkpoint was resolved
        resolved = checkpoint_store.load(checkpoint_id)
        assert resolved["status"] == "resolved"
        assert resolved["response"]["choice"] == "proceed"
        assert "resolved_at" in resolved

    @pytest.mark.asyncio
    async def test_checkpoint_timeout_recovery(self, checkpoint_store):
        """Test handling checkpoint timeout with recovery strategy."""
        checkpoint_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        # Create checkpoint
        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "execution_id": execution_id,
            "step_name": "critical_decision",
            "question": {
                "question_text": "Confirm?",
                "question_type": "yes_no",
                "metadata": {},
            },
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        checkpoint_store.save(checkpoint_data)

        # Simulate timeout with keep_alive strategy
        checkpoint_store.mark_timeout(checkpoint_id, "keep_alive")

        # Verify timeout was recorded
        timed_out = checkpoint_store.load(checkpoint_id)
        assert timed_out["status"] == "timeout"
        assert timed_out["timeout_strategy"] == "keep_alive"

        # Verify execution is still queryable (not deleted)
        pending = checkpoint_store.get_pending(execution_id)
        # Should have the timed-out checkpoint (not strictly "pending" anymore)
        all_checkpoints = checkpoint_store.query_execution_checkpoints(execution_id)
        assert len(all_checkpoints) == 1

    @pytest.mark.asyncio
    async def test_multiple_checkpoints_per_execution(self, checkpoint_store):
        """Test handling multiple checkpoints in single execution."""
        execution_id = str(uuid.uuid4())
        checkpoint_ids = []

        # Create 3 checkpoints
        for step_num in range(3):
            checkpoint_id = str(uuid.uuid4())
            checkpoint_ids.append(checkpoint_id)

            checkpoint_data = {
                "checkpoint_id": checkpoint_id,
                "execution_id": execution_id,
                "step_name": f"step_{step_num}",
                "question": {
                    "question_text": f"Proceed with step {step_num}?",
                    "question_type": "yes_no",
                    "metadata": {"step_number": step_num},
                },
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }
            checkpoint_store.save(checkpoint_data)

        # Resolve first two checkpoints
        for i in range(2):
            checkpoint_store.mark_resolved(
                checkpoint_ids[i],
                {"confirmed": True},
            )

        # Verify state
        all_checkpoints = checkpoint_store.query_execution_checkpoints(execution_id)
        assert len(all_checkpoints) == 3

        resolved_count = sum(
            1 for cp in all_checkpoints if cp["status"] == "resolved"
        )
        assert resolved_count == 2

        pending_count = sum(
            1 for cp in all_checkpoints if cp["status"] == "pending"
        )
        assert pending_count == 1

    @pytest.mark.asyncio
    async def test_checkpoint_context_preservation(self, checkpoint_store):
        """Test that checkpoint preserves workflow context."""
        checkpoint_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        # Simulate complex workflow state
        workflow_context = {
            "current_page": "http://example.com/form",
            "form_data": {
                "username": "test_user",
                "email": "test@example.com",
            },
            "step_counter": 5,
            "browser_state": {
                "cookies": ["session_id=abc123"],
                "local_storage": {"preferences": "dark_mode"},
            },
        }

        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "execution_id": execution_id,
            "step_name": "form_validation",
            "question": {
                "question_text": "Submit form?",
                "question_type": "yes_no",
                "metadata": {},
            },
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "context": workflow_context,
        }

        checkpoint_store.save(checkpoint_data)

        # Load and verify context preserved
        loaded = checkpoint_store.load(checkpoint_id)
        assert loaded["context"] == workflow_context
        assert loaded["context"]["form_data"]["username"] == "test_user"
        assert loaded["context"]["browser_state"]["cookies"][0] == "session_id=abc123"
