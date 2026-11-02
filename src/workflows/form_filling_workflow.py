"""Form filling workflow using reusable action framework."""

import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from src.framework import Workflow, step
from src.framework.action_registry import ActionRegistry
from src.framework.errors import WorkflowError, WorkflowCheckpointTimeout
from src.framework.checkpoint import CheckpointQuestion, CheckpointDecision


@dataclass
class FormField:
    """Represents a form field to fill."""

    selector: str
    value: str
    field_type: str = "text"  # text, password, email, dropdown, checkbox


@dataclass
class FormFillingInput:
    """Input data for form filling workflow."""

    url: str
    form_selector: str
    fields: List[FormField]
    submit_button_selector: str
    wait_for_element: Optional[str] = None  # Element to wait for after submission
    username_selector: Optional[str] = None  # For login forms
    password_selector: Optional[str] = None  # For login forms
    verify_url_contains: Optional[str] = None  # URL verification after submission


@dataclass
class FormFillingOutput:
    """Output data from form filling workflow."""

    success: bool
    message: str
    submitted_at: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None


class FormFillingWorkflow(Workflow):
    """
    Workflow for filling and submitting forms using reusable actions.

    Demonstrates the action framework in use:
    - Uses custom actions from the action registry
    - Actions handle their own error handling and retry logic
    - Workflows orchestrate action execution without implementation details
    - Easy to extend with new custom actions
    """

    workflow_type = "form_filling"
    version = "1.0.0"
    description = "Fill form fields and submit using reusable actions"

    def __init__(
        self,
        execution_id: str | None = None,
        base_url: str = "http://localhost:8000",
    ):
        """Initialize FormFillingWorkflow."""
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        super().__init__(
            execution_id=execution_id,
            base_url=base_url,
        )
        self.input: FormFillingInput | None = None
        self.output: FormFillingOutput | None = None
        self.action_registry = ActionRegistry()

    @step(name="Navigate to Form Page", max_retries=2, timeout_ms=10000)
    async def navigate_to_form(self) -> None:
        """Navigate to the form page."""
        if not self.input:
            raise WorkflowError("Input not provided")

        await self.navigate(self.input.url)
        await self.wait_for_selector(self.input.form_selector, timeout_ms=10000)

    @step(name="Fill Form Fields", max_retries=1)
    async def fill_form_fields(self) -> Dict[str, Any]:
        """Fill form fields using actions."""
        if not self.input or not self.input.fields:
            raise WorkflowError("Form fields not provided")

        # Use FillFormAction from registry for generic form filling
        fill_action_class = self.action_registry.get("FillFormAction")
        fill_action = fill_action_class(self)

        # Prepare field mapping for form filling
        field_mapping = {
            field.selector: field.value
            for field in self.input.fields
            if field.field_type != "checkbox"
        }

        # Execute form filling action
        result = await fill_action.run(
            field_mapping=field_mapping,
            wait_ms=5000,
        )

        # Handle checkbox fields separately
        for field in self.input.fields:
            if field.field_type == "checkbox" and field.value == "on":
                checkbox_action_class = self.action_registry.get("CheckCheckboxAction")
                checkbox_action = checkbox_action_class(self)
                await checkbox_action.run(
                    selector=field.selector,
                )

        self.logger.info(f"Form fields filled: {len(self.input.fields)} fields")
        return result

    @step(name="Request Form Submission Approval", max_retries=0)
    async def request_approval(self) -> CheckpointDecision:
        """Request agent/human approval before submitting the form."""
        if not self.input:
            raise WorkflowError("Input not provided")

        # Skip checkpoint if execution not initialized (e.g., in unit tests)
        if not self._execution:
            self.logger.info("Execution not initialized - skipping checkpoint")
            return CheckpointDecision(choice="proceed")

        # Create checkpoint question
        question = CheckpointQuestion(
            question_text="Ready to submit the form?",
            question_type="single_choice",
            options=["proceed", "cancel"],
            metadata={
                "current_page": self._page.url if self._page else None,
                "form_selector": self.input.form_selector,
                "fields_count": len(self.input.fields) if self.input.fields else 0,
            },
        )

        try:
            # Request decision from agent
            response = await self.checkpoint(
                question=question,
                timeout_seconds=300,
                allow_skip=False,
            )

            return response.decision

        except WorkflowCheckpointTimeout:
            raise WorkflowError(
                "Checkpoint timeout: Agent did not respond within 5 minutes"
            )

    @step(name="Submit Form", max_retries=2)
    async def submit_form(self) -> Dict[str, Any]:
        """Submit the form using action."""
        if not self.input:
            raise WorkflowError("Input not provided")

        # Use ClickElementAction for form submission
        submit_action_class = self.action_registry.get("ClickElementAction")
        submit_action = submit_action_class(self)

        result = await submit_action.run(
            selector=self.input.submit_button_selector,
            wait_ms=10000,
        )

        return result

    @step(name="Verify Form Submission", max_retries=2, timeout_ms=10000)
    async def verify_submission(self) -> Dict[str, Any]:
        """Verify the form was submitted successfully."""
        if not self.input:
            raise WorkflowError("Input not provided")

        verification_result = {}

        # Wait for expected element if provided
        if self.input.wait_for_element:
            await self.wait_for_selector(
                self.input.wait_for_element,
                timeout_ms=10000,
            )
            verification_result["element_found"] = True

        # Verify URL change if provided
        if self.input.verify_url_contains:
            current_url = self._page.url if self._page else ""
            if self.input.verify_url_contains in current_url:
                verification_result["url_verified"] = True
            else:
                raise WorkflowError(
                    f"URL verification failed: expected '{self.input.verify_url_contains}' "
                    f"in '{current_url}'"
                )

        self.logger.info(f"Form submission verified: {verification_result}")
        return verification_result

    async def run(self, input_data: FormFillingInput) -> FormFillingOutput:
        """
        Execute the form filling workflow.

        Args:
            input_data: FormFillingInput with form details and fields

        Returns:
            FormFillingOutput with success status
        """
        self.input = input_data

        try:
            # Execute workflow steps
            await self.navigate_to_form()
            await self.fill_form_fields()

            # Request approval before submitting
            decision = await self.request_approval()

            # Check agent's decision
            if decision.choice == "cancel":
                self.output = FormFillingOutput(
                    success=False,
                    message="Form submission cancelled by agent",
                )
                raise WorkflowError("Form submission cancelled by agent")
            elif decision.choice != "proceed":
                self.output = FormFillingOutput(
                    success=False,
                    message=f"Invalid decision: {decision.choice}",
                )
                raise WorkflowError(f"Invalid checkpoint decision: {decision.choice}")

            # Agent approved, proceed with submission
            await self.submit_form()
            verification_result = await self.verify_submission()

            # Success
            self.output = FormFillingOutput(
                success=True,
                message="Form filled and submitted successfully",
                submitted_at=self._page.url if self._page else None,
                verification_result=verification_result,
            )

            return self.output

        except Exception as e:
            # Handle errors
            error_message = str(e)

            if "cancelled by agent" in error_message.lower():
                # Don't re-wrap cancellation messages
                raise
            else:
                self.output = FormFillingOutput(
                    success=False,
                    message=f"Form filling failed: {error_message}",
                )

            # Re-raise for framework to handle
            raise WorkflowError(f"Form filling workflow failed: {error_message}") from e

    async def on_step_complete(self, step_name: str, result: Any) -> None:
        """Called when a step completes successfully."""
        self.logger.info(f"✓ Step complete: {step_name}")

    async def on_error(self, error: Exception) -> None:
        """Called when an error occurs during workflow execution."""
        self.logger.error(f"✗ Error occurred: {type(error).__name__}: {error}")
