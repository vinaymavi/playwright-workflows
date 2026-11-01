# LoginWorkflow Example

## Overview

The `LoginWorkflow` is a complete example of a web automation workflow that demonstrates the core capabilities of the Playwright Workflow Orchestration Framework. It automates a multi-step login process for a web application, showcasing step-based execution, error handling, and structured output.

## Features

- **Step-based execution**: Each workflow action (navigate, fill, click, wait) is a distinct step
- **Error handling**: Built-in error handling for common login failures (timeout, invalid credentials)
- **Structured input/output**: Strongly-typed input and output using Pydantic dataclasses
- **Logging**: Comprehensive JSON-formatted logging for debugging and audit trails
- **State management**: Automatic execution state persistence for pause/resume capabilities

## Workflow Steps

The LoginWorkflow executes the following steps in sequence:

### 1. Navigate to Login Page
- **Purpose**: Load the login page URL in the browser
- **Actions**:
  - Navigate to the base URL
  - Wait for the login form to become visible
- **Error handling**: Raises `PermanentError` if page fails to load
- **Output**: Page is loaded and ready for input

### 2. Fill Username
- **Purpose**: Enter the username into the login form
- **Actions**:
  - Locate the username input field
  - Clear any existing text
  - Type the username from input
- **Error handling**: Raises `PermanentError` if field not found
- **Output**: Username field contains user input

### 3. Fill Password
- **Purpose**: Enter the password into the login form
- **Actions**:
  - Locate the password input field
  - Clear any existing text
  - Type the password from input
- **Error handling**: Raises `PermanentError` if field not found
- **Output**: Password field contains user input (masked in UI)

### 4. Click Submit
- **Purpose**: Submit the login form
- **Actions**:
  - Locate the submit button
  - Click the button
  - Wait for form submission to complete
- **Error handling**: 
  - Raises `PermanentError` for invalid credentials (401 response)
  - Raises `TransientError` for temporary server issues (retry attempts)
- **Output**: Form is submitted and page navigation begins

### 5. Wait for Dashboard
- **Purpose**: Verify successful login by waiting for dashboard page
- **Actions**:
  - Wait for dashboard-specific element to appear
  - Extract user information from dashboard
  - Extract session ID from cookies
- **Error handling**: 
  - Raises `PermanentError` if dashboard never appears (timeout)
- **Output**: Dashboard is loaded and user information is extracted

## Input and Output

### Input: LoginInput

```python
from dataclasses import dataclass

@dataclass
class LoginInput:
    """Input parameters for LoginWorkflow."""
    url: str               # URL of the login page to navigate to
    username: str          # Username to use for login
    password: str          # Password to use for login
```

### Output: LoginOutput

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class LoginOutput:
    """Output from LoginWorkflow execution."""
    success: bool              # True if login completed successfully
    message: str               # Status message describing the result
    dashboard_url: Optional[str]  # URL of the dashboard after successful login (None if failed)
    session_id: Optional[str]     # Session identifier from cookies (None if login failed)
```

## Usage Examples

### Basic Usage

```python
import asyncio
from src.workflows.login_workflow import LoginWorkflow, LoginInput
from playwright.async_api import async_playwright

async def main():
    # Create workflow instance
    workflow = LoginWorkflow(base_url="https://app.example.com")
    
    # Initialize browser and page (in real usage, done by framework)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        workflow._page = page
        
        # Create input parameters
        input_data = LoginInput(
            url="https://app.example.com/login",
            username="user@example.com",
            password="secure_password"
        )
        
        # Run the workflow
        result = await workflow.run(input_data)
        
        # Handle results
        if result.success:
            print(f"Login successful!")
            print(f"Dashboard URL: {result.dashboard_url}")
            print(f"Session ID: {result.session_id}")
        else:
            print(f"Login failed: {result.message}")
        
        await browser.close()

asyncio.run(main())
```

### Using with Framework ExecutionContext

```python
import asyncio
from src.framework.execution_context import ExecutionContext
from src.workflows.login_workflow import LoginWorkflow, LoginInput

async def main():
    # Create execution context (handles browser lifecycle)
    context = ExecutionContext()
    
    # Create workflow
    workflow = LoginWorkflow(base_url="https://app.example.com")
    
    # Initialize browser through context
    await context.initialize()
    workflow._page = context.page
    
    # Run workflow
    input_data = LoginInput(
        url="https://app.example.com/login",
        username="user@example.com",
        password="secure_password"
    )
    
    result = await workflow.run(input_data)
    print(f"Result: {result}")
    
    # Cleanup
    await context.cleanup()

asyncio.run(main())
```

### Using with CLI

```bash
# Run the workflow via CLI (when available)
python3 -m src.cli.workflow_runner \
  --workflow-type LoginWorkflow \
  --base-url "https://app.example.com" \
  --input '{"url": "https://app.example.com/login", "username": "user@example.com", "password": "secure_password"}' \
  --output-format json
```

### Integration with MCP Server

When running within the MCP Server context, the workflow can be invoked through the workflow execution endpoint:

```python
# Example MCP request
{
  "jsonrpc": "2.0",
  "method": "execute_workflow",
  "params": {
    "workflow_type": "LoginWorkflow",
    "base_url": "https://app.example.com",
    "input": {
      "url": "https://app.example.com/login",
      "username": "user@example.com",
      "password": "secure_password"
    }
  },
  "id": "req-001"
}
```

## Error Handling

The LoginWorkflow handles various error scenarios:

- **Page Load Failure**: Raises `PermanentError` if the login page doesn't load
- **Invalid Credentials**: Raises `PermanentError` if credentials are rejected (401 response)
- **Form Not Found**: Raises `PermanentError` if form elements are not found
- **Timeout**: Raises `PermanentError` if dashboard doesn't appear within timeout
- **Transient Network Errors**: Raises `TransientError` for temporary network issues (can be retried)

## Testing

The LoginWorkflow includes comprehensive tests:

- **Unit Tests**: Test individual steps with mocked browser operations
- **Integration Tests**: Test framework integration including state persistence and concurrent execution
- **Test Data**: MockPage fixture simulates browser operations without requiring real browser

Run tests with:

```bash
# Unit tests
pytest tests/workflows/unit/test_login_workflow.py -v

# Integration tests
pytest tests/workflows/integration/test_login_workflow_integration.py -v

# All workflow tests
pytest tests/workflows/ -v
```

## Performance Considerations

- **Browser startup**: ~3-5 seconds
- **Per-step execution**: ~1-2 seconds
- **Full login workflow**: ~10-15 seconds (varies by network)
- **Concurrent executions**: Limited by system resources (default: 5 concurrent)

## Security Notes

- Credentials are NOT stored in logs
- Session IDs are stored in-memory and in encrypted state files
- Always use HTTPS for real applications
- Consider using credential management systems (env vars, vaults)

## Related Documentation

- [Workflow Base Class](../framework/workflow.md)
- [Step Decorator and Execution Flow](../framework/step_decorator.md)
- [Checkpoint Protocol](../checkpoint-protocol.md)
- [Error Handling and Recovery](../framework/error_handling.md)
- [State Management and Persistence](../framework/state_management.md)
