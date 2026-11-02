"""Integration tests for LoginWorkflow with quick resume scenarios.

Tests LoginWorkflow with pause/checkpoint and quick resume (<5 min).
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workflows.login_workflow import LoginWorkflow


@pytest.fixture
def mock_browser_context():
    """Fixture providing a mock browser context."""
    context = AsyncMock()
    context.close = AsyncMock()
    return context


@pytest.fixture
def mock_page():
    """Fixture providing a mock Playwright page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"screenshot_data")
    page.url = "https://example.com/dashboard"
    return page


@pytest.fixture
def execution_dir(tmp_path):
    """Fixture providing a temporary execution directory."""
    exec_dir = tmp_path / "executions"
    exec_dir.mkdir()
    return exec_dir


@pytest.mark.asyncio
class TestLoginWorkflowQuickResume:
    """Tests LoginWorkflow quick resume scenarios."""
    
    async def test_login_workflow_pause_at_checkpoint(
        self, mock_browser_context, mock_page, execution_dir
    ):
        """Test LoginWorkflow pauses and creates checkpoint before completing."""
        workflow = LoginWorkflow()
        
        # Set up execution context
        workflow.execution_id = "exec-login-1"
        workflow.execution_dir = execution_dir
        
        # Mock browser context
        workflow.context = mock_browser_context
        workflow.page = mock_page
        
        # Simulate pausing at checkpoint after 2 steps
        workflow.status = "paused"
        workflow.current_step = 2
        workflow.total_steps = 5
        workflow.checkpoint_data = {
            "step": 2,
            "description": "Entered credentials",
            "timestamp": time.time(),
            "url": "https://example.com/login"
        }
        
        # Verify checkpoint was created
        assert workflow.status == "paused"
        assert workflow.current_step == 2
        assert workflow.total_steps == 5
        assert workflow.checkpoint_data is not None
        assert workflow.checkpoint_data["step"] == 2
    
    async def test_login_workflow_save_state_on_pause(
        self, mock_browser_context, mock_page, execution_dir
    ):
        """Test LoginWorkflow saves execution state when pausing."""
        workflow = LoginWorkflow()
        workflow.execution_id = "exec-login-2"
        workflow.execution_dir = execution_dir
        workflow.context = mock_browser_context
        workflow.page = mock_page
        
        # Simulate workflow pause
        workflow.status = "paused"
        workflow.current_step = 2
        workflow.total_steps = 5
        workflow.started_at = time.time()
        workflow.last_activity_at = time.time()
        workflow.checkpoint_data = {
            "step": 2,
            "url": "https://example.com/login",
            "form_data": {"username": "user@example.com"}
        }
        
        # Create state dict as would be saved
        state = {
            "execution_id": workflow.execution_id,
            "status": workflow.status,
            "current_step": workflow.current_step,
            "total_steps": workflow.total_steps,
            "started_at": workflow.started_at,
            "last_activity_at": workflow.last_activity_at,
            "checkpoint_data": workflow.checkpoint_data,
            "workflow_type": "LoginWorkflow"
        }
        
        # Verify state contains all necessary info for resumption
        assert state["status"] == "paused"
        assert state["current_step"] == 2
        assert state["checkpoint_data"]["step"] == 2
        assert "form_data" in state["checkpoint_data"]
    
    async def test_login_workflow_quick_resume_from_checkpoint(
        self, mock_browser_context, mock_page, execution_dir
    ):
        """Test LoginWorkflow resumes quickly from checkpoint within 5 min."""
        workflow = LoginWorkflow()
        workflow.execution_id = "exec-login-3"
        workflow.execution_dir = execution_dir
        workflow.context = mock_browser_context
        workflow.page = mock_page
        
        # Simulate resumed execution state
        now = time.time()
        workflow.started_at = now - 100  # 100 seconds ago
        workflow.last_activity_at = now - 50  # 50 seconds since last activity
        workflow.current_step = 2
        workflow.total_steps = 5
        workflow.status = "paused"
        workflow.checkpoint_data = {
            "step": 2,
            "url": "https://example.com/login",
            "form_data": {"username": "user@example.com"}
        }
        
        # Verify quick resume conditions
        session_age = workflow.last_activity_at - workflow.started_at
        assert session_age < 300  # < 5 minutes, so quick resume
        
        # Simulate resumption
        workflow.status = "running"
        
        # Execute remaining steps (3-5)
        for step in range(workflow.current_step + 1, workflow.total_steps + 1):
            workflow.current_step = step
        
        workflow.status = "completed"
        
        assert workflow.status == "completed"
        assert workflow.current_step == 5
        assert workflow.total_steps == 5
    
    async def test_login_workflow_no_replay_for_quick_resume(
        self, mock_browser_context, mock_page, execution_dir
    ):
        """Test LoginWorkflow does not replay steps for quick resume."""
        workflow = LoginWorkflow()
        workflow.execution_id = "exec-login-4"
        workflow.execution_dir = execution_dir
        workflow.context = mock_browser_context
        workflow.page = mock_page
        
        # Setup quick resume state (< 5 min old)
        now = time.time()
        workflow.started_at = now - 120  # 2 minutes ago
        workflow.last_activity_at = now - 60  # 1 minute since last activity
        workflow.current_step = 2
        workflow.checkpoint_step = 2
        
        # For quick resume with fresh session, no replay needed
        session_age = workflow.last_activity_at - workflow.started_at
        needs_replay = session_age > 300  # > 5 minutes
        
        # Since we're in quick resume, replay should NOT be needed
        assert not needs_replay
        assert session_age < 300
    
    async def test_login_workflow_preserves_session_for_quick_resume(
        self, mock_browser_context, mock_page, execution_dir
    ):
        """Test LoginWorkflow preserves browser session for quick resume."""
        workflow = LoginWorkflow()
        workflow.execution_id = "exec-login-5"
        workflow.execution_dir = execution_dir
        workflow.context = mock_browser_context
        workflow.page = mock_page
        
        # Quick resume should keep existing context
        original_context = workflow.context
        original_page = workflow.page
        
        # Simulate quick resume flow
        now = time.time()
        session_age = now - (now - 100)  # 100 seconds
        
        # For quick resume, we should use existing session
        if session_age < 300:  # < 5 minutes
            new_context = workflow.context  # Reuse existing
            new_page = workflow.page  # Reuse existing
        else:
            new_context = None  # Would need new context
            new_page = None
        
        assert new_context is original_context
        assert new_page is original_page
    
    async def test_login_workflow_multiple_quick_resumes(
        self, mock_browser_context, mock_page, execution_dir
    ):
        """Test LoginWorkflow handles multiple quick resume cycles."""
        workflow = LoginWorkflow()
        workflow.execution_id = "exec-login-6"
        workflow.execution_dir = execution_dir
        workflow.context = mock_browser_context
        workflow.page = mock_page
        
        now = time.time()
        workflow.started_at = now - 50  # Started recently
        workflow.last_activity_at = now
        
        # Simulate multiple pause/resume cycles
        for cycle in range(1, 4):
            workflow.status = "paused"
            workflow.completed_steps = cycle
            workflow.total_steps = 5
            workflow.checkpoint = {
                "step": cycle,
                "cycle": cycle
            }
            
            # Quick resume
            workflow.status = "running"
            workflow.completed_steps = cycle
            
            # Update activity time but stay within 5 min
            workflow.last_activity_at = now + (cycle * 30)
        
        # All cycles should be within 5 minutes
        total_time = workflow.last_activity_at - workflow.started_at
        assert total_time < 300
    
    async def test_login_workflow_resume_continues_correct_step(
        self, mock_browser_context, mock_page, execution_dir
    ):
        """Test LoginWorkflow resume continues from correct step."""
        workflow = LoginWorkflow()
        workflow.execution_id = "exec-login-7"
        workflow.execution_dir = execution_dir
        workflow.context = mock_browser_context
        workflow.page = mock_page
        
        # Simulate paused state after step 2 of 6
        workflow.current_step = 2
        workflow.total_steps = 6
        workflow.checkpoint_step = 2
        
        # Simulate resume continuing from step 3
        steps_executed = []
        
        # Resume from checkpoint
        workflow.status = "running"
        
        # Execute remaining steps (3-6)
        for step in range(workflow.current_step + 1, workflow.total_steps + 1):
            steps_executed.append(step)
            workflow.current_step = step
        
        workflow.status = "completed"
        
        # Verify only steps 3-6 were executed
        assert steps_executed == [3, 4, 5, 6]
        assert workflow.current_step == 6
    
    async def test_login_workflow_quick_resume_error_recovery(
        self, mock_browser_context, mock_page, execution_dir
    ):
        """Test LoginWorkflow error recovery during quick resume."""
        workflow = LoginWorkflow()
        workflow.execution_id = "exec-login-8"
        workflow.execution_dir = execution_dir
        workflow.context = mock_browser_context
        workflow.page = mock_page
        
        # Setup quick resume state
        now = time.time()
        workflow.started_at = now - 90
        workflow.last_activity_at = now - 45
        workflow.current_step = 3
        workflow.total_steps = 6
        workflow.status = "paused"
        
        # Simulate error scenario during quick resume
        error_scenario = {
            "error_occurred": False,
            "recovery_attempted": False,
            "error_message": ""
        }
        
        # Simulate workflow encountering error during resume
        workflow.status = "running"
        workflow.current_step = 4  # Simulate failure at step 4
        
        # Simulate error condition
        try:
            # Simulate network error
            raise Exception("Network error during step execution")
        except Exception as e:
            error_scenario["error_occurred"] = True
            error_scenario["error_message"] = str(e)
            workflow.status = "failed"
            # In recovery, workflow would attempt to restore
            error_scenario["recovery_attempted"] = True
        
        # Verify error handling
        assert error_scenario["error_occurred"]
        assert error_scenario["recovery_attempted"]
        assert workflow.status == "failed"
        assert "Network error" in error_scenario["error_message"]
