# Python API Contract: Workflow Framework

**Status**: Phase 1 Design  
**Target Audience**: Developers creating custom Playwright workflows

---

## Overview

Developers extend the `Workflow` base class to define custom automation logic. The framework provides lifecycle hooks, step decorators, checkpoint APIs, and logging.

---

## Base Workflow Class

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

class Workflow(ABC):
    """
    Base class for all Playwright workflow implementations.
    
    Developers extend this class and override the `run()` method to define
    workflow logic. The framework manages execution context, state persistence,
    checkpoints, and error handling.
    
    Example:
        class LoginWorkflow(Workflow):
            async def run(self, username: str, password: str) -> Dict[str, Any]:
                await self.navigate(f"{self.base_url}/login")
                await self.fill("#username", username)
                await self.fill("#password", password)
                
                # Checkpoint: ask agent before submitting
                decision = await self.checkpoint(
                    question={"text": "Ready to submit login?"},
                    timeout_seconds=300
                )
                
                await self.click("button[type='submit']")
                return {"status": "logged_in"}
    """
    
    # Class-level metadata (required for framework registration)
    workflow_type: str  # e.g., "login_workflow"
    version: str  # e.g., "1.0.0" (semantic versioning)
    description: str  # Human-readable description
    
    def __init__(
        self,
        execution_id: str,
        base_url: str,
        max_retries: int = 3,
        timeout_seconds: int = 3600,
        logger = None
    ):
        """
        Initialize workflow execution context.
        
        Args:
            execution_id: Unique UUID v4 for this execution
            base_url: Base URL for the target website
            max_retries: Default max retries for steps (overridable per-step)
            timeout_seconds: Hard timeout for entire workflow
            logger: Structured logger instance (auto-created if None)
        """
        self.execution_id = execution_id
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.logger = logger or self._setup_logger()
        
        # Framework-managed state
        self._state = {}  # Persisted across checkpoint/resume
        self._page = None  # Playwright page handle
        self._context = None  # Browser context
    
    @abstractmethod
    async def run(self, **input_params) -> Dict[str, Any]:
        """
        Execute workflow steps. Developers override this method.
        
        Returns:
            Dict with workflow result/output
        
        Raises:
            WorkflowError: For permanent failures
            WorkflowCheckpointRequired: Raised internally when checkpoint needed
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
        pass
    
    async def click(self, selector: str, timeout_ms: int = 10000) -> None:
        """Click element; auto-logged as step."""
        pass
    
    async def fill(self, selector: str, text: str, timeout_ms: int = 10000) -> None:
        """Fill text input; auto-logged as step."""
        pass
    
    async def select(self, selector: str, value: str, timeout_ms: int = 10000) -> None:
        """Select dropdown option; auto-logged as step."""
        pass
    
    async def get_text(self, selector: str) -> str:
        """Extract text from element; included in step output."""
        pass
    
    async def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Get element attribute value."""
        pass
    
    async def wait_for_selector(self, selector: str, timeout_ms: int = 10000) -> None:
        """Wait for element to appear."""
        pass
    
    async def take_screenshot(self, name: str = None) -> Path:
        """
        Capture screenshot.
        
        Returns:
            Path to saved PNG file in data/artifacts/{execution_id}/
        """
        pass
    
    async def export_to_pdf(self, name: str = None) -> Path:
        """
        Export current page as PDF.
        
        Returns:
            Path to saved PDF file in data/artifacts/{execution_id}/
        """
        pass
    
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
    
    def get_all_state(self) -> Dict[str, Any]:
        """Get complete state dict (read-only)."""
        return dict(self._state)
    
    # ==================== Checkpoint API ====================
    
    async def checkpoint(
        self,
        question: Dict[str, Any],
        timeout_seconds: Optional[int] = None,
        allow_skip: bool = False
    ) -> Dict[str, Any]:
        """
        Pause workflow and request agent decision.
        
        The workflow suspends here until the MCP server receives a decision from
        the agent. All execution state is persisted; on resume, execution continues
        from exactly this point.
        
        Args:
            question: JSON-serializable dict with checkpoint question.
                      Format: {"type": "confirmation", "text": "...", "options": [...]}
            timeout_seconds: Timeout for agent response (default: framework timeout)
            allow_skip: If True and agent doesn't respond, skip this checkpoint
        
        Returns:
            Agent's decision response (JSON object)
        
        Raises:
            WorkflowCheckpointTimeout: If timeout exceeded and allow_skip=False
        
        Example:
            decision = await self.checkpoint(
                question={
                    "type": "confirmation",
                    "text": "Ready to submit login form?",
                    "options": [
                        {"value": "proceed", "label": "Yes, submit"},
                        {"value": "cancel", "label": "Cancel"}
                    ]
                },
                timeout_seconds=300
            )
            
            if decision['value'] == 'proceed':
                await self.click("button[type='submit']")
            else:
                raise WorkflowCancelled("User cancelled workflow")
        """
        pass
    
    # ==================== Error Handling & Retry ====================
    
    @retry(
        max_retries=3,
        backoff_strategy='exponential',
        retry_on_errors=['TimeoutError', 'NetworkError'],
        fail_on_errors=['ValidationError', 'AuthorizationError']
    )
    async def some_step(self):
        """
        Decorator-based retry configuration.
        
        - transient_errors (TimeoutError, NetworkError): auto-retried
        - permanent_errors (ValidationError): escalate to checkpoint
        
        Retries are logged; each attempt has its own step record.
        """
        pass
    
    # ==================== Logging ====================
    
    def logger.info(self, message: str, **context) -> None:
        """
        Structured logging (auto-prefixed with execution_id, step_name).
        
        All logs written to JSON format in data/logs/{execution_id}.log
        """
        pass
    
    def logger.error(self, message: str, error: Exception = None, **context) -> None:
        """Log error with stack trace."""
        pass
    
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
    
    async def on_checkpoint(self, question: Dict) -> None:
        """Called before checkpoint. Override to customize checkpoint behavior."""
        pass
    
    async def on_complete(self, result: Dict[str, Any]) -> None:
        """Called after workflow completes successfully."""
        pass
    
    async def on_error(self, error: Exception) -> None:
        """Called when workflow fails. Override for cleanup logic."""
        pass
```

---

## Step Decorator

```python
from functools import wraps
from typing import Callable

def step(
    name: str = None,
    max_retries: int = 3,
    backoff_strategy: str = 'exponential',
    retry_on_errors: list = None,
    fail_on_errors: list = None,
    timeout_ms: int = None
):
    """
    Decorator for workflow methods to enable retry, logging, and error classification.
    
    Usage:
        class MyWorkflow(Workflow):
            @step(
                name="login",
                max_retries=3,
                retry_on_errors=['TimeoutError', 'ConnectError'],
                fail_on_errors=['ValidationError']
            )
            async def login_step(self, username, password):
                await self.fill("#username", username)
                await self.fill("#password", password)
                await self.click("button[type='submit']")
    
    Behavior:
    - Step execution is automatically logged as structured JSON
    - On transient error, step is retried (with backoff)
    - On permanent error, execution pauses at checkpoint (agent decides next action)
    - Step duration, retries, and output are recorded in ExecutionLog
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            step_name = name or func.__name__
            step_index = len(self._state.get('completed_steps', []))
            
            self.logger.info(f"Starting step: {step_name}")
            
            for attempt in range(max_retries + 1):
                try:
                    result = await func(self, *args, **kwargs)
                    self.logger.info(f"Completed step: {step_name}")
                    return result
                except Exception as e:
                    error_type = type(e).__name__
                    
                    if error_type in (fail_on_errors or []):
                        self.logger.error(f"Permanent error in {step_name}: {e}")
                        raise WorkflowError(f"Step failed: {step_name}", cause=e)
                    
                    if attempt < max_retries and error_type in (retry_on_errors or []):
                        self.logger.warning(f"Retry {attempt + 1} of {step_name}: {e}")
                        continue
                    
                    raise
        
        return wrapper
    return decorator
```

---

## Error Classes

```python
class WorkflowError(Exception):
    """Base error for workflow execution failures."""
    def __init__(self, message: str, cause: Exception = None):
        self.message = message
        self.cause = cause
        super().__init__(message)

class WorkflowCheckpointRequired(WorkflowError):
    """Raised when workflow needs agent decision before continuing."""
    pass

class WorkflowCheckpointTimeout(WorkflowError):
    """Raised when checkpoint decision not received within timeout."""
    pass

class WorkflowCancelled(WorkflowError):
    """Raised when agent cancels workflow at checkpoint."""
    pass

class WorkflowSessionExpired(WorkflowError):
    """Raised when browser session is invalid (401/403)."""
    pass

class WorkflowResourceExhausted(WorkflowError):
    """Raised when execution exceeds resource quota."""
    pass
```

---

## Example: Complete Login Workflow

```python
from typing import Dict, Any
from src.framework import Workflow, step, WorkflowError

class LoginWorkflow(Workflow):
    """Automated login workflow with agent checkpoint."""
    
    workflow_type = "login_workflow"
    version = "1.0.0"
    description = "Authenticate to example.com using username/password"
    
    @step(name="navigate", max_retries=2, retry_on_errors=['TimeoutError'])
    async def navigate_to_login(self):
        """Navigate to login page."""
        await self.navigate(f"{self.base_url}/login")
        self.logger.info("Navigated to login page")
    
    @step(name="fill_credentials", max_retries=1)
    async def fill_credentials(self, username: str, password: str):
        """Fill login form with credentials."""
        await self.fill("#username", username)
        await self.fill("#password", password)
        self.logger.info(f"Filled credentials for user: {username}")
    
    async def run(self, username: str, password: str, **kwargs) -> Dict[str, Any]:
        """Main workflow execution."""
        try:
            # Step 1: Navigate
            await self.navigate_to_login()
            
            # Step 2: Fill form
            await self.fill_credentials(username, password)
            
            # Step 3: Checkpoint - ask agent before submitting
            decision = await self.checkpoint(
                question={
                    "type": "confirmation",
                    "text": "Ready to submit login form?",
                    "context": {
                        "username": username,
                        "screenshot_url": (await self.take_screenshot()).name
                    },
                    "options": [
                        {"value": "proceed", "label": "Yes, submit form"},
                        {"value": "cancel", "label": "Cancel and stop"}
                    ]
                },
                timeout_seconds=300
            )
            
            if decision.get('value') != 'proceed':
                raise WorkflowCancelled("Agent cancelled login")
            
            # Step 4: Submit
            await self.click("button[type='submit']")
            await self.wait_for_selector(".dashboard")
            
            # Step 5: Verify
            title = await self.get_text("h1")
            
            return {
                "status": "success",
                "username": username,
                "page_title": title
            }
        
        except WorkflowError as e:
            self.logger.error(f"Workflow failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", error=e)
            raise WorkflowError(f"Unexpected error: {e}", cause=e)
```

---

## Registration & Discovery

```python
# Framework auto-discovers workflows via entry_point in pyproject.toml:
# [project.entry-points."playwright.workflows"]
# login = "src.workflows.login:LoginWorkflow"

# Or manual registration:
from src.framework import WorkflowRegistry

registry = WorkflowRegistry()
registry.register(LoginWorkflow)
registry.register(FormFillingWorkflow)

# List available workflows
workflows = registry.list()  # Returns metadata
workflow_cls = registry.get("login_workflow")  # Returns class
```

---

## Contract Version

**Version**: 1.0.0  
**Status**: Locked (Phase 1)  
**Last Updated**: 2026-11-01

---

**Python API contract complete. Ready for implementation.**
