"""Base Workflow class for Playwright-based automation workflows."""

import asyncio
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import Page, Browser, BrowserContext

from .checkpoint import CheckpointQuestion, CheckpointRequest, CheckpointResponse, CheckpointDecision
from .errors import WorkflowError, WorkflowCheckpointTimeout
from .execution import Execution
from .resource_manager import ResourceManager
from .state_manager import StateManager
from ..utils.logging import setup_logger


class Workflow(ABC):
    """
    Base class for all Playwright workflow implementations.

    Developers extend this class and override the `run()` method to define
    workflow logic. The framework manages execution context, state persistence,
    checkpoints, and error handling.

    Example:
        class LoginWorkflow(Workflow):
            workflow_type = "login_workflow"
            version = "1.0.0"
            description = "Login to web application"

            async def run(self, username: str, password: str) -> dict[str, Any]:
                await self.navigate(f"{self.base_url}/login")
                await self.fill("#username", username)
                await self.fill("#password", password)

                # Checkpoint: ask agent before submitting
                decision = await self.checkpoint(
                    question=CheckpointQuestion(
                        question_text="Ready to submit login?"
                    ),
                    timeout_seconds=300
                )

                await self.click("button[type='submit']")
                return {"status": "logged_in"}
    """

    # Class-level metadata (required for framework registration)
    workflow_type: str = ""
    version: str = "1.0.0"
    description: str = ""

    def __init__(
        self,
        execution_id: str,
        base_url: str,
        max_retries: int = 3,
        timeout_seconds: int = 3600,
        logger=None,
        state_file: Optional[Path] = None,
        debug: bool = False,
        save_screenshots: bool = False):
        """
        Initialize workflow execution context.

        Args:
            execution_id: Unique UUID v4 for this execution
            base_url: Base URL for the target website
            max_retries: Default max retries for steps (overridable per-step)
            timeout_seconds: Hard timeout for entire workflow
            logger: Structured logger instance (auto-created if None)
            state_file: Path to execution state file (auto-created if None)
            debug: Enable debug mode with verbose logging
            save_screenshots: Save screenshots on errors
        """
        self.execution_id = execution_id
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.logger = logger or setup_logger(__name__, execution_id)
        self.debug = debug
        self.save_screenshots = save_screenshots

        # State management
        if state_file is None:
            state_file = Path(f"data/executions/{execution_id}.json")
        elif isinstance(state_file, str):
            state_file = Path(state_file)
        self._state_manager = StateManager(state_file.parent)
        self._state = {}

        # Resource management (artifacts: screenshots, PDFs, etc.)
        self._resource_manager = ResourceManager()

        # Playwright context
        self._page: Optional[Page] = None
        self._context: Optional[BrowserContext] = None
        self._browser: Optional[Browser] = None

        # Execution tracking
        self._execution: Optional[Execution] = None
        
        # Debug directory
        self.debug_dir: Optional[Path] = None
        if self.debug or self.save_screenshots:
            try:
                self.debug_dir = Path(f"data/debug/{execution_id}")
                self.debug_dir.mkdir(parents=True, exist_ok=True)
                (self.debug_dir / "screenshots").mkdir(exist_ok=True)
                (self.debug_dir / "html").mkdir(exist_ok=True)
                self.logger.debug(f"Debug directory created: {self.debug_dir}")
            except Exception as e:
                self.logger.warning(f"Failed to create debug directory: {e}")
                self.debug_dir = None

    @abstractmethod
    async def run(self, **input_params) -> dict[str, Any]:
        """
        Execute workflow steps. Developers override this method.

        Returns:
            Dict with workflow result/output

        Raises:
            WorkflowError: For permanent failures
        """
        pass

    # ==================== Playwright API Wrappers ====================

    async def navigate(self, url: str, timeout_ms: int = 30000) -> None:
        """
        Navigate to URL with step logging.

        Args:
            url: Target URL
            timeout_ms: Navigation timeout in milliseconds

        Raises:
            WorkflowError: If navigation fails after retries
        """
        if not self._page:
            raise WorkflowError("Page not initialized")

        self.logger.info(f"Navigating to {url}")
        try:
            await self._page.goto(url, timeout=timeout_ms, wait_until="load")
            self.logger.info(f"Successfully navigated to {url}")
        except Exception as e:
            self.logger.error(f"Navigation failed: {e}")
            raise WorkflowError(f"Failed to navigate to {url}: {e}") from e

    async def click(self, selector: str, timeout_ms: int = 10000) -> None:
        """Click element; auto-logged as step."""
        if not self._page:
            raise WorkflowError("Page not initialized")

        self.logger.info(f"Clicking element: {selector}")
        try:
            await self._page.click(selector, timeout=timeout_ms)
            self.logger.info(f"Successfully clicked: {selector}")
        except Exception as e:
            self.logger.error(f"Click failed: {e}")
            raise WorkflowError(f"Failed to click {selector}: {e}") from e

    async def fill(self, selector: str, text: str, timeout_ms: int = 10000) -> None:
        """Fill text input; auto-logged as step."""
        if not self._page:
            raise WorkflowError("Page not initialized")

        self.logger.info(f"Filling element: {selector}")

        # Debug: Log available input fields
        if self.debug:
            try:
                element = await self._page.query_selector(selector)
                if not element:
                    # Element not found - help with debugging
                    inputs = await self._page.query_selector_all("input")
                    self.logger.warning(
                        f"Element '{selector}' not found. "
                        f"Found {len(inputs)} input elements on page."
                    )
                    for idx, inp in enumerate(inputs):
                        inp_id = await inp.get_attribute("id")
                        inp_name = await inp.get_attribute("name")
                        inp_type = await inp.get_attribute("type")
                        self.logger.warning(
                            f"  Input {idx}: id='{inp_id}', name='{inp_name}', type='{inp_type}'"
                        )
                    # Capture page state before error
                    await self.debug_capture_page_state(f"fill_{selector}", "error")
            except Exception as debug_e:
                self.logger.debug(f"Debug logging error: {debug_e}")

        try:
            await self._page.fill(selector, text, timeout=timeout_ms)
            self.logger.info(f"Successfully filled: {selector}")
        except Exception as e:
            self.logger.error(f"Fill failed: {e}")
            if self.debug or self.save_screenshots:
                await self.debug_capture_page_state(f"fill_{selector}", "error")
            raise WorkflowError(f"Failed to fill {selector}: {e}") from e

    async def select(self, selector: str, value: str, timeout_ms: int = 10000) -> None:
        """Select dropdown option; auto-logged as step."""
        if not self._page:
            raise WorkflowError("Page not initialized")

        self.logger.info(f"Selecting option: {value} in {selector}")
        try:
            await self._page.select_option(selector, value, timeout=timeout_ms)
            self.logger.info(f"Successfully selected: {value}")
        except Exception as e:
            self.logger.error(f"Select failed: {e}")
            raise WorkflowError(f"Failed to select {value} in {selector}: {e}") from e

    async def get_text(self, selector: str, timeout_ms: int = 10000) -> str:
        """Extract text from element; included in step output."""
        if not self._page:
            raise WorkflowError("Page not initialized")

        self.logger.info(f"Getting text from: {selector}")
        try:
            text = await self._page.text_content(selector, timeout=timeout_ms)
            self.logger.info(f"Got text: {text}")
            return text or ""
        except Exception as e:
            self.logger.error(f"Get text failed: {e}")
            raise WorkflowError(f"Failed to get text from {selector}: {e}") from e

    async def get_attribute(
        self, selector: str, attribute: str, timeout_ms: int = 10000
    ) -> Optional[str]:
        """Get element attribute value."""
        if not self._page:
            raise WorkflowError("Page not initialized")

        self.logger.info(f"Getting attribute {attribute} from: {selector}")
        try:
            value = await self._page.get_attribute(selector, attribute, timeout=timeout_ms)
            self.logger.info(f"Got attribute: {value}")
            return value
        except Exception as e:
            self.logger.error(f"Get attribute failed: {e}")
            raise WorkflowError(
                f"Failed to get attribute {attribute} from {selector}: {e}"
            ) from e

    async def wait_for_selector(
        self, selector: str, timeout_ms: int = 10000
    ) -> None:
        """Wait for element to appear."""
        if not self._page:
            raise WorkflowError("Page not initialized")

        self.logger.info(f"Waiting for selector: {selector}")
        try:
            await self._page.wait_for_selector(selector, timeout=timeout_ms)
            self.logger.info(f"Selector appeared: {selector}")
        except Exception as e:
            self.logger.error(f"Wait for selector failed: {e}")
            raise WorkflowError(f"Selector not found: {selector}: {e}") from e

    async def take_screenshot(self, name: str = None) -> Path:
        """
        Capture screenshot.

        Returns:
            Path to saved PNG file in data/artifacts/{execution_id}/
        """
        if not self._page:
            raise WorkflowError("Page not initialized")

        artifacts_dir = Path(f"data/artifacts/{self.execution_id}")
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        if name is None:
            name = f"screenshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"

        file_path = artifacts_dir / name
        self.logger.info(f"Taking screenshot: {file_path}")

        try:
            await self._page.screenshot(path=str(file_path))
            self.logger.info(f"Screenshot saved: {file_path}")

            # Track resource in execution state
            resource = self._resource_manager.track_resource(
                self.execution_id,
                file_path,
                resource_type="screenshot",
                name=name
            )

            # Update execution state with resource
            if self._execution:
                resources_data = self._execution.state.resources or []
                resources_data.append(resource.model_dump())
                self._execution.state.resources = resources_data
                await self._execution.save()

            return file_path
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            raise WorkflowError(f"Failed to take screenshot: {e}") from e

    async def export_to_pdf(self, name: str = None) -> Path:
        """
        Export current page as PDF.

        Returns:
            Path to saved PDF file in data/artifacts/{execution_id}/
        """
        if not self._page:
            raise WorkflowError("Page not initialized")

        artifacts_dir = Path(f"data/artifacts/{self.execution_id}")
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        if name is None:
            name = f"export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"

        file_path = artifacts_dir / name
        self.logger.info(f"Exporting to PDF: {file_path}")

        try:
            await self._page.pdf(path=str(file_path), print_background=True)
            self.logger.info(f"PDF exported: {file_path}")

            # Track resource in execution state
            resource = self._resource_manager.track_resource(
                self.execution_id,
                file_path,
                resource_type="pdf",
                name=name
            )

            # Update execution state with resource
            if self._execution:
                resources_data = self._execution.state.resources or []
                resources_data.append(resource.model_dump())
                self._execution.state.resources = resources_data
                await self._execution.save()

            return file_path
        except Exception as e:
            self.logger.error(f"PDF export failed: {e}")
            raise WorkflowError(f"Failed to export PDF: {e}") from e

    async def debug_capture_page_state(self, step_name: str = "debug", context: str = "before") -> None:
        """
        Capture page state for debugging (screenshots, HTML, console messages).

        Args:
            step_name: Name of the step for file naming
            context: Context like "before", "after", "error"
        """
        if not self.debug and not self.save_screenshots:
            return

        if not self._page:
            self.logger.warning("Cannot capture page state: page not initialized")
            return

        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_step_name = step_name.lower().replace(" ", "_")

            # Take screenshot
            screenshot_path = (
                self.debug_dir / "screenshots" / f"{safe_step_name}_{context}_{timestamp}.png"
            )
            await self._page.screenshot(path=str(screenshot_path))
            self.logger.debug(f"Debug screenshot saved: {screenshot_path}")

            # Save HTML content
            html_path = (
                self.debug_dir / "html" / f"{safe_step_name}_{context}_{timestamp}.html"
            )
            html_content = await self._page.content()
            html_path.write_text(html_content)
            self.logger.debug(f"Debug HTML saved: {html_path}")

            # Log page metadata
            current_url = self._page.url
            page_title = await self._page.title()
            self.logger.info(
                f"Debug Capture: {step_name} ({context}) - URL: {current_url}, Title: {page_title}"
            )

            # Log available input fields for debugging
            if self.debug:
                try:
                    inputs = await self._page.query_selector_all("input")
                    self.logger.debug(f"Found {len(inputs)} input elements on page")

                    for idx, inp in enumerate(inputs):
                        input_id = await inp.get_attribute("id")
                        input_name = await inp.get_attribute("name")
                        input_type = await inp.get_attribute("type")
                        placeholder = await inp.get_attribute("placeholder")
                        visible = await inp.is_visible()

                        self.logger.debug(
                            f"  Input {idx}: id={input_id}, name={input_name}, "
                            f"type={input_type}, placeholder={placeholder}, visible={visible}"
                        )
                except Exception as e:
                    self.logger.debug(f"Could not log input fields: {e}")

        except Exception as e:
            self.logger.error(f"Debug capture failed: {e}")

    # ==================== State Management ====================

    def get_state(self, key: str, default=None) -> Any:
        """
        Get persisted state value.

        State persists across checkpoint/resume cycles.
        """
        return self._state.get(key, default)

    def set_state(self, key: str, value: Any) -> None:
        """Set persisted state value (auto-saved to JSON)."""
        self._state[key] = value
        # Auto-save to state manager
        if self._execution:
            self._execution.save()

    def get_all_state(self) -> dict[str, Any]:
        """Get complete state dict (read-only)."""
        return dict(self._state)

    # ==================== Checkpoint API ====================

    async def checkpoint(
        self,
        question: CheckpointQuestion,
        timeout_seconds: Optional[int] = None,
        allow_skip: bool = False) -> CheckpointResponse:
        """
        Pause workflow and request agent decision.

        The workflow suspends here until the MCP server receives a decision from
        the agent. All execution state is persisted; on resume, execution continues
        from exactly this point.

        Args:
            question: CheckpointQuestion instance with checkpoint details
            timeout_seconds: Timeout for agent response (default: framework timeout)
            allow_skip: If True and agent doesn't respond, skip this checkpoint

        Returns:
            Agent's decision response

        Raises:
            WorkflowCheckpointTimeout: If timeout exceeded and allow_skip=False
        """
        if not self._execution:
            raise WorkflowError("Execution not initialized")

        timeout_seconds = timeout_seconds or self.timeout_seconds

        self.logger.info(
            f"Checkpoint: {question.question_text} (timeout: {timeout_seconds}s)"
        )

        # Create checkpoint request
        checkpoint_request = CheckpointRequest(
            checkpoint_id=str(uuid.uuid4()),
            execution_id=self.execution_id,
            workflow_name=self.workflow_type or self.__class__.__name__,
            step_name="checkpoint",
            question=question,
            timeout_seconds=timeout_seconds,
            context=self.get_all_state())

        # Pause execution and wait for decision
        try:
            # Create event for MCP server to signal when decision is ready
            event = asyncio.Event()
            self._execution.checkpoint_event = event
            
            # Store checkpoint in execution state
            self._execution.pause(checkpoint_request.model_dump())
            self.logger.info("Execution paused at checkpoint")

            # Wait for agent to respond via MCP resolve_checkpoint tool
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                if allow_skip:
                    self.logger.warning(f"Checkpoint timeout ({timeout_seconds}s), skipping")
                    decision = CheckpointDecision(confirmed=False)
                else:
                    raise WorkflowCheckpointTimeout(
                        f"Checkpoint timed out after {timeout_seconds}s"
                    )
            else:
                # Event was set by MCP server, get the decision
                decision = self._execution.checkpoint_decision
                if not decision:
                    decision = CheckpointDecision(confirmed=False)

            response = CheckpointResponse(
                checkpoint_id=checkpoint_request.checkpoint_id,
                execution_id=self.execution_id,
                decision=decision)

            self.logger.info(f"Checkpoint decision: {response.decision}")
            return response

        except asyncio.TimeoutError:
            if allow_skip:
                self.logger.warning("Checkpoint timeout, skipping")
                decision = CheckpointDecision(confirmed=False)
                return CheckpointResponse(
                    checkpoint_id=checkpoint_request.checkpoint_id,
                    execution_id=self.execution_id,
                    decision=decision)
            else:
                raise WorkflowCheckpointTimeout(
                    f"Checkpoint timed out after {timeout_seconds}s"
                )
        except Exception as e:
            self.logger.error(f"Checkpoint error: {e}")
            raise WorkflowError(f"Checkpoint failed: {e}") from e

    # ==================== Lifecycle Hooks ====================

    async def on_start(self) -> None:
        """Called before first step. Override for setup logic."""
        pass

    async def on_step_start(self, step_name: str, step_index: int) -> None:
        """Called before each step. Override to hook into step lifecycle."""
        pass

    async def on_step_complete(self, step_name: str, output: Any) -> None:
        """Called after step success. Override for post-step logic."""
        pass

    async def on_step_error(self, step_name: str, error: Exception) -> None:
        """Called on step error. Override for error handling logic."""
        pass

    async def on_checkpoint(self, question: CheckpointQuestion) -> None:
        """Called before checkpoint. Override to customize checkpoint behavior."""
        pass

    async def on_complete(self, result: dict[str, Any]) -> None:
        """Called after workflow completes successfully."""
        pass

    async def on_error(self, error: Exception) -> None:
        """Called when workflow fails. Override for cleanup logic."""
        pass

    # ==================== Execution Helpers ====================

    def set_page(self, page: Page) -> None:
        """Set the Playwright page instance (internal use)."""
        self._page = page

    def set_browser_context(self, context: BrowserContext) -> None:
        """Set the browser context (internal use)."""
        self._context = context

    def set_browser(self, browser: Browser) -> None:
        """Set the browser instance (internal use)."""
        self._browser = browser

    def set_execution(self, execution: Execution) -> None:
        """Set the execution tracker (internal use)."""
        self._execution = execution
