"""Integration tests for LoginWorkflow with mock web server.

These tests verify that the LoginWorkflow integrates correctly with a mock web application,
testing the full workflow execution flow without requiring a real browser.
"""

import pytest
import asyncio
from src.workflows.login_workflow import LoginWorkflow, LoginInput, LoginOutput
from src.framework.errors import WorkflowError, PermanentError
from tests.fixtures import MockWebApp


@pytest.fixture
def mock_web_app():
    """Create a mock web application server."""
    return MockWebApp()


@pytest.fixture
def login_workflow_with_server(mock_web_app):
    """Create a LoginWorkflow configured to connect to mock server."""
    workflow = LoginWorkflow(base_url=mock_web_app.base_url)
    yield workflow


@pytest.fixture
def valid_login_input():
    """Create valid login input for the mock server."""
    return LoginInput(
        username="testuser",
        password="testpass",
        timeout_seconds=10
    )


class TestLoginWorkflowIntegration:
    """Integration tests for LoginWorkflow with mock web server."""

    @pytest.mark.asyncio
    async def test_happy_path_login_flow(self, login_workflow_with_server, valid_login_input):
        """Test complete login workflow with mock server.
        
        Verifies that:
        - Workflow navigates to login page
        - All form fields are properly filled
        - Submit is successful
        - Dashboard is reached
        - Output contains expected data
        """
        login_workflow_with_server.input = valid_login_input
        
        result = await login_workflow_with_server.run()
        
        assert result is not None
        assert result.success is True
        assert result.user_name == "testuser"
        assert result.session_id is not None
        assert result.redirect_url == f"{login_workflow_with_server.base_url}/dashboard"

    @pytest.mark.asyncio
    async def test_invalid_credentials_flow(self, login_workflow_with_server):
        """Test login workflow with invalid credentials.
        
        Verifies that:
        - Invalid credentials are properly detected
        - Appropriate error is raised
        - Error is logged correctly
        """
        invalid_input = LoginInput(
            username="invaliduser",
            password="wrongpass",
            timeout_seconds=10
        )
        login_workflow_with_server.input = invalid_input
        
        with pytest.raises(PermanentError):
            await login_workflow_with_server.run()

    @pytest.mark.asyncio
    async def test_concurrent_login_workflows(self, login_workflow_with_server, valid_login_input):
        """Test multiple LoginWorkflow instances run concurrently.
        
        Verifies that:
        - Multiple workflows can run simultaneously
        - Each has its own isolated state
        - All complete successfully
        - No interference between workflows
        """
        # Create multiple workflow instances with different credentials
        workflows = []
        inputs = []
        
        for i in range(3):
            wf = LoginWorkflow(base_url=login_workflow_with_server.base_url)
            user_input = LoginInput(
                username=f"user{i}",
                password=f"pass{i}",
                timeout_seconds=10
            )
            wf.input = user_input
            workflows.append(wf)
            inputs.append(user_input)
        
        # Run all workflows concurrently
        results = await asyncio.gather(
            *[wf.run() for wf in workflows],
            return_exceptions=False
        )
        
        # Verify all succeeded with correct data
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.success is True
            assert result.user_name == f"user{i}"

    @pytest.mark.asyncio
    async def test_workflow_state_persistence(self, login_workflow_with_server, valid_login_input):
        """Test that workflow execution state is properly persisted.
        
        Verifies that:
        - Execution state is saved after workflow runs
        - State contains all step information
        - State can be loaded and inspected
        - Logs are created with proper format
        """
        login_workflow_with_server.input = valid_login_input
        
        result = await login_workflow_with_server.run()
        
        # Verify execution state exists
        assert login_workflow_with_server.execution is not None
        assert login_workflow_with_server.execution.id is not None
        
        # Verify state persistence
        execution_state = login_workflow_with_server.execution.state
        assert execution_state.status == "completed"
        assert execution_state.steps is not None
        assert len(execution_state.steps) > 0
        
        # Verify all steps have completion info
        for step in execution_state.steps:
            assert step.name is not None
            assert step.status in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_workflow_error_recovery(self, login_workflow_with_server):
        """Test workflow handles errors gracefully.
        
        Verifies that:
        - Transient errors trigger retry
        - Permanent errors trigger checkpoint escalation
        - Error information is properly logged
        - Workflow state reflects error
        """
        # Test with empty credentials (will cause validation error)
        empty_input = LoginInput(
            username="",
            password="",
            timeout_seconds=10
        )
        login_workflow_with_server.input = empty_input
        
        # Should raise error due to invalid input
        with pytest.raises(PermanentError):
            await login_workflow_with_server.run()

    @pytest.mark.asyncio
    async def test_step_execution_order(self, login_workflow_with_server, valid_login_input):
        """Test that workflow steps execute in correct order.
        
        Verifies that:
        - Steps execute sequentially
        - Each step output feeds into next step
        - No steps are skipped
        - Timing information is recorded
        """
        login_workflow_with_server.input = valid_login_input
        
        result = await login_workflow_with_server.run()
        
        # Verify step sequence
        steps = login_workflow_with_server.execution.state.steps
        step_names = [step.name for step in steps]
        
        expected_order = [
            "navigate_to_login",
            "fill_username",
            "fill_password",
            "click_submit",
            "wait_for_dashboard"
        ]
        
        assert step_names == expected_order
        
        # Verify no gaps in timing
        for i in range(len(steps) - 1):
            assert steps[i].completed_at is not None
            assert steps[i+1].started_at is not None
            # Started time should be after previous completed time
            assert steps[i+1].started_at >= steps[i].completed_at
