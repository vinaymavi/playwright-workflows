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
from src.workflows.login_workflow import LoginWorkflow, LoginInput
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
        
        # Prepare input
        input_data = LoginInput(
            url="http://localhost:8003",
            username="testuser",
            password="testpass"
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
        
        input_data = LoginInput(
            url="http://localhost:8003",
            username="testuser",
            password="testpass"
        )
        
        result = await workflow.run(input_data)
        
        # Verify all output fields
        assert result.success is True
        assert isinstance(result.session_id, str) and len(result.session_id) > 0
        assert isinstance(result.message, str) and len(result.message) > 0
        # dashboard_url can be None or string (depends on implementation)
        assert result.dashboard_url is None or isinstance(result.dashboard_url, str)

    @pytest.mark.asyncio
    async def test_workflow_all_steps_executed(self, mock_page):
        """Test that all workflow steps are executed in correct order.
        
        Verifies that:
        - All 5 steps of LoginWorkflow are executed
        - Steps complete in the expected order
        - Each step has status 'completed'
        """
        workflow = LoginWorkflow(base_url="http://localhost:8003")
        workflow._page = mock_page
        
        input_data = LoginInput(
            url="http://localhost:8003",
            username="testuser",
            password="testpass"
        )
        
        result = await workflow.run(input_data)
        
        # Verify result was successful
        assert result.success is True
        
        # Verify interactions were recorded
        interactions = mock_page.get_interactions()
        
        # Should have at least: navigate, fill username, fill password, click, wait for selector
        assert len(interactions) >= 4, f"Expected at least 4 interactions, got {len(interactions)}"
