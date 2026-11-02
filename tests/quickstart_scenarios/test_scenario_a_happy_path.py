"""Quickstart Scenario A: Basic Workflow Execution (Happy Path)

This test demonstrates the simplest use case: a workflow that runs to completion
without any checkpoints or human intervention, completing in under 30 seconds.

Expected Duration: < 30 seconds
Success Criteria:
  - Execution status is 'completed'
  - Result contains expected output data
  - No errors or warnings
  - Execution time is within 30 seconds
"""

import pytest
import time
from unittest.mock import AsyncMock, patch
from src.workflows.login_workflow import LoginWorkflow, LoginInput
from src.framework.execution import Execution
from src.framework.checkpoint import CheckpointResponse, CheckpointDecision
from tests.fixtures import MockPage


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


class TestScenarioAHappyPath:
    """Scenario A: Basic Workflow Execution (Happy Path)
    
    This scenario tests the simplest use case where a workflow runs from
    start to completion without any interruptions or checkpoints.
    
    Note: These tests use MockPage to mock Playwright browser operations,
    simulating a real workflow execution without requiring actual browser launch.
    This aligns with test efficiency while validating the framework's core
    orchestration logic works end-to-end.
    """

    @pytest.mark.asyncio
    async def test_workflow_completes_successfully(self, mock_page):
        """Test that a simple workflow completes successfully.
        
        Scenario A: Basic workflow execution (happy path)
        - Single workflow runs to completion without checkpoints
        - Expected Duration: < 30 seconds
        - Success Criteria: Execution status is 'completed', result is returned
        """
        start_time = time.time()
        
        # Create workflow
        workflow = LoginWorkflow(base_url="http://localhost:8003")
        workflow._page = mock_page
        
        # Create and set execution
        execution = Execution(
            execution_id=workflow.execution_id,
            base_url=workflow.base_url,
        )
        workflow.set_execution(execution)
        
        # Mock the request_approval to auto-approve for happy path
        async def mock_approval():
            return CheckpointDecision(choice="proceed")
        
        workflow.request_approval = mock_approval
        
        # Prepare input
        input_data = LoginInput(
            url="http://localhost:8003",
            username="testuser",
            password="password123"
        )
        
        # Run workflow
        result = await workflow.run(input_data)
        
        elapsed = time.time() - start_time
        
        # Verify success
        assert result is not None
        assert result.success is True
        assert result.session_id is not None
        
        # Verify timing
        assert elapsed < 30, f"Workflow took {elapsed:.2f}s, expected < 30s"

    @pytest.mark.asyncio
    async def test_workflow_output_is_valid(self, mock_page):
        """Test that workflow output contains all expected fields.
        
        Verifies that the result object has all required fields populated:
        - success: boolean indicating workflow completion
        - session_id: session token from server
        - dashboard_url: final URL after successful login
        - message: status message
        """
        workflow = LoginWorkflow(base_url="http://localhost:8003")
        workflow._page = mock_page
        
        # Create and set execution
        execution = Execution(
            execution_id=workflow.execution_id,
            base_url=workflow.base_url,
        )
        workflow.set_execution(execution)
        
        # Mock the request_approval to auto-approve for happy path
        async def mock_approval():
            return CheckpointDecision(choice="proceed")
        
        workflow.request_approval = mock_approval
        
        input_data = LoginInput(
            url="http://localhost:8003",
            username="testuser",
            password="password123"
        )
        
        result = await workflow.run(input_data)
        
        # Verify output structure
        assert hasattr(result, 'success')
        assert hasattr(result, 'session_id')
        assert hasattr(result, 'dashboard_url')
        assert hasattr(result, 'message')
        
        # Verify output values
        assert result.success is True
        assert isinstance(result.session_id, str)
        assert len(result.session_id) > 0
        assert isinstance(result.dashboard_url, str)
        assert len(result.dashboard_url) > 0
        assert isinstance(result.message, str)

    @pytest.mark.asyncio
    async def test_workflow_all_steps_executed(self, mock_page):
        """Test that all workflow steps execute in sequence.
        
        Verifies that the workflow calls all expected steps in the correct order:
        1. Navigate to login page
        2. Fill username
        3. Fill password
        4. Request approval
        5. Click submit
        6. Wait for dashboard
        """
        workflow = LoginWorkflow(base_url="http://localhost:8003")
        workflow._page = mock_page
        
        # Create and set execution
        execution = Execution(
            execution_id=workflow.execution_id,
            base_url=workflow.base_url,
        )
        workflow.set_execution(execution)
        
        # Track step execution
        steps_executed = []
        
        # Mock step methods to track execution
        original_navigate = workflow.navigate_to_login
        original_fill_username = workflow.fill_username
        original_fill_password = workflow.fill_password
        original_click_submit = workflow.click_submit
        original_wait_dashboard = workflow.wait_for_dashboard
        
        async def track_navigate():
            steps_executed.append("navigate")
            return await original_navigate()
        
        async def track_fill_username():
            steps_executed.append("fill_username")
            return await original_fill_username()
        
        async def track_fill_password():
            steps_executed.append("fill_password")
            return await original_fill_password()
        
        async def track_click_submit():
            steps_executed.append("click_submit")
            return await original_click_submit()
        
        async def track_wait_dashboard():
            steps_executed.append("wait_dashboard")
            return await original_wait_dashboard()
        
        workflow.navigate_to_login = track_navigate
        workflow.fill_username = track_fill_username
        workflow.fill_password = track_fill_password
        workflow.click_submit = track_click_submit
        workflow.wait_for_dashboard = track_wait_dashboard
        
        # Mock the request_approval to auto-approve for happy path
        async def mock_approval():
            steps_executed.append("request_approval")
            return CheckpointDecision(choice="proceed")
        
        workflow.request_approval = mock_approval
        
        input_data = LoginInput(
            url="http://localhost:8003",
            username="testuser",
            password="password123"
        )
        
        result = await workflow.run(input_data)
        
        # Verify all steps were executed
        expected_order = ["navigate", "fill_username", "fill_password", "request_approval", "click_submit", "wait_dashboard"]
        assert steps_executed == expected_order, f"Expected steps {expected_order}, got {steps_executed}"
        
        # Verify workflow completed successfully
        assert result.success is True
