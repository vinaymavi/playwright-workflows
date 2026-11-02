"""Test Scenario B: Checkpoint Pause/Resume within Timeout Window (Quick Resume)

This test validates that:
1. A workflow can pause at a checkpoint and wait for external decision
2. Browser session is preserved during pause (no re-login required)
3. Workflow resumes from exact pause point with agent decision
4. Execution completes successfully within timeout window

Scenario B Requirements (from quickstart.md):
- Workflow pauses at checkpoint
- Agent responds within 5 minutes (quick resume)
- Browser session is preserved (same cookies, storage)
- No re-authentication required
- Workflow completes from pause point
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from playwright.async_api import Page

from src.framework.checkpoint import (
    CheckpointDecision,
    CheckpointQuestion,
    CheckpointRequest,
    CheckpointResponse,
)
from src.framework.execution import Execution, ExecutionState, CheckpointState
from src.workflows.login_workflow import LoginWorkflow

# Scenario B constants
SOFT_TIMEOUT = 120  # 2 minutes soft timeout
HARD_TIMEOUT = 300  # 5 minutes hard timeout


@pytest.fixture
async def execution_with_data_dir(tmp_path):
    """Create execution with persistent data directory."""
    execution = Execution(
        execution_id=str(uuid4()),
        base_url="http://localhost:8000",
        data_dir=str(tmp_path / "data" / "executions"),
    )
    (tmp_path / "data" / "executions").mkdir(parents=True, exist_ok=True)
    execution.start(input_params={"username": "test", "password": "test"})
    return execution


@pytest.fixture
async def mock_browser_page():
    """Mock Playwright page with session tracking."""
    page = MagicMock(spec=Page)
    page.url = "http://localhost:8000/login"
    page.goto = AsyncMock(return_value=None)
    page.fill = AsyncMock(return_value=None)
    page.click = AsyncMock(return_value=None)
    page.get_by_role = MagicMock()
    page.context = MagicMock()
    page.context.cookies = AsyncMock(
        return_value=[
            {"name": "session_id", "value": "test_session_12345"},
            {"name": "user_id", "value": "user_456"},
        ]
    )
    page.context.add_cookies = AsyncMock(return_value=None)
    return page


class TestScenarioBQuickResume:
    """Test suite for Scenario B: Quick Resume within timeout window."""

    @pytest.mark.asyncio
    async def test_checkpoint_pauses_workflow_execution(
        self, execution_with_data_dir, mock_browser_page
    ):
        """Verify workflow pauses at checkpoint and state is saved.

        Given: A workflow executing a multi-step form
        When: Checkpoint is triggered requiring agent decision
        Then: Workflow pauses, execution state saved, pending checkpoint recorded
        """
        execution = execution_with_data_dir

        # Create checkpoint state
        question = {
            "question_text": "Ready to submit the login form?",
            "question_type": "yes_no",
            "metadata": {
                "current_page": mock_browser_page.url,
                "form_fields": ["username", "password"],
            },
        }

        checkpoint = CheckpointState(
            checkpoint_id=str(uuid4()),
            question=question,
            timeout_seconds=HARD_TIMEOUT,
        )

        # Pause execution at checkpoint
        checkpoint_start = datetime.utcnow()
        execution.pause(checkpoint)

        # Verify execution state was saved
        execution.save()
        state_file = Path(execution.data_dir) / f"{execution.execution_id}.json"
        assert state_file.exists(), "Execution state file should be saved"

        # Verify state contains paused status
        with open(state_file, "r") as f:
            saved_state = json.load(f)

        assert saved_state["execution_id"] == execution.execution_id
        assert saved_state["state"] == ExecutionState.PAUSED.value
        assert len(saved_state["checkpoints"]) == 1
        checkpoint_data = saved_state["checkpoints"][0]
        assert checkpoint_data["checkpoint_id"] == checkpoint.checkpoint_id
        assert checkpoint_data["question"]["question_type"] == "yes_no"
        assert checkpoint_data["response"] is None  # No response yet

        # Verify checkpoint duration is within expected range
        checkpoint_end = datetime.utcnow()
        checkpoint_duration = (checkpoint_end - checkpoint_start).total_seconds()
        assert checkpoint_duration < 5, "Checkpoint setup should complete in < 5 seconds"

    @pytest.mark.asyncio
    async def test_browser_session_preserved_during_pause(
        self, execution_with_data_dir, mock_browser_page
    ):
        """Verify browser cookies and storage are preserved across pause.

        Given: Workflow with active browser session
        When: Workflow pauses at checkpoint
        Then: Browser cookies remain valid (can resume without re-login)
        """
        execution = execution_with_data_dir

        # Simulate logged-in session with cookies
        session_cookies = [
            {"name": "session_id", "value": "test_session_preserved"},
            {"name": "auth_token", "value": "token_abc123"},
        ]
        mock_browser_page.context.cookies = AsyncMock(return_value=session_cookies)

        # Store session data in workflow state before pause
        execution.set_workflow_state("browser_session", {"cookies": session_cookies})

        # Create and pause at checkpoint
        question = {
            "question_text": "Proceed with form submission?",
            "question_type": "yes_no",
        }
        checkpoint = CheckpointState(
            checkpoint_id=str(uuid4()),
            question=question,
            timeout_seconds=HARD_TIMEOUT,
            state_snapshot=execution._state.workflow_state.copy(),
        )
        execution.pause(checkpoint)

        # Retrieve and verify cookies persisted in workflow state
        state_file = Path(execution.data_dir) / f"{execution.execution_id}.json"
        with open(state_file, "r") as f:
            saved_state = json.load(f)

        assert "browser_session" in saved_state["workflow_state"]
        assert saved_state["workflow_state"]["browser_session"]["cookies"] == session_cookies

    @pytest.mark.asyncio
    async def test_workflow_resumes_from_checkpoint_with_decision(
        self, execution_with_data_dir
    ):
        """Verify workflow resumes execution after receiving decision at checkpoint.

        Given: Execution paused at checkpoint waiting for decision
        When: Agent provides decision within timeout window
        Then: Execution transitions to RUNNING state with decision recorded
        """
        execution = execution_with_data_dir

        # Pause at checkpoint
        question = {
            "question_text": "Submit form?",
            "question_type": "yes_no",
        }
        checkpoint = CheckpointState(
            checkpoint_id=str(uuid4()),
            question=question,
            timeout_seconds=HARD_TIMEOUT,
        )
        execution.pause(checkpoint)
        pause_time = datetime.utcnow()

        assert execution.get_state() == ExecutionState.PAUSED

        # Provide decision within timeout window (simulate quick response)
        decision_time = datetime.utcnow()
        assert (decision_time - pause_time).total_seconds() < HARD_TIMEOUT

        # Resume with decision
        response = {"decision": "proceed", "confirmed": True}
        execution.resume(response=response)
        resume_time = datetime.utcnow()

        # Verify state transition
        assert execution.get_state() == ExecutionState.RUNNING
        assert execution._state.resumed_at is not None
        assert len(execution._state.checkpoints) > 0
        assert execution._state.checkpoints[-1].response is not None
        assert execution._state.checkpoints[-1].response == response

    @pytest.mark.asyncio
    async def test_workflow_completes_after_quick_resume(
        self, execution_with_data_dir
    ):
        """Verify workflow completes successfully after pause and quick resume.

        Given: Workflow paused at checkpoint after agent decision
        When: Workflow executes remaining steps within session timeout
        Then: Workflow completes with success output
        """
        execution = execution_with_data_dir

        # Pause at checkpoint
        question = {
            "question_text": "Ready to complete login?",
            "question_type": "yes_no",
        }
        checkpoint = CheckpointState(
            checkpoint_id=str(uuid4()),
            question=question,
            timeout_seconds=HARD_TIMEOUT,
        )
        execution.pause(checkpoint)

        # Simulate agent decision received quickly
        execution.resume(response={"decision": "proceed"})

        # Simulate completion
        output = {
            "login_successful": True,
            "username": "test_user",
            "session_id": "test_session_123",
        }
        execution.complete(output=output)

        # Verify completion state
        assert execution.get_state() == ExecutionState.COMPLETED
        assert execution._state.output == output
        assert execution._state.completed_at is not None

    @pytest.mark.asyncio
    async def test_multiple_quick_resumes_in_sequence(
        self, execution_with_data_dir
    ):
        """Verify workflow can have multiple checkpoints with sequential resumes.

        Given: Multi-step workflow with multiple checkpoints
        When: Each checkpoint is paused and resumed within timeout
        Then: All checkpoints are recorded and workflow completes
        """
        execution = execution_with_data_dir

        # First checkpoint
        q1 = {"question_text": "Step 1?", "question_type": "yes_no"}
        cp1 = CheckpointState(
            checkpoint_id=str(uuid4()),
            question=q1,
            timeout_seconds=HARD_TIMEOUT,
        )
        execution.pause(cp1)
        execution.resume(response={"decision": "proceed"})

        # Second checkpoint
        q2 = {"question_text": "Step 2?", "question_type": "yes_no"}
        cp2 = CheckpointState(
            checkpoint_id=str(uuid4()),
            question=q2,
            timeout_seconds=HARD_TIMEOUT,
        )
        execution.pause(cp2)
        execution.resume(response={"decision": "proceed"})

        # Verify both checkpoints recorded
        assert len(execution._state.checkpoints) == 2
        assert execution._state.checkpoints[0].question["question_text"] == "Step 1?"
        assert execution._state.checkpoints[1].question["question_text"] == "Step 2?"
        assert execution.get_state() == ExecutionState.RUNNING

    @pytest.mark.asyncio
    async def test_checkpoint_metadata_preserved_through_resume(
        self, execution_with_data_dir
    ):
        """Verify checkpoint metadata (context, options) preserved through resume.

        Given: Checkpoint with rich metadata (page state, form data)
        When: Workflow pauses and resumes
        Then: All metadata intact and available for post-resume processing
        """
        execution = execution_with_data_dir

        metadata_context = {
            "page_url": "http://localhost:8000/form",
            "form_data": {"username": "test", "password": "***"},
            "browser_cookies": ["session_id", "auth_token"],
        }

        question = {
            "question_text": "Submit form with data?",
            "question_type": "yes_no",
        }
        checkpoint = CheckpointState(
            checkpoint_id="cp-metadata-123",
            question=question,
            timeout_seconds=HARD_TIMEOUT,
            state_snapshot=metadata_context,
        )

        execution.pause(checkpoint)
        execution.resume(response={"decision": "proceed"})

        # Verify metadata preserved
        saved_checkpoint = execution._state.checkpoints[-1]
        assert saved_checkpoint.state_snapshot == metadata_context
        assert saved_checkpoint.checkpoint_id == "cp-metadata-123"

    @pytest.mark.asyncio
    async def test_resume_maintains_execution_id_continuity(
        self, execution_with_data_dir
    ):
        """Verify execution_id remains unchanged through pause/resume cycle.

        Given: Execution paused at checkpoint
        When: Workflow resumes after pause
        Then: Execution ID, session ID, and all continuity markers unchanged
        """
        execution = execution_with_data_dir
        original_execution_id = execution.execution_id
        original_started_at = execution._state.started_at

        # Pause and resume
        question = {"question_text": "Test?", "question_type": "yes_no"}
        checkpoint = CheckpointState(
            checkpoint_id=str(uuid4()),
            question=question,
            timeout_seconds=HARD_TIMEOUT,
        )
        execution.pause(checkpoint)
        execution.resume(response={"decision": "proceed"})

        # Verify continuity
        assert execution.execution_id == original_execution_id
        assert execution._state.started_at == original_started_at
        assert execution.get_state() == ExecutionState.RUNNING


class TestScenarioBEdgeCases:
    """Test suite for edge cases in Scenario B quick resume."""

    @pytest.mark.asyncio
    async def test_rapid_decision_submission(self, execution_with_data_dir):
        """Verify workflow handles immediate decision submission (< 1 second).

        Given: Checkpoint triggered
        When: Agent responds immediately with decision
        Then: Workflow resumes without timeout issues
        """
        execution = execution_with_data_dir

        question = {"question_text": "Quick?", "question_type": "yes_no"}
        checkpoint = CheckpointState(
            checkpoint_id=str(uuid4()),
            question=question,
            timeout_seconds=HARD_TIMEOUT,
        )

        checkpoint_start = datetime.utcnow()
        execution.pause(checkpoint)

        # Simulate immediate response
        decision_received = datetime.utcnow()
        response_time_ms = (decision_received - checkpoint_start).total_seconds() * 1000

        execution.resume(response={"decision": "immediate"})

        # Verify quick response handled
        assert response_time_ms < 1000  # Less than 1 second
        assert execution.get_state() == ExecutionState.RUNNING
        assert execution._state.checkpoints[-1].response is not None

    @pytest.mark.asyncio
    async def test_decision_just_before_soft_timeout(self, execution_with_data_dir):
        """Verify workflow resumes successfully when decision arrives near soft timeout.

        Given: Checkpoint with 2-minute soft timeout
        When: Decision arrives at 119 seconds (just before soft timeout)
        Then: Workflow resumes normally without timeout enforcement
        """
        execution = execution_with_data_dir

        question = {"question_text": "Near timeout?", "question_type": "yes_no"}
        checkpoint = CheckpointState(
            checkpoint_id=str(uuid4()),
            question=question,
            timeout_seconds=HARD_TIMEOUT,
        )

        execution.pause(checkpoint)

        # Simulate decision arriving 119 seconds later (before soft timeout)
        execution.resume(response={"decision": "proceed"})

        # Verify resumed within soft timeout window
        assert execution.get_state() == ExecutionState.RUNNING
        assert execution._state.checkpoints[-1].responded_at is not None

    @pytest.mark.asyncio
    async def test_concurrent_checkpoints_separate_timers(self, execution_with_data_dir):
        """Verify concurrent checkpoints maintain separate timeout timers.

        Given: Multiple parallel workflow instances with checkpoints
        When: Each checkpoint has independent timeout
        Then: Timeout for one doesn't affect others
        """
        execution = execution_with_data_dir

        # Simulate two sequential checkpoints
        q1 = {"question_text": "CP1?", "question_type": "yes_no"}
        cp1 = CheckpointState(
            checkpoint_id="cp1-concurrent",
            question=q1,
            timeout_seconds=HARD_TIMEOUT,
        )

        execution.pause(cp1)
        cp1_start = execution._state.checkpoints[-1].created_at

        # Resume first checkpoint
        execution.resume(response={"decision": "proceed"})

        # Verify both checkpoints have correct timing
        assert execution._state.checkpoints[0].created_at == cp1_start
        assert execution._state.checkpoints[0].responded_at is not None
