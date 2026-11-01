"""Example LoginWorkflow demonstrating web automation with the framework."""

import uuid
from typing import Optional, Dict, Any
from src.framework import Workflow, step
from src.framework.errors import WorkflowError
from dataclasses import dataclass


@dataclass
class LoginInput:
    """Input data for login workflow."""

    url: str
    username: str
    password: str


@dataclass
class LoginOutput:
    """Output data from login workflow."""

    success: bool
    message: str
    dashboard_url: Optional[str] = None
    session_id: Optional[str] = None


class LoginWorkflow(Workflow):
    """
    Example workflow for logging into a web application.

    Demonstrates:
    - Sequential step execution with @step decorator
    - Form filling and submission
    - Error handling for authentication failures
    - Structured input/output
    """

    # Workflow metadata
    workflow_type = "login"
    version = "1.0.0"
    description = "Login to a web application with username and password"

    def __init__(self, execution_id: Optional[str] = None, base_url: str = "http://localhost:8000"):
        """Initialize LoginWorkflow."""
        # Generate execution_id if not provided (for testing)
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        super().__init__(
            execution_id=execution_id,
            base_url=base_url,
        )
        self.input: Optional[LoginInput] = None
        self.output: Optional[LoginOutput] = None

    @step(name="Navigate to Login Page", max_retries=2, timeout_ms=10000)
    async def navigate_to_login(self) -> None:
        """Navigate to the login page."""
        if not self.input:
            raise WorkflowError("Input not provided")

        await self.navigate(self.input.url)
        await self.wait_for_selector("#login-form", timeout_ms=10000)

    @step(name="Fill Username", max_retries=1)
    async def fill_username(self) -> None:
        """Fill in the username field."""
        if not self.input:
            raise WorkflowError("Input not provided")

        await self.fill("#username", self.input.username)

    @step(name="Fill Password", max_retries=1)
    async def fill_password(self) -> None:
        """Fill in the password field."""
        if not self.input:
            raise WorkflowError("Input not provided")

        await self.fill("#password", self.input.password)

    @step(name="Click Submit", max_retries=2)
    async def click_submit(self) -> None:
        """Click the login submit button."""
        await self.click("#submit-btn")

    @step(name="Wait for Dashboard", max_retries=2, timeout_ms=10000)
    async def wait_for_dashboard(self) -> None:
        """Wait for the dashboard to load (indicates successful login)."""
        await self.wait_for_selector("#user-info", timeout_ms=10000)

    async def run(self, input_data: LoginInput) -> LoginOutput:
        """
        Execute the login workflow.

        Args:
            input_data: LoginInput with url, username, password

        Returns:
            LoginOutput with success status and dashboard URL
        """
        self.input = input_data

        try:
            # Execute steps in sequence
            await self.navigate_to_login()
            await self.fill_username()
            await self.fill_password()
            await self.click_submit()
            await self.wait_for_dashboard()

            # Success
            dashboard_url = self._page.url if self._page else None
            self.output = LoginOutput(
                success=True,
                message="Login successful",
                dashboard_url=dashboard_url,
                session_id="session_123",
            )

            return self.output

        except Exception as e:
            # Handle errors
            error_message = str(e)

            # Check for authentication errors
            if "401" in error_message or "Unauthorized" in error_message:
                self.output = LoginOutput(
                    success=False,
                    message="Invalid credentials (401 Unauthorized)",
                )
            elif "403" in error_message or "Forbidden" in error_message:
                self.output = LoginOutput(
                    success=False,
                    message="Access forbidden (403)",
                )
            else:
                self.output = LoginOutput(
                    success=False,
                    message=f"Login failed: {error_message}",
                )

            # Re-raise for framework to handle
            raise WorkflowError(f"Login workflow failed: {error_message}") from e

    async def on_step_complete(self, step_name: str, result: Any) -> None:
        """Called when a step completes successfully."""
        self.logger.info(f"✓ Step complete: {step_name}")

    async def on_error(self, error: Exception) -> None:
        """Called when an error occurs during workflow execution."""
        self.logger.error(f"✗ Error occurred: {type(error).__name__}: {error}")
