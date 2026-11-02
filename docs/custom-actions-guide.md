# Custom Actions Guide

This guide explains how to create reusable custom actions for the Playwright Workflow Orchestration Framework.

## Table of Contents

- [Overview](#overview)
- [Action Base Class](#action-base-class)
- [Creating Custom Actions](#creating-custom-actions)
- [Registering Actions](#registering-actions)
- [Using Custom Actions in Workflows](#using-custom-actions-in-workflows)
- [Error Handling](#error-handling)
- [Action Dependencies](#action-dependencies)
- [Examples](#examples)
  - [Form Actions](#form-actions)
  - [Login Actions](#login-actions)
  - [Custom Action Example](#custom-action-example)

## Overview

Actions are reusable, encapsulated units of workflow logic that can be:
- **Composed** into multiple workflows without code duplication
- **Tested** independently and in isolation
- **Extended** with retry logic, logging, and error handling automatically
- **Discovered** at runtime via the ActionRegistry
- **Coordinated** with dependency management

Actions are ideal for repetitive tasks like:
- Filling forms with different data
- Logging into applications
- Uploading files
- Taking screenshots
- Navigating between pages
- Waiting for elements to appear

## Action Base Class

The `Action` base class is defined in `src/framework/action.py` and provides:

### Core Components

```python
from src.framework.action import Action
from src.framework.errors import PermanentError, TransientError

class MyCustomAction(Action):
    """Your custom action implementation."""
    
    async def execute(self, **kwargs) -> Any:
        """Implement your action logic here."""
        pass
```

### Key Features

**1. Automatic Logging**
- All actions inherit structured JSON logging
- Actions automatically log execution start, completion, and errors
- Logs include action name, error type, and retry count

**2. Error Classification & Retry**
- Actions support automatic retry for transient errors
- `PermanentError`: Non-retryable errors (bad selector, invalid input)
- `TransientError`: Retryable errors (timeout, network failure)
- Configurable retry policy with exponential backoff

**3. Workflow Context**
- Actions receive reference to parent workflow via `workflow_context`
- Access browser page via `self.workflow_context.page`
- Access execution tracking via `self.workflow_context._execution`

**4. Dependency Management**
- Actions can declare dependencies on other actions
- Framework validates that dependencies complete before executing action

### Constructor

```python
def __init__(
    self,
    workflow_context: Any,           # Reference to parent workflow
    name: Optional[str] = None,      # Action name for logging (defaults to class name)
    max_retries: int = 3,            # Max retry attempts
    requires: Optional[List[str]] = None,  # List of action names this depends on
):
    """Initialize action with workflow context."""
```

### Public Interface

```python
async def run(self, **kwargs) -> Any:
    """Execute the action with retry logic and error handling.
    
    This is the public method to execute actions.
    It wraps execute() with automatic retry, logging, and tracking.
    """

def get_dependencies(self) -> List[str]:
    """Get list of action names this action depends on."""

def has_dependency(self, action_name: str) -> bool:
    """Check if this action depends on another action."""
```

## Creating Custom Actions

### Step 1: Define Your Action Class

Create a new file in `src/shared_steps/` or `src/workflows/actions/`:

```python
"""Custom action module."""

from typing import Any, Dict
from src.framework.action import Action
from src.framework.errors import PermanentError, TransientError
from src.utils.logging import setup_logger

logger = setup_logger(__name__)


class MyCustomAction(Action):
    """Brief description of what your action does.
    
    Longer description with examples of usage.
    """
    
    async def execute(self, **kwargs) -> Any:
        """Execute the action.
        
        Args:
            **kwargs: Action-specific parameters
            
        Returns:
            Result of action execution
            
        Raises:
            PermanentError: For non-retryable errors
            TransientError: For retryable errors
        """
        # Your implementation here
        pass
```

### Step 2: Implement Execute Method

The `execute()` method is where your action logic goes:

```python
async def execute(self, **kwargs) -> Any:
    """Execute the action.
    
    Access workflow resources via self.workflow_context:
    - self.workflow_context.page: Playwright Page object
    - self.workflow_context._execution: Execution tracking
    
    Example with form filling:
    """
    page = self.workflow_context.page
    
    # Your async logic here
    await page.goto(self.workflow_context.input_data.url)
    
    return {"status": "success", "result": ...}
```

### Step 3: Error Handling

Classify errors appropriately to enable automatic retry:

```python
async def execute(self, **kwargs) -> Any:
    try:
        # Your code
        result = await self.workflow_context.page.query_selector(selector)
        if not result:
            # Permanent error - invalid selector
            raise PermanentError(
                self.name,
                f"Selector '{selector}' not found",
            )
            
        # Transient error - temporary network issue
    except TimeoutError as e:
        raise TransientError(
            self.name,
            f"Timeout: {str(e)}",
            cause=e,
        )
    except Exception as e:
        # Unknown error - classify based on error type
        if "timeout" in str(e).lower():
            raise TransientError(self.name, str(e), cause=e)
        else:
            raise PermanentError(self.name, str(e), cause=e)
```

## Registering Actions

### Option 1: Manual Registration

Register actions in your workflow initialization:

```python
from src.framework.action_registry import ActionRegistry
from src.shared_steps.form_actions import FillFormAction

# Create registry
registry = ActionRegistry()

# Register actions
registry.register(FillFormAction, name="fill_form")
registry.register(SubmitFormAction, name="submit_form")
registry.register(ValidateFormAction, name="validate_form")
```

### Option 2: Entry Point Registration

Register actions in `pyproject.toml` for automatic discovery:

```toml
[project.entry-points."playwright.actions"]
fill_form = "src.shared_steps.form_actions:FillFormAction"
submit_form = "src.shared_steps.form_actions:SubmitFormAction"
validate_form = "src.shared_steps.form_actions:ValidateFormAction"
enter_credentials = "src.shared_steps.login_actions:EnterCredentialsAction"
click_login = "src.shared_steps.login_actions:ClickLoginAction"
verify_login = "src.shared_steps.login_actions:VerifyLoginAction"
```

Then load them automatically:

```python
from src.framework.action_registry import ActionRegistry

# Auto-discover from entry points
registry = ActionRegistry.from_entry_points()
```

## Using Custom Actions in Workflows

### In Workflow Steps

```python
async def fill_user_form(self, input_data: FormFillingInput) -> Dict[str, Any]:
    """Fill user form using custom action."""
    # Get action from registry
    FillFormAction = self.action_registry.get("fill_form")
    if not FillFormAction:
        raise WorkflowError(f"Action 'fill_form' not found in registry")
    
    # Instantiate action with workflow context
    action = FillFormAction(self, name="fill_user_form")
    
    # Execute action with run() method
    result = await action.run(
        fields={
            "input[name='first_name']": input_data.first_name,
            "input[name='last_name']": input_data.last_name,
            "input[name='email']": input_data.email,
        },
        wait_ms=5000,
    )
    
    return result
```

### With Dependencies

```python
async def submit_form(self, input_data: FormFillingInput) -> Dict[str, Any]:
    """Submit form after filling (depends on fill_form)."""
    # Get action from registry
    SubmitFormAction = self.action_registry.get("submit_form")
    
    # Create action with dependency on fill_form action
    action = SubmitFormAction(
        self,
        name="submit_form",
        requires=["fill_user_form"],  # Must complete before this
    )
    
    # Execute action
    result = await action.run(submit_button_selector="#submit-btn")
    return result
```

## Error Handling

### Automatic Retry

The framework automatically retries transient errors:

```python
# Example with TimeoutError (transient - will retry)
async def execute(self, **kwargs) -> Any:
    try:
        # This will timeout and retry up to max_retries times
        await page.wait_for_selector(selector, timeout=5000)
    except TimeoutError as e:
        # Classified as transient - framework will retry
        raise TransientError(self.name, f"Timeout: {selector}", cause=e)
```

### Manual Retry Configuration

```python
action = MyCustomAction(
    workflow_context,
    name="my_action",
    max_retries=5,  # Retry up to 5 times instead of default 3
)

result = await action.run(param="value")
```

### Handling Retries in Execute

```python
async def execute(self, **kwargs) -> Any:
    """Execute with built-in retry handling."""
    max_attempts = self.max_retries + 1
    last_error = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            # Your code
            return await self._do_work()
        except TimeoutError as e:
            last_error = e
            if attempt == max_attempts:
                raise TransientError(
                    self.name,
                    f"Failed after {max_attempts} attempts: {str(e)}",
                    cause=e,
                )
            # Will retry
```

## Action Dependencies

### Declaring Dependencies

```python
class ValidateFormAction(Action):
    """Validate form must run after fill_form completes."""
    
    def __init__(self, workflow_context, name=None, **kwargs):
        super().__init__(
            workflow_context,
            name=name or "validate_form",
            requires=["fill_form"],  # Must complete before this
            **kwargs,
        )
    
    async def execute(self, **kwargs) -> Any:
        # At this point, fill_form has completed
        pass
```

### Checking Dependencies

```python
action = MyCustomAction(
    workflow_context,
    requires=["action_a", "action_b"],
)

# Get dependencies
dependencies = action.get_dependencies()  # ["action_a", "action_b"]

# Check specific dependency
depends_on_a = action.has_dependency("action_a")  # True
```

## Examples

### Form Actions

The `FillFormAction` example fills multiple form fields by selector:

**File**: `src/shared_steps/form_actions.py`

```python
class FillFormAction(Action):
    """Fill form fields with provided data."""
    
    async def execute(
        self,
        fields: Dict[str, str],
        wait_ms: int = 5000,
    ) -> Dict[str, Any]:
        """Fill form fields.
        
        Args:
            fields: Dictionary of {selector: value} pairs
            wait_ms: Wait time for elements in milliseconds
        
        Returns:
            Dictionary with filled fields and any errors
        """
        page = self.workflow_context.page
        filled = []
        errors = {}
        
        for selector, value in fields.items():
            try:
                await page.wait_for_selector(selector, timeout=wait_ms)
                await page.fill(selector, value)
                filled.append(selector)
            except TimeoutError as e:
                errors[selector] = f"Timeout: {str(e)}"
                raise TransientError(self.name, str(e), cause=e)
            except Exception as e:
                errors[selector] = str(e)
                raise PermanentError(self.name, str(e), cause=e)
        
        return {
            "fields_filled": filled,
            "total_filled": len(filled),
            "errors": errors,
        }
```

**Usage**:

```python
action = FillFormAction(workflow_context, name="fill_form")
result = await action.run(fields={
    "input[name='username']": "john@example.com",
    "input[name='password']": "secret",
})
```

### Login Actions

The `EnterCredentialsAction` example fills login form from credential store:

**File**: `src/shared_steps/login_actions.py`

```python
class EnterCredentialsAction(Action):
    """Fill login form with stored credentials."""
    
    async def execute(
        self,
        username_selector: str,
        password_selector: str,
        credential_key: str,
    ) -> Dict[str, Any]:
        """Enter credentials from secure store.
        
        Args:
            username_selector: CSS selector for username field
            password_selector: CSS selector for password field
            credential_key: Key to look up in credential store
        
        Returns:
            Status of credential entry
        """
        # Get credentials from secure store
        page = self.workflow_context.page
        credential_mgr = self.workflow_context.credential_manager
        
        creds = credential_mgr.get_credentials(credential_key)
        
        # Fill form
        try:
            await page.fill(username_selector, creds.username)
            await page.fill(password_selector, creds.password)
            return {"status": "success"}
        except Exception as e:
            raise PermanentError(self.name, str(e), cause=e)
```

**Usage**:

```python
action = EnterCredentialsAction(
    workflow_context,
    name="enter_credentials",
)
result = await action.run(
    username_selector="input[name='user']",
    password_selector="input[name='pass']",
    credential_key="my_app_login",
)
```

### Custom Action Example

Here's a complete example of a custom action that takes screenshots:

```python
"""Screenshot action."""

from typing import Any, Dict
from pathlib import Path
from datetime import datetime
from src.framework.action import Action
from src.framework.errors import PermanentError
from src.utils.logging import setup_logger

logger = setup_logger(__name__)


class TakeScreenshotAction(Action):
    """Take a screenshot of the current page."""
    
    async def execute(
        self,
        filename: str = None,
        output_dir: str = "data/artifacts",
    ) -> Dict[str, Any]:
        """Take screenshot.
        
        Args:
            filename: Name for screenshot file (auto-generated if not provided)
            output_dir: Directory to save screenshot
        
        Returns:
            Dictionary with path to saved screenshot
        """
        try:
            page = self.workflow_context.page
            
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            # Create output directory if needed
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Take screenshot
            filepath = output_path / filename
            await page.screenshot(path=str(filepath))
            
            logger.info(f"Screenshot saved: {filepath}")
            
            return {
                "status": "success",
                "path": str(filepath),
                "filename": filename,
            }
            
        except Exception as e:
            raise PermanentError(
                self.name,
                f"Failed to take screenshot: {str(e)}",
                cause=e,
            )


class SavePageAsPDFAction(Action):
    """Save current page as PDF via print command."""
    
    async def execute(
        self,
        filename: str = None,
        output_dir: str = "data/artifacts",
    ) -> Dict[str, Any]:
        """Save page as PDF.
        
        Args:
            filename: Name for PDF file (auto-generated if not provided)
            output_dir: Directory to save PDF
        
        Returns:
            Dictionary with path to saved PDF
        """
        try:
            page = self.workflow_context.page
            
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"page_{timestamp}.pdf"
            
            # Create output directory if needed
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Save as PDF
            filepath = output_path / filename
            await page.pdf(path=str(filepath))
            
            logger.info(f"PDF saved: {filepath}")
            
            return {
                "status": "success",
                "path": str(filepath),
                "filename": filename,
            }
            
        except Exception as e:
            raise PermanentError(
                self.name,
                f"Failed to save PDF: {str(e)}",
                cause=e,
            )
```

**Register in pyproject.toml**:

```toml
[project.entry-points."playwright.actions"]
take_screenshot = "src.shared_steps.screenshot_actions:TakeScreenshotAction"
save_pdf = "src.shared_steps.screenshot_actions:SavePageAsPDFAction"
```

**Use in workflow**:

```python
async def capture_page(self, input_data) -> Dict[str, Any]:
    """Capture page and save as PDF."""
    # Take screenshot
    screenshot_action = self.action_registry.get("take_screenshot")
    action = screenshot_action(self, name="take_screenshot")
    await action.run(filename="form_filled.png")
    
    # Save as PDF
    pdf_action = self.action_registry.get("save_pdf")
    action = pdf_action(self, name="save_pdf")
    result = await action.run(filename="form_filled.pdf")
    
    return result
```

## Best Practices

### 1. Make Actions Focused

Keep actions small and focused on a single task:

```python
# Good - focused action
class FillUsernameFieldAction(Action):
    async def execute(self, value: str) -> Dict[str, Any]:
        await self.workflow_context.page.fill("input[name='username']", value)
        return {"status": "success"}

# Less ideal - too much responsibility
class CompleteLoginAction(Action):
    async def execute(self, username: str, password: str, ...) -> Dict[str, Any]:
        # Too many concerns in one action
        pass
```

### 2. Use Descriptive Names

Action names should clearly describe what they do:

```python
# Good
registry.register(FillFormAction, name="fill_form")
registry.register(SubmitFormAction, name="submit_form")
registry.register(ValidateFormAction, name="validate_form")

# Less ideal
registry.register(FormAction, name="action1")
registry.register(FormAction2, name="action2")
```

### 3. Document Parameters

Clearly document action parameters with type hints and docstrings:

```python
async def execute(
    self,
    fields: Dict[str, str],
    wait_ms: int = 5000,
    skip_hidden: bool = True,
) -> Dict[str, Any]:
    """Fill form fields.
    
    Args:
        fields: Dictionary of {selector: value} pairs
        wait_ms: Wait time for elements in milliseconds
        skip_hidden: Skip hidden elements
    
    Returns:
        Dictionary with filled fields and errors
    """
```

### 4. Handle Errors Appropriately

Classify errors correctly to enable proper retry logic:

```python
# Transient errors (will retry)
- TimeoutError
- ConnectionError
- NetworkError
- TemporaryFileNotFoundError

# Permanent errors (won't retry)
- ValueError (invalid input)
- TypeError (wrong type)
- KeyError (missing data)
- SelectorNotFoundError (invalid selector)
```

### 5. Log Important Events

Use the logger to track action execution:

```python
logger.debug(f"Filling {len(fields)} fields")
logger.info(f"Successfully filled {len(filled)} fields")
logger.warning(f"Timeout on selector: {selector}")
logger.error(f"Failed to fill form: {error_msg}")
```

### 6. Test Actions Independently

Create unit tests for your actions:

```python
@pytest.mark.asyncio
async def test_fill_form_action():
    """Test FillFormAction with mock workflow."""
    # Mock workflow context
    mock_workflow = AsyncMock()
    mock_page = AsyncMock()
    mock_workflow.page = mock_page
    
    # Create action
    action = FillFormAction(mock_workflow, name="test_fill")
    
    # Execute
    result = await action.run(fields={
        "input[name='user']": "john",
    })
    
    # Assert
    assert result["status"] == "success"
    mock_page.fill.assert_called_once()
```

## Troubleshooting

### Action Not Found in Registry

```python
# Error: ValueError: Action 'my_action' not found in registry

# Solution: Ensure action is registered
registry.register(MyAction, name="my_action")

# Or check if entry point is correct in pyproject.toml
[project.entry-points."playwright.actions"]
my_action = "path.to.module:MyAction"  # Check path is correct
```

### Transient Error Not Retrying

```python
# Problem: Action fails but doesn't retry

# Solution: Make sure to raise TransientError, not generic Exception
async def execute(self, **kwargs):
    try:
        await page.wait_for_selector(selector, timeout=5000)
    except TimeoutError as e:
        # Correct - will retry
        raise TransientError(self.name, str(e), cause=e)
        
        # Wrong - won't retry (permanent error)
        # raise Exception(str(e))
```

### Action Hangs on Retry

```python
# Problem: Action retries too many times

# Solution: Use appropriate retry configuration
action = MyAction(
    workflow_context,
    max_retries=3,  # Lower retry count
)

# Or detect infinite retry loop and raise PermanentError
async def execute(self, **kwargs):
    # Detect problem and raise permanent error
    if some_bad_condition:
        raise PermanentError(self.name, "Cannot proceed")
```

## See Also

- [Workflow Base Class](./workflow-base.md)
- [Checkpoint Protocol](./checkpoint-protocol.md)
- [Error Handling Guide](./error-handling.md)
- [Action Registry API](./action-registry-api.md)
