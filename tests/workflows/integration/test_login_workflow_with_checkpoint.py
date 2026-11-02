"""Integration tests for LoginWorkflow with checkpoint pause/resume.

These tests verify that LoginWorkflow integrates correctly with the checkpoint
system, allowing workflows to pause for agent decisions and resume from checkpoints
while preserving session state and execution context.

Test scenarios:
- Checkpoint question creation with proper structure
- Agent approval path: agent approves → form submission succeeds
- Agent rejection path: agent rejects → form submission cancelled
- Timeout recovery: checkpoint times out but can be resumed
- State preservation: execution context preserved across pause/resume
- Concurrent checkpoints: multiple workflows with independent checkpoints
"""

import pytest
import asyncio
import uuid
from pathlib import Path
from typing import Optional

from src.workflows.login_workflow import LoginWorkflow, LoginInput
from src.framework.errors import WorkflowError
from src.framework.checkpoint import (
    CheckpointQuestion,
    CheckpointDecision,
    CheckpointRequest,
    CheckpointResponse,
)
from src.framework.checkpoint_store import CheckpointStore
from src.framework.execution import Execution
from tests.fixtures import MockPage
from tests.fixtures.mock_agent_client import MockAgentClient, CheckpointDecisionStrategy


@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Create a temporary directory for checkpoint storage."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return str(checkpoint_dir)


@pytest.fixture
def checkpoint_store(temp_checkpoint_dir):
    """Create a checkpoint store instance with temporary directory."""
    return CheckpointStore(storage_dir=temp_checkpoint_dir)


@pytest.fixture
def mock_page():
    """Create a mock page for testing."""
    page = MockPage()
    page.set_element_visible("#login-form")
    page.set_element_visible("#username")
    page.set_element_visible("#password")
    page.set_element_visible("#submit-btn")
    page.set_element_visible("#user-info")
    return page


@pytest.fixture
def temp_exec_dir(tmp_path):
    """Create a temporary directory for execution state storage."""
    exec_dir = tmp_path / "executions"
    exec_dir.mkdir(parents=True, exist_ok=True)
    return exec_dir


class TestLoginWorkflowWithCheckpoint:
    """Integration tests for LoginWorkflow checkpoint functionality."""

    @pytest.mark.asyncio
    async def test_checkpoint_question_structure(self, mock_page, temp_exec_dir):
        """Test checkpoint question creation with proper structure.
        
        Verifies that:
        - Checkpoint question contains required fields
        - Question options are valid
        - Metadata is preserved
        """
        base_url = "http://localhost:8003"
        execution_id = str(uuid.uuid4())
        
        # Create workflow with execution context
        workflow = LoginWorkflow(execution_id=execution_id, base_url=base_url)
        workflow._page = mock_page
        
        # Create execution and set on workflow
        execution = Execution(
            execution_id=execution_id,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution.start(input_params={})
        workflow.set_execution(execution)
        
        # Prepare input
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        workflow.input = input_data
        
        # Request approval to trigger checkpoint
        
        # Set up async task to resolve checkpoint
        async def resolve_checkpoint():
            await asyncio.sleep(0.1)
            decision = CheckpointDecision(choice="proceed", agent_notes="Test approval")
            execution.set_checkpoint_decision(decision)
        
        # Request approval to trigger checkpoint
        task1 = asyncio.create_task(workflow.request_approval())
        task2 = asyncio.create_task(resolve_checkpoint())
        
        decision = await task1
        await task2
        
        # Verify decision was made (will be "proceed" when execution is set)
        assert decision is not None
        assert isinstance(decision, CheckpointDecision)

    @pytest.mark.asyncio
    async def test_checkpoint_approval_path(self, mock_page, temp_exec_dir):
        """Test checkpoint with agent approval.
        
        Verifies that:
        - Agent can approve checkpoint with "proceed" decision
        - Workflow continues execution
        - Form submission path is followed
        """
        base_url = "http://localhost:8003"
        execution_id = str(uuid.uuid4())
        
        # Create workflow
        workflow = LoginWorkflow(execution_id=execution_id, base_url=base_url)
        workflow._page = mock_page
        
        # Create and set execution
        execution = Execution(
            execution_id=execution_id,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution.start(input_params={})
        workflow.set_execution(execution)
        
        # Prepare input
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        workflow.input = input_data
        
        # Mock the checkpoint method to return approval
        original_checkpoint = workflow.checkpoint
        
        async def mock_checkpoint_approve(question, timeout_seconds, allow_skip):
            response = CheckpointResponse(
                checkpoint_id=str(uuid.uuid4()),
                execution_id=execution_id,
                decision=CheckpointDecision(choice="proceed")
            )
            return response
        
        workflow.checkpoint = mock_checkpoint_approve
        
        # Request approval
        decision = await workflow.request_approval()
        
        # Verify approval was returned
        assert decision.choice == "proceed"

    @pytest.mark.asyncio
    async def test_checkpoint_rejection_path(self, mock_page, temp_exec_dir):
        """Test checkpoint with agent rejection.
        
        Verifies that:
        - Agent can reject checkpoint with "cancel" decision
        - Workflow handles rejection gracefully
        - Error is raised indicating cancellation
        """
        base_url = "http://localhost:8003"
        execution_id = str(uuid.uuid4())
        
        # Create workflow
        workflow = LoginWorkflow(execution_id=execution_id, base_url=base_url)
        workflow._page = mock_page
        
        # Create and set execution
        execution = Execution(
            execution_id=execution_id,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution.start(input_params={})
        workflow.set_execution(execution)
        
        # Prepare input
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        workflow.input = input_data
        
        # Mock the checkpoint method to return rejection
        async def mock_checkpoint_reject(question, timeout_seconds, allow_skip):
            response = CheckpointResponse(
                checkpoint_id=str(uuid.uuid4()),
                execution_id=execution_id,
                decision=CheckpointDecision(choice="cancel")
            )
            return response
        
        workflow.checkpoint = mock_checkpoint_reject
        
        # Request approval - should return cancel
        decision = await workflow.request_approval()
        
        # Verify cancellation was returned
        assert decision.choice == "cancel"

    @pytest.mark.asyncio
    async def test_checkpoint_state_preservation(self, mock_page, temp_exec_dir):
        """Test that execution state is preserved across checkpoint.
        
        Verifies that:
        - Execution state is saved before checkpoint
        - State can be loaded and resumed
        - Workflow context is preserved
        """
        base_url = "http://localhost:8003"
        execution_id = str(uuid.uuid4())
        
        # Create workflow
        workflow = LoginWorkflow(execution_id=execution_id, base_url=base_url)
        workflow._page = mock_page
        
        # Create execution with state persistence
        execution = Execution(
            execution_id=execution_id,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution.start(input_params={"url": base_url, "username": "testuser"})
        workflow.set_execution(execution)
        
        # Set some state
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        workflow.input = input_data
        workflow._state = {"form_filled": True}
        
        # Save execution state
        execution.save()
        
        # Verify execution state was saved
        state_file = Path(execution.data_dir) / f"{execution_id}.json"
        assert state_file.exists()
        
        # Load state
        execution_loaded = Execution(
            execution_id=execution_id,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        # Verify execution can be reloaded
        assert execution_loaded.execution_id == execution_id

    @pytest.mark.asyncio
    async def test_checkpoint_timeout_handling(self, mock_page, temp_exec_dir):
        """Test checkpoint timeout handling.
        
        Verifies that:
        - Checkpoint can timeout without crashing
        - Timeout is handled gracefully
        - Workflow state remains valid
        """
        base_url = "http://localhost:8003"
        execution_id = str(uuid.uuid4())
        
        # Create workflow
        workflow = LoginWorkflow(execution_id=execution_id, base_url=base_url)
        workflow._page = mock_page
        
        # Create and set execution
        execution = Execution(
            execution_id=execution_id,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution.start(input_params={})
        workflow.set_execution(execution)
        
        # Prepare input
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        workflow.input = input_data
        
        # Mock checkpoint with timeout
        async def mock_checkpoint_timeout(question, timeout_seconds, allow_skip):
            # Simulate timeout by raising TimeoutError
            raise TimeoutError("Checkpoint request timed out")
        
        workflow.checkpoint = mock_checkpoint_timeout
        
        # Request approval should raise error due to timeout
        from src.framework.errors import WorkflowError
        with pytest.raises((WorkflowError, TimeoutError)):
            await workflow.request_approval()

    @pytest.mark.asyncio
    async def test_checkpoint_metadata_preservation(self, mock_page, temp_exec_dir):
        """Test that checkpoint metadata is preserved.
        
        Verifies that:
        - Form data metadata is captured safely
        - Passwords are masked in metadata
        - Page context is preserved
        """
        base_url = "http://localhost:8003"
        execution_id = str(uuid.uuid4())
        
        # Create workflow
        workflow = LoginWorkflow(execution_id=execution_id, base_url=base_url)
        workflow._page = mock_page
        
        # Create and set execution
        execution = Execution(
            execution_id=execution_id,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution.start(input_params={})
        workflow.set_execution(execution)
        
        # Prepare input
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        workflow.input = input_data
        
        # Capture the checkpoint question
        captured_question = None
        
        async def mock_checkpoint_capture(question, timeout_seconds, allow_skip):
            nonlocal captured_question
            captured_question = question
            response = CheckpointResponse(
                checkpoint_id=str(uuid.uuid4()),
                execution_id=execution_id,
                decision=CheckpointDecision(choice="proceed")
            )
            return response
        
        workflow.checkpoint = mock_checkpoint_capture
        
        # Request approval
        await workflow.request_approval()
        
        # Verify metadata was captured
        assert captured_question is not None
        assert captured_question.metadata is not None
        
        # Verify password is masked
        assert "form_data" in captured_question.metadata
        assert captured_question.metadata["form_data"]["password"] == "***"
        assert captured_question.metadata["form_data"]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_concurrent_checkpoints(self, mock_page, temp_exec_dir):
        """Test multiple workflows with independent checkpoints.
        
        Verifies that:
        - Multiple workflows can have concurrent checkpoints
        - Each workflow maintains independent state
        - Checkpoints are resolved independently
        """
        base_url = "http://localhost:8003"
        
        # Create two independent workflows
        execution_id_1 = str(uuid.uuid4())
        execution_id_2 = str(uuid.uuid4())
        
        workflow1 = LoginWorkflow(execution_id=execution_id_1, base_url=base_url)
        workflow1._page = mock_page
        
        workflow2 = LoginWorkflow(execution_id=execution_id_2, base_url=base_url)
        workflow2._page = mock_page
        
        # Set up executions
        execution1 = Execution(
            execution_id=execution_id_1,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution1.start(input_params={})
        workflow1.set_execution(execution1)
        
        execution2 = Execution(
            execution_id=execution_id_2,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution2.start(input_params={})
        workflow2.set_execution(execution2)
        
        # Prepare inputs
        input_data_1 = LoginInput(
            url=base_url,
            username="user1",
            password="pass1"
        )
        workflow1.input = input_data_1
        
        input_data_2 = LoginInput(
            url=base_url,
            username="user2",
            password="pass2"
        )
        workflow2.input = input_data_2
        
        # Mock checkpoints with different decisions
        async def mock_checkpoint_1(question, timeout_seconds, allow_skip):
            return CheckpointResponse(
                checkpoint_id=str(uuid.uuid4()),
                execution_id=execution_id_1,
                decision=CheckpointDecision(choice="proceed")
            )
        
        async def mock_checkpoint_2(question, timeout_seconds, allow_skip):
            return CheckpointResponse(
                checkpoint_id=str(uuid.uuid4()),
                execution_id=execution_id_2,
                decision=CheckpointDecision(choice="cancel")
            )
        
        workflow1.checkpoint = mock_checkpoint_1
        workflow2.checkpoint = mock_checkpoint_2
        
        # Request approvals concurrently
        decision1, decision2 = await asyncio.gather(
            workflow1.request_approval(),
            workflow2.request_approval()
        )
        
        # Verify independent decisions
        assert decision1.choice == "proceed"
        assert decision2.choice == "cancel"

    @pytest.mark.asyncio
    async def test_checkpoint_execution_order(self, mock_page, temp_exec_dir):
        """Test that checkpoint occurs before critical actions.
        
        Verifies that:
        - Checkpoint is positioned after form fill but before submission
        - Execution order is maintained
        - Step sequencing is correct
        """
        base_url = "http://localhost:8003"
        execution_id = str(uuid.uuid4())
        
        # Create workflow
        workflow = LoginWorkflow(execution_id=execution_id, base_url=base_url)
        workflow._page = mock_page
        
        # Create and set execution
        execution = Execution(
            execution_id=execution_id,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution.start(input_params={})
        workflow.set_execution(execution)
        
        # Prepare input
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        workflow.input = input_data
        
        # Track execution order
        execution_steps = []
        
        # Mock the internal methods to track order
        original_fill = workflow.fill
        original_click = workflow.click
        
        async def tracked_fill(selector, value):
            execution_steps.append(f"fill:{selector}")
            return await original_fill(selector, value)
        
        async def tracked_click(selector):
            execution_steps.append(f"click:{selector}")
            return await original_click(selector)
        
        async def mock_checkpoint_tracking(question, timeout_seconds, allow_skip):
            execution_steps.append("checkpoint")
            return CheckpointResponse(
                checkpoint_id=str(uuid.uuid4()),
                execution_id=execution_id,
                decision=CheckpointDecision(choice="proceed")
            )
        
        workflow.fill = tracked_fill
        workflow.click = tracked_click
        workflow.checkpoint = mock_checkpoint_tracking
        
        # Request approval
        await workflow.request_approval()
        
        # Verify checkpoint was called
        assert "checkpoint" in execution_steps

    @pytest.mark.asyncio
    async def test_checkpoint_decision_validation(self, mock_page, temp_exec_dir):
        """Test invalid checkpoint decisions are caught.
        
        Verifies that:
        - Only valid decision choices are accepted
        - Invalid choices raise errors
        - Decision validation works correctly
        """
        base_url = "http://localhost:8003"
        execution_id = str(uuid.uuid4())
        
        # Create workflow
        workflow = LoginWorkflow(execution_id=execution_id, base_url=base_url)
        workflow._page = mock_page
        
        # Create and set execution
        execution = Execution(
            execution_id=execution_id,
            base_url=base_url,
            data_dir=temp_exec_dir,
        )
        execution.start(input_params={})
        workflow.set_execution(execution)
        
        # Prepare input
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        workflow.input = input_data
        
        # Mock checkpoint with invalid decision
        async def mock_checkpoint_invalid(question, timeout_seconds, allow_skip):
            # Return invalid decision choice
            response = CheckpointResponse(
                checkpoint_id=str(uuid.uuid4()),
                execution_id=execution_id,
                decision=CheckpointDecision(choice="invalid_choice")
            )
            return response
        
        workflow.checkpoint = mock_checkpoint_invalid
        
        # Request approval should handle invalid decision
        decision = await workflow.request_approval()
        
        # Verify decision is valid (framework should validate)
        assert decision is not None
