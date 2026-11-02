"""Integration tests for FormFillingWorkflow using custom actions."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from src.workflows.form_filling_workflow import (
    FormFillingWorkflow,
    FormFillingInput,
    FormField,
)
from src.framework.errors import WorkflowError
from src.framework.action_registry import ActionRegistry


@pytest.fixture
def mock_page():
    """Create a mock Playwright page object."""
    page = AsyncMock()
    page.url = "http://localhost:8000/form"
    page.goto = AsyncMock()
    page.locator = MagicMock(return_value=AsyncMock())
    page.wait_for_selector = AsyncMock()

    # Mock locator chain for various selectors
    def locator_side_effect(selector):
        locator = MagicMock()
        locator.first = MagicMock()
        locator.first.text_content = AsyncMock(return_value="field_value")
        locator.fill = AsyncMock()
        locator.click = AsyncMock()
        locator.check = AsyncMock()
        locator.is_visible = AsyncMock(return_value=True)
        locator.is_enabled = AsyncMock(return_value=True)
        return locator

    page.locator.side_effect = locator_side_effect
    return page


@pytest.fixture
def workflow(mock_page):
    """Create a FormFillingWorkflow instance with mock page."""
    workflow = FormFillingWorkflow(execution_id="test-exec-001")
    workflow._page = mock_page
    return workflow


@pytest.fixture
def action_registry():
    """Create and populate action registry with mock actions."""
    from src.framework.action import Action

    registry = ActionRegistry()

    # Mock FillFormAction
    class MockFillFormAction(Action):
        async def execute(self, **kwargs):
            return {
                "status": "success",
                "fields_filled": 3,
                "message": "Form fields filled successfully",
            }

    # Mock ClickElementAction
    class MockClickElementAction(Action):
        async def execute(self, **kwargs):
            return {"status": "success", "element_clicked": True}

    # Mock CheckCheckboxAction
    class MockCheckCheckboxAction(Action):
        async def execute(self, **kwargs):
            return {"status": "success", "checkbox_checked": True}

    # Register mock actions
    registry.register(MockFillFormAction, name="FillFormAction")
    registry.register(MockClickElementAction, name="ClickElementAction")
    registry.register(MockCheckCheckboxAction, name="CheckCheckboxAction")

    return registry


class TestFormFillingWorkflow:
    """Test FormFillingWorkflow with custom actions."""

    @pytest.mark.asyncio
    async def test_form_filling_workflow_success(self, workflow, action_registry):
        """Test successful form filling and submission workflow."""
        # Setup
        workflow.action_registry = action_registry

        input_data = FormFillingInput(
            url="http://localhost:8000/form",
            form_selector="#form-container",
            fields=[
                FormField(selector="#username", value="testuser", field_type="text"),
                FormField(selector="#email", value="test@example.com", field_type="email"),
                FormField(selector="#terms", value="on", field_type="checkbox"),
            ],
            submit_button_selector="#submit-btn",
            wait_for_element="#success-message",
            verify_url_contains="/success",
        )

        # Mock the checkpoint to return proceed
        workflow.checkpoint = AsyncMock(
            return_value=MagicMock(
                decision=MagicMock(choice="proceed")
            )
        )
        # Set _execution to avoid skipping checkpoint
        workflow._execution = MagicMock()

        # Update page URL to reflect successful submission
        workflow._page.url = "http://localhost:8000/success"

        # Execute workflow
        output = await workflow.run(input_data)

        # Assertions
        assert output.success is True
        assert output.message == "Form filled and submitted successfully"
        assert output.verification_result is not None
        assert output.verification_result.get("url_verified") is True
        assert output.verification_result.get("element_found") is True

    @pytest.mark.asyncio
    async def test_form_filling_workflow_agent_cancellation(
        self, workflow, action_registry
    ):
        """Test workflow handling agent cancellation at checkpoint."""
        # Setup
        workflow.action_registry = action_registry

        input_data = FormFillingInput(
            url="http://localhost:8000/form",
            form_selector="#form-container",
            fields=[
                FormField(selector="#username", value="testuser", field_type="text"),
            ],
            submit_button_selector="#submit-btn",
        )

        # Mock checkpoint to return cancel
        workflow.checkpoint = AsyncMock(
            return_value=MagicMock(
                decision=MagicMock(choice="cancel")
            )
        )
        # Set _execution to process checkpoint
        workflow._execution = MagicMock()

        # Execute workflow and expect error
        with pytest.raises(WorkflowError) as exc_info:
            await workflow.run(input_data)

        assert "Form submission cancelled by agent" in str(exc_info.value)
        assert workflow.output.success is False

    @pytest.mark.asyncio
    async def test_form_filling_workflow_missing_input(self, workflow):
        """Test workflow error handling when input not provided."""
        # Execute without providing input
        with pytest.raises(WorkflowError) as exc_info:
            await workflow.run(None)  # type: ignore

        assert "Input not provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_form_filling_workflow_navigate_failure(self, workflow, action_registry):
        """Test workflow handling navigation errors."""
        # Setup
        workflow.action_registry = action_registry

        input_data = FormFillingInput(
            url="http://localhost:8000/form",
            form_selector="#form-container",
            fields=[],
            submit_button_selector="#submit-btn",
        )

        # Mock navigation to fail
        workflow._page.goto = AsyncMock(
            side_effect=Exception("Navigation failed")
        )

        # Execute workflow and expect error
        with pytest.raises(WorkflowError) as exc_info:
            await workflow.run(input_data)

        assert "Form filling workflow failed" in str(exc_info.value)
        assert workflow.output.success is False

    @pytest.mark.asyncio
    async def test_form_filling_workflow_verification_url_mismatch(
        self, workflow, action_registry
    ):
        """Test workflow error handling for URL verification failure."""
        # Setup
        workflow.action_registry = action_registry

        input_data = FormFillingInput(
            url="http://localhost:8000/form",
            form_selector="#form-container",
            fields=[
                FormField(selector="#username", value="testuser", field_type="text"),
            ],
            submit_button_selector="#submit-btn",
            verify_url_contains="/success",
        )

        # Mock checkpoint to return proceed
        workflow.checkpoint = AsyncMock(
            return_value=MagicMock(
                decision=MagicMock(choice="proceed")
            )
        )
        workflow._execution = MagicMock()

        # URL remains at form page (doesn't contain /success)
        workflow._page.url = "http://localhost:8000/form"

        # Execute workflow and expect error
        with pytest.raises(WorkflowError) as exc_info:
            await workflow.run(input_data)

        assert "URL verification failed" in str(exc_info.value)
        assert workflow.output.success is False

    @pytest.mark.asyncio
    async def test_form_filling_workflow_invalid_checkpoint_decision(
        self, workflow, action_registry
    ):
        """Test workflow error handling for invalid checkpoint decision."""
        # Setup
        workflow.action_registry = action_registry

        input_data = FormFillingInput(
            url="http://localhost:8000/form",
            form_selector="#form-container",
            fields=[
                FormField(selector="#field1", value="value1", field_type="text"),
            ],
            submit_button_selector="#submit-btn",
        )

        # Mock checkpoint to return invalid decision
        workflow.checkpoint = AsyncMock(
            return_value=MagicMock(
                decision=MagicMock(choice="invalid_choice")
            )
        )
        workflow._execution = MagicMock()
        workflow._page.url = "http://localhost:8000/form"

        # Execute workflow and expect error
        with pytest.raises(WorkflowError) as exc_info:
            await workflow.run(input_data)

        assert "Invalid checkpoint decision" in str(exc_info.value)
        assert workflow.output.success is False

    @pytest.mark.asyncio
    async def test_form_filling_workflow_multiple_fields(
        self, workflow, action_registry
    ):
        """Test form filling with multiple field types."""
        # Setup
        workflow.action_registry = action_registry

        input_data = FormFillingInput(
            url="http://localhost:8000/form",
            form_selector="#form-container",
            fields=[
                FormField(selector="#first-name", value="John", field_type="text"),
                FormField(selector="#last-name", value="Doe", field_type="text"),
                FormField(selector="#email", value="john@example.com", field_type="email"),
                FormField(selector="#password", value="secret123", field_type="password"),
                FormField(selector="#newsletter", value="on", field_type="checkbox"),
            ],
            submit_button_selector="#submit-btn",
            wait_for_element="#confirmation-message",
        )

        # Mock checkpoint
        workflow.checkpoint = AsyncMock(
            return_value=MagicMock(
                decision=MagicMock(choice="proceed")
            )
        )
        workflow._execution = MagicMock()
        workflow._page.url = "http://localhost:8000/confirmation"

        # Execute workflow
        output = await workflow.run(input_data)

        # Assertions
        assert output.success is True
        assert output.message == "Form filled and submitted successfully"
        assert len(input_data.fields) == 5

    @pytest.mark.asyncio
    async def test_form_filling_workflow_without_checkpoint_execution(
        self, workflow, action_registry
    ):
        """Test workflow skips checkpoint when execution not initialized (unit test mode)."""
        # Setup
        workflow.action_registry = action_registry
        # Don't set _execution - should skip checkpoint

        input_data = FormFillingInput(
            url="http://localhost:8000/form",
            form_selector="#form-container",
            fields=[
                FormField(selector="#username", value="testuser", field_type="text"),
            ],
            submit_button_selector="#submit-btn",
            wait_for_element="#success-message",
        )

        # Update page URL
        workflow._page.url = "http://localhost:8000/success"

        # Execute workflow
        output = await workflow.run(input_data)

        # Should succeed (checkpoint was skipped)
        assert output.success is True
        assert output.message == "Form filled and submitted successfully"


class TestFormFillingWorkflowActionIntegration:
    """Test FormFillingWorkflow integration with action framework."""

    @pytest.mark.asyncio
    async def test_workflow_uses_action_registry(self, workflow):
        """Test that workflow can instantiate and use actions from registry."""
        # Verify registry is initialized
        assert workflow.action_registry is not None

        # Verify registry has expected methods
        assert hasattr(workflow.action_registry, "register")
        assert hasattr(workflow.action_registry, "get")
        assert hasattr(workflow.action_registry, "list")

    @pytest.mark.asyncio
    async def test_workflow_action_execution_error_handling(
        self, workflow, action_registry
    ):
        """Test workflow handles errors from action execution."""
        from src.framework.action import Action

        # Setup registry with action that raises error
        class FailingFillFormAction(Action):
            async def execute(self, **kwargs):
                raise Exception("Form fill failed: field not found")

        workflow.action_registry.register(FailingFillFormAction, name="FillFormAction")

        input_data = FormFillingInput(
            url="http://localhost:8000/form",
            form_selector="#form-container",
            fields=[
                FormField(selector="#invalid-field", value="test", field_type="text"),
            ],
            submit_button_selector="#submit-btn",
        )

        # Execute and expect error
        with pytest.raises(WorkflowError) as exc_info:
            await workflow.run(input_data)

        assert "Form filling workflow failed" in str(exc_info.value)
        assert workflow.output.success is False

    @pytest.mark.asyncio
    async def test_workflow_coordinates_multiple_actions(
        self, workflow, action_registry
    ):
        """Test workflow correctly coordinates execution of multiple different actions."""
        from src.framework.action import Action

        # Setup
        workflow.action_registry = action_registry
        call_log = []

        # Create tracked mock actions
        class TrackedFillFormAction(Action):
            async def execute(self, **kwargs):
                call_log.append("FillFormAction")
                return {"status": "success", "fields_filled": 2}

        class TrackedClickElementAction(Action):
            async def execute(self, **kwargs):
                call_log.append("ClickElementAction")
                return {"status": "success"}

        workflow.action_registry.register(TrackedFillFormAction, name="FillFormAction")
        workflow.action_registry.register(TrackedClickElementAction, name="ClickElementAction")

        input_data = FormFillingInput(
            url="http://localhost:8000/form",
            form_selector="#form-container",
            fields=[
                FormField(selector="#field1", value="value1", field_type="text"),
                FormField(selector="#field2", value="value2", field_type="text"),
            ],
            submit_button_selector="#submit-btn",
            wait_for_element="#success",
        )

        # Mock checkpoint
        workflow.checkpoint = AsyncMock(
            return_value=MagicMock(
                decision=MagicMock(choice="proceed")
            )
        )
        workflow._execution = MagicMock()
        workflow._page.url = "http://localhost:8000/form/success"

        # Execute
        output = await workflow.run(input_data)

        # Verify action execution order
        assert "FillFormAction" in call_log
        assert "ClickElementAction" in call_log
        assert call_log.index("FillFormAction") < call_log.index("ClickElementAction")
        assert output.success is True
