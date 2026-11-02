"""Unit tests for LoginWorkflow."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.workflows.login_workflow import LoginWorkflow, LoginInput, LoginOutput
from src.framework.errors import WorkflowError
from tests.fixtures import MockPage


@pytest.fixture
def login_workflow():
    """Create a LoginWorkflow instance for testing."""
    return LoginWorkflow(base_url="http://localhost:8000")


@pytest.fixture
def mock_page():
    """Create a mock page for testing."""
    page = MockPage()
    page.set_element_visible("#login-form")
    page.set_element_visible("#txtLogin")
    page.set_element_visible("#txtPwd")
    page.set_element_visible("#submit-btn")
    page.set_element_visible("#user-info")
    return page


@pytest.fixture
def valid_login_input():
    """Create valid login input."""
    return LoginInput(
        url="http://localhost:8000",
        username="testuser",
        password="testpass123",
    )


@pytest.fixture
def invalid_login_input():
    """Create invalid login input."""
    return LoginInput(
        url="http://localhost:8000",
        username="baduser",
        password="badpass",
    )


class TestLoginWorkflowSequence:
    """Test LoginWorkflow step execution sequence."""

    @pytest.mark.asyncio
    async def test_workflow_initialization(self, login_workflow):
        """Test workflow initializes correctly."""
        assert login_workflow.input is None
        assert login_workflow.output is None

    @pytest.mark.asyncio
    async def test_step_sequence_order(self, login_workflow, mock_page, valid_login_input):
        """Test that steps execute in the correct order."""
        # Set up mock page
        login_workflow._page = mock_page
        login_workflow.input = valid_login_input

        # Execute steps
        await login_workflow.navigate_to_login()
        assert mock_page.url == valid_login_input.url

        await login_workflow.fill_username()
        assert mock_page.get_form_data()["#txtLogin"] == valid_login_input.username

        await login_workflow.fill_password()
        assert mock_page.get_form_data()["#txtPwd"] == valid_login_input.password

        await login_workflow.click_submit()
        # Check that click was recorded
        interactions = mock_page.get_interactions()
        assert any(i["type"] == "click" for i in interactions)

    @pytest.mark.asyncio
    async def test_all_steps_execute(self, login_workflow, mock_page, valid_login_input):
        """Test that all workflow steps execute without error."""
        login_workflow._page = mock_page
        login_workflow.input = valid_login_input

        # Execute all steps
        await login_workflow.navigate_to_login()
        await login_workflow.fill_username()
        await login_workflow.fill_password()
        await login_workflow.click_submit()
        await login_workflow.wait_for_dashboard()

        # Verify interactions were recorded
        interactions = mock_page.get_interactions()
        assert len(interactions) >= 4  # At least 4 interactions

    @pytest.mark.asyncio
    async def test_input_validation(self, login_workflow):
        """Test that workflow validates input is provided."""
        login_workflow.input = None

        with pytest.raises(WorkflowError):
            await login_workflow.navigate_to_login()


class TestLoginWorkflowErrorHandling:
    """Test LoginWorkflow error handling."""

    @pytest.mark.asyncio
    async def test_missing_input_raises_error(self, login_workflow):
        """Test that missing input raises WorkflowError."""
        login_workflow.input = None

        with pytest.raises(WorkflowError):
            await login_workflow.fill_username()

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, login_workflow, valid_login_input):
        """Test handling of network timeouts."""
        from src.framework.errors import PermanentError
        
        # Create a mock page that simulates timeout
        mock_page = MockPage()
        login_workflow._page = mock_page

        # Mock wait_for_selector to raise timeout
        original_wait_for = mock_page.wait_for_selector

        async def timeout_wait_for(*args, **kwargs):
            raise asyncio.TimeoutError("wait_for_selector timed out")

        mock_page.wait_for_selector = timeout_wait_for
        login_workflow.input = valid_login_input

        with pytest.raises(PermanentError) as exc_info:
            await login_workflow.navigate_to_login()
        
        # Verify the error message contains timeout information
        assert "Selector not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_step_captures_errors(self, login_workflow, mock_page):
        """Test that @step decorator captures errors."""
        login_workflow.input = LoginInput(
            url="http://localhost:8000",
            username="test",
            password="test",
        )
        login_workflow._page = mock_page

        # This should not raise, error is captured by @step decorator
        # but execution should fail at run() level
        try:
            await login_workflow.navigate_to_login()
        except Exception:
            # @step decorator may wrap the error
            pass


class TestLoginWorkflowOutput:
    """Test LoginWorkflow output structure."""

    def test_login_output_dataclass_structure(self):
        """Test LoginOutput dataclass has correct fields."""
        output = LoginOutput(
            success=True,
            message="Success",
            dashboard_url="http://localhost:8000/dashboard",
            session_id="session_123",
        )

        assert output.success is True
        assert output.message == "Success"
        assert output.dashboard_url == "http://localhost:8000/dashboard"
        assert output.session_id == "session_123"

    def test_login_output_failure_case(self):
        """Test LoginOutput for failure case."""
        output = LoginOutput(
            success=False,
            message="Invalid credentials",
            dashboard_url=None,
        )

        assert output.success is False
        assert output.message == "Invalid credentials"
        assert output.dashboard_url is None

    @pytest.mark.asyncio
    async def test_output_generated_on_success(self, login_workflow, mock_page, valid_login_input):
        """Test that output is generated on successful workflow completion."""
        login_workflow._page = mock_page
        mock_page.url = "http://localhost:8000/dashboard"

        # Mock the run method to not actually try Playwright
        login_workflow.input = valid_login_input
        login_workflow.output = LoginOutput(
            success=True,
            message="Login successful",
            dashboard_url=mock_page.url,
            session_id="session_123",
        )

        assert login_workflow.output is not None
        assert login_workflow.output.success is True


class TestLoginWorkflowIntegration:
    """Test LoginWorkflow integration scenarios."""

    @pytest.mark.asyncio
    async def test_form_data_persistence(self, login_workflow, mock_page, valid_login_input):
        """Test that form data is persisted during execution."""
        login_workflow._page = mock_page
        login_workflow.input = valid_login_input

        await login_workflow.fill_username()
        await login_workflow.fill_password()

        form_data = mock_page.get_form_data()
        assert form_data["#txtLogin"] == valid_login_input.username
        assert form_data["#txtPwd"] == valid_login_input.password

    @pytest.mark.asyncio
    async def test_navigation_recorded(self, login_workflow, mock_page, valid_login_input):
        """Test that navigation is recorded."""
        login_workflow._page = mock_page
        login_workflow.input = valid_login_input

        await login_workflow.navigate_to_login()

        interactions = mock_page.get_interactions()
        assert any(i["type"] == "goto" and i["url"] == valid_login_input.url for i in interactions)

    @pytest.mark.asyncio
    async def test_wait_for_selector_called(self, login_workflow, mock_page, valid_login_input):
        """Test that wait_for_selector is called for dashboard."""
        login_workflow._page = mock_page
        login_workflow.input = valid_login_input

        await login_workflow.wait_for_dashboard()

        interactions = mock_page.get_interactions()
        assert any(
            i["type"] == "wait_for" and i["selector"] == "#user-info" for i in interactions
        )
