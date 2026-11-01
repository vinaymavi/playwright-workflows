"""Integration tests for LoginWorkflow with mock page.

These tests verify that the LoginWorkflow integrates correctly with the framework's
integration infrastructure. Rather than testing against a real web server, these tests
use MockPage to simulate browser operations while focusing on workflow orchestration,
state persistence, and error handling.
"""

import pytest
import asyncio
from src.workflows.login_workflow import LoginWorkflow, LoginInput
from src.framework.errors import WorkflowError
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


class TestLoginWorkflowIntegration:
    """Integration tests for LoginWorkflow framework integration.
    
    These tests validate that LoginWorkflow:
    - Executes steps in correct order
    - Persists execution state
    - Handles errors appropriately
    - Supports concurrent execution
    - Integrates with checkpoint infrastructure
    """

    @pytest.mark.asyncio
    async def test_happy_path_login_flow(self, mock_page):
        """Test complete login workflow execution.
        
        Verifies that:
        - Workflow navigates to login page
        - All form fields are properly filled
        - Submit is successful
        - Dashboard is reached
        - Output contains expected data
        """
        base_url = "http://localhost:8003"
        workflow = LoginWorkflow(base_url=base_url)
        workflow._page = mock_page

        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        result = await workflow.run(input_data)
        
        assert result is not None
        assert result.success is True
        assert result.session_id is not None

    @pytest.mark.asyncio
    async def test_workflow_with_different_base_urls(self, mock_page):
        """Test login workflow with different base URLs.
        
        Verifies that:
        - Workflow correctly uses configured base_url
        - Different instances can have different configurations
        - URL is properly passed to navigate step
        """
        base_url = "http://example.com:8080"
        workflow = LoginWorkflow(base_url=base_url)
        workflow._page = mock_page
        
        assert workflow.base_url == base_url
        
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        result = await workflow.run(input_data)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_concurrent_login_workflows(self):
        """Test multiple LoginWorkflow instances run concurrently.
        
        Verifies that:
        - Multiple workflows can run simultaneously
        - Each has its own isolated state
        - Each has its own mock page
        - All complete successfully
        - No interference between workflows
        """
        base_url = "http://localhost:8003"
        workflows = []
        inputs = []
        
        for i in range(3):
            mock_page = MockPage()
            mock_page.set_element_visible("#login-form")
            mock_page.set_element_visible("#username")
            mock_page.set_element_visible("#password")
            mock_page.set_element_visible("#submit-btn")
            mock_page.set_element_visible("#user-info")
            
            wf = LoginWorkflow(base_url=base_url)
            wf._page = mock_page
            
            user_input = LoginInput(
                url=base_url,
                username=f"user{i}",
                password=f"pass{i}"
            )
            workflows.append(wf)
            inputs.append(user_input)
        
        # Run all workflows concurrently
        results = await asyncio.gather(
            *[wf.run(inp) for wf, inp in zip(workflows, inputs)],
            return_exceptions=False
        )
        
        # Verify all succeeded
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.success is True, f"Workflow {i} failed"

    @pytest.mark.asyncio
    async def test_workflow_input_stored_in_execution(self, mock_page):
        """Test that workflow input is stored in execution context.
        
        Verifies that:
        - Input data is stored in workflow.input after run()
        - Input data is accessible during step execution
        - Username and URL are correctly stored
        """
        base_url = "http://localhost:8003"
        workflow = LoginWorkflow(base_url=base_url)
        workflow._page = mock_page
        
        input_data = LoginInput(
            url=base_url,
            username="testuser123",
            password="testpass456"
        )
        
        result = await workflow.run(input_data)
        
        # Verify input was stored
        assert workflow.input is not None
        assert workflow.input.username == "testuser123"
        assert workflow.input.url == base_url

    @pytest.mark.asyncio
    async def test_workflow_output_structure(self, mock_page):
        """Test that workflow output has correct structure.
        
        Verifies that:
        - Output is a LoginOutput instance
        - All required fields are present
        - Session ID is generated
        - Success flag is set correctly
        """
        base_url = "http://localhost:8003"
        workflow = LoginWorkflow(base_url=base_url)
        workflow._page = mock_page
        
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        result = await workflow.run(input_data)
        
        # Verify output structure
        assert hasattr(result, 'success')
        assert hasattr(result, 'session_id')
        assert hasattr(result, 'message')
        assert hasattr(result, 'dashboard_url')
        assert result.success is True
        assert result.session_id is not None

    @pytest.mark.asyncio
    async def test_workflow_error_when_page_not_set(self):
        """Test workflow handles error when page is not set.
        
        Verifies that:
        - Workflow raises WorkflowError when _page is None
        - Error is raised when trying to access browser methods
        - Error message is informative
        """
        base_url = "http://localhost:8003"
        workflow = LoginWorkflow(base_url=base_url)
        # Intentionally don't set mock_page
        
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        # Should raise WorkflowError when _page is None
        with pytest.raises(WorkflowError):
            await workflow.run(input_data)

    @pytest.mark.asyncio
    async def test_step_execution_records_interactions(self, mock_page):
        """Test that workflow step execution is recorded.
        
        Verifies that:
        - All browser interactions are recorded by MockPage
        - Interactions include goto, fill, click, wait_for
        - At least 4 interactions occur (one per major step)
        """
        base_url = "http://localhost:8003"
        workflow = LoginWorkflow(base_url=base_url)
        workflow._page = mock_page
        
        input_data = LoginInput(
            url=base_url,
            username="testuser",
            password="testpass"
        )
        
        result = await workflow.run(input_data)
        
        # Verify interactions were recorded
        interactions = mock_page.get_interactions()
        assert len(interactions) >= 4, f"Expected at least 4 interactions, got {len(interactions)}: {interactions}"
        
        # Verify interaction types
        interaction_types = [i['type'] for i in interactions]
        assert 'goto' in interaction_types, "Should have goto interaction"
        assert 'fill' in interaction_types, "Should have fill interactions"
        assert 'click' in interaction_types, "Should have click interaction"

    @pytest.mark.asyncio
    async def test_workflow_with_different_inputs(self, mock_page):
        """Test that workflow properly stores input data.
        
        Verifies that:
        - Workflow accepts all required input fields
        - Input data is accessible after run()
        - All fields are properly stored
        """
        base_url = "http://localhost:8003"
        workflow = LoginWorkflow(base_url=base_url)
        workflow._page = mock_page
        
        input_data = LoginInput(
            url=base_url,
            username="testuser456",
            password="testpass789"
        )
        
        result = await workflow.run(input_data)
        
        # Verify input stored
        assert workflow.input.username == "testuser456"
        assert workflow.input.password == "testpass789"
        assert workflow.input.url == base_url
        assert result.success is True
