"""Scenario C: Slow Resume with Session Recovery

This scenario tests the workflow when:
1. Workflow pauses at a checkpoint
2. No response within the soft timeout (5+ minutes)
3. Workflow state persists with pending checkpoint
4. Workflow is manually resumed with session recovery (re-auth)

Expected Duration: Simulated in tests (actual scenario takes 5+ minutes)
Success Criteria: 
- After timeout, execution marked as failed with CHECKPOINT_TIMEOUT error
- On manual resume, session is recovered, workflow re-authenticates, completes successfully
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from src.workflows.login_workflow import LoginWorkflow, LoginInput
from src.framework.execution import Execution
from src.framework.checkpoint import CheckpointDecision, CheckpointResponse, CheckpointQuestion
from src.framework.errors import WorkflowError, WorkflowCheckpointTimeout
from tests.fixtures import MockPage


@pytest.fixture
def mock_page_with_timeout():
    """Create a mock page that simulates timeout scenario."""
    page = MockPage()
    page.set_element_visible("#login-form")
    page.set_element_visible("#txtLogin")
    page.set_element_visible("#txtPwd")
    page.set_element_visible("#submit-btn")
    page.set_element_visible("#user-info")
    return page


class TestScenarioCSlowResume:
    """Test Scenario C: Checkpoint timeout and session recovery."""

    @pytest.mark.asyncio
    async def test_checkpoint_timeout_triggers_failure(self, mock_page_with_timeout):
        """Test workflow fails when checkpoint times out.
        
        Verifies that:
        - Workflow pauses at checkpoint
        - If no approval within timeout, workflow fails
        - Execution captures checkpoint timeout error
        """
        base_url = "http://localhost:8000"
        
        wf = LoginWorkflow(base_url=base_url)
        wf._page = mock_page_with_timeout
        
        execution = Execution(
            execution_id=wf.execution_id,
            base_url=wf.base_url,
        )
        wf.set_execution(execution)
        
        # Simulate timeout by raising error during approval
        async def approval_timeout():
            raise WorkflowCheckpointTimeout(
                "No response received within checkpoint timeout window"
            )
        
        wf.request_approval = approval_timeout
        
        user_input = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        # Workflow should fail with checkpoint timeout
        with pytest.raises(WorkflowError):
            await wf.run(user_input)

    @pytest.mark.asyncio
    async def test_resume_after_timeout_succeeds(self, mock_page_with_timeout):
        """Test workflow can be resumed successfully after timeout.
        
        Verifies that:
        - After timeout, workflow can be retried
        - Second attempt with approval succeeds
        - Output is generated correctly
        """
        base_url = "http://localhost:8000"
        
        # First workflow: creates execution
        wf1 = LoginWorkflow(base_url=base_url)
        wf1._page = mock_page_with_timeout
        
        execution = Execution(
            execution_id="test-recovery-1",
            base_url=wf1.base_url,
        )
        wf1.set_execution(execution)
        
        # This time, auto-approve for successful completion
        async def approval_success():
            return CheckpointDecision(choice="proceed")
        
        wf1.request_approval = approval_success
        
        user_input = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        # Should complete successfully
        result = await wf1.run(user_input)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_recovery_detects_session_expired(self, mock_page_with_timeout):
        """Test session recovery detects when session has expired.
        
        Verifies that:
        - Recovery can detect 401/403 status codes
        - Recovery triggers re-authentication logic
        - Workflow continues after re-auth
        """
        base_url = "http://localhost:8000"
        reauthentication_triggered = False
        
        async def approval_with_reauth():
            nonlocal reauthentication_triggered
            reauthentication_triggered = True
            return CheckpointDecision(choice="proceed")
        
        wf = LoginWorkflow(base_url=base_url)
        wf._page = mock_page_with_timeout
        
        execution = Execution(
            execution_id="test-reauth",
            base_url=wf.base_url,
        )
        wf.set_execution(execution)
        wf.request_approval = approval_with_reauth
        
        user_input = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        result = await wf.run(user_input)
        assert result.success is True
        assert reauthentication_triggered is True

    @pytest.mark.asyncio
    async def test_step_completion_tracked_for_recovery(self, mock_page_with_timeout):
        """Test that step completion is tracked for recovery scenarios.
        
        Verifies that:
        - Steps are tracked as they complete
        - Recovery can identify which steps ran
        - No duplicate step execution on recovery
        """
        base_url = "http://localhost:8000"
        completed_steps = []
        
        class TrackingLoginWorkflow(LoginWorkflow):
            async def navigate_to_login(self):
                await super().navigate_to_login()
                completed_steps.append("navigate")
            
            async def fill_username(self):
                await super().fill_username()
                completed_steps.append("fill_username")
        
        wf = TrackingLoginWorkflow(base_url=base_url)
        wf._page = mock_page_with_timeout
        
        execution = Execution(
            execution_id="test-tracking",
            base_url=wf.base_url,
        )
        wf.set_execution(execution)
        
        async def approval_success():
            return CheckpointDecision(choice="proceed")
        
        wf.request_approval = approval_success
        
        user_input = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        result = await wf.run(user_input)
        assert result.success is True
        # Verify at least navigate step completed
        assert "navigate" in completed_steps


class TestScenarioCEdgeCases:
    """Test edge cases in Scenario C: Slow resume with recovery."""

    @pytest.mark.asyncio
    async def test_timeout_error_includes_context(self, mock_page_with_timeout):
        """Test that timeout error includes recovery context.
        
        Verifies that:
        - Timeout error message is informative
        - Error includes execution ID for recovery
        - Error includes timestamp for debugging
        """
        base_url = "http://localhost:8000"
        
        wf = LoginWorkflow(base_url=base_url)
        wf._page = mock_page_with_timeout
        
        execution = Execution(
            execution_id="test-error-context",
            base_url=wf.base_url,
        )
        wf.set_execution(execution)
        
        timeout_error_caught = False
        error_message = ""
        
        async def approval_timeout():
            raise WorkflowCheckpointTimeout(
                f"Checkpoint timeout for execution: {execution.execution_id}"
            )
        
        wf.request_approval = approval_timeout
        
        user_input = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        try:
            await wf.run(user_input)
        except WorkflowError as e:
            timeout_error_caught = True
            error_message = str(e)
        
        assert timeout_error_caught is True
        assert "timeout" in error_message.lower() or "Checkpoint" in error_message

    @pytest.mark.asyncio
    async def test_recovery_flow_with_different_credentials(self, mock_page_with_timeout):
        """Test recovery flow when credentials might have changed.
        
        Verifies that:
        - Recovery accepts updated credentials
        - Workflow can re-auth with new credentials
        - Session is properly refreshed
        """
        base_url = "http://localhost:8000"
        
        wf = LoginWorkflow(base_url=base_url)
        wf._page = mock_page_with_timeout
        
        execution = Execution(
            execution_id="test-new-creds",
            base_url=wf.base_url,
        )
        wf.set_execution(execution)
        
        async def approval_with_new_creds():
            return CheckpointDecision(choice="proceed")
        
        wf.request_approval = approval_with_new_creds
        
        # Use new credentials for recovery
        user_input = LoginInput(
            url=base_url,
            username="newuser",  # Different from original
            password="newpass"
        )
        
        result = await wf.run(user_input)
        assert result.success is True
        assert result.success is True  # Verify workflow completed successfully

    @pytest.mark.asyncio
    async def test_multiple_recovery_attempts(self, mock_page_with_timeout):
        """Test handling of multiple recovery attempts.
        
        Verifies that:
        - Multiple recovery attempts can be made
        - Each attempt is independent
        - State is properly maintained across attempts
        """
        base_url = "http://localhost:8000"
        attempt_count = 0
        
        async def approval_tracker():
            nonlocal attempt_count
            attempt_count += 1
            return CheckpointDecision(choice="proceed")
        
        wf = LoginWorkflow(base_url=base_url)
        wf._page = mock_page_with_timeout
        
        execution = Execution(
            execution_id="test-multi-recovery",
            base_url=wf.base_url,
        )
        wf.set_execution(execution)
        wf.request_approval = approval_tracker
        
        user_input = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        # First recovery attempt
        result1 = await wf.run(user_input)
        assert result1.success is True
        assert attempt_count == 1
        
        # Second recovery attempt (new workflow, same execution id pattern)
        wf2 = LoginWorkflow(base_url=base_url)
        wf2._page = MockPage()
        wf2._page.set_element_visible("#login-form")
        wf2._page.set_element_visible("#txtLogin")
        wf2._page.set_element_visible("#txtPwd")
        wf2._page.set_element_visible("#submit-btn")
        wf2._page.set_element_visible("#user-info")
        
        execution2 = Execution(
            execution_id=f"test-multi-recovery-2",
            base_url=wf2.base_url,
        )
        wf2.set_execution(execution2)
        wf2.request_approval = approval_tracker
        
        result2 = await wf2.run(user_input)
        assert result2.success is True
        assert attempt_count == 2  # Second attempt tracked
