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
    username: str          # Username to use for login
    password: str          # Password to use for login
    timeout_seconds: int   # Maximum seconds to wait for each step (default: 10)
```

### Output: LoginOutput

```python
from dataclasses import dataclass

@dataclass
class LoginOutput:
    """Output from LoginWorkflow execution."""
    success: bool          # True if login completed successfully
    user_name: str         # Username of logged-in user (from dashboard)
    session_id: str        # Session identifier (from cookies)
    redirect_url: str      # URL of final page after login
```

## Usage Examples

### Basic Usage

```python
import asyncio
from src.workflows.login_workflow import LoginWorkflow, LoginInput

async def main():
    # Create workflow instance
    workflow = LoginWorkflow(base_url="https://app.example.com")
    
    # Set input parameters
    workflow.input = LoginInput(
        username="user@example.com",
        password="secure_password",
        timeout_seconds=10
    )
    
    # Run the workflow
    result = await workflow.run()
    
    # Handle results
    if result.success:
        print(f"Login successful! User: {result.user_name}")
        print(f"Session ID: {result.session_id}")
    else:
        print("Login failed!")

asyncio.run(main())
```

### Using with CLI

```bash
# Run the workflow via CLI
python3 -m src.cli.workflow_runner \
  --workflow-type LoginWorkflow \
  --base-url "https://app.example.com" \
  --input '{"username": "user@example.com", "password": "secure_password", "timeout_seconds": 10}' \
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
      "username": "user@example.com",
      "password": "secure_password",
      "timeout_seconds": 10
    }
  },
  "id": "req-001"
}
```

## Error Handling

The LoginWorkflow handles various error scenarios:

### Transient Errors (Auto-Retry)
- Network timeout during page load
- Temporary server unavailability (5xx errors)
- Browser connection issues

These errors trigger automatic retry with exponential backoff (default: 3 attempts).

### Permanent Errors (Checkpoint Escalation)
- Invalid credentials (401 response)
- Page element not found (field missing from form)
- Page load timeout after retries
- Session expired during execution

These errors escalate to a checkpoint for human/agent decision.

### Error Recovery

If an error occurs during workflow execution:

1. **Transient errors**: Framework automatically retries up to 3 times with exponential backoff
2. **Permanent errors**: Framework pauses execution and creates a checkpoint
3. **Checkpoint resolution**: Human/agent reviews error and decides to:
   - **Proceed**: Retry from checkpoint (useful for network issues)
   - **Cancel**: Cancel workflow execution
   - **Modify input**: Provide corrected credentials and retry

## State Management and Persistence

### Execution State

The workflow automatically saves its execution state after each step:

```
data/executions/{execution_id}.json
```

This includes:
- Current execution status (running, paused, completed, failed)
- All completed steps and their outputs
- Any active checkpoints
- Timing information
- Error details

### Resume from Checkpoint

If a workflow is paused at a checkpoint:

1. User/agent resolves the checkpoint with a decision
2. Framework reloads execution state from disk
3. Workflow resumes from the paused step
4. All previous step outputs are available for reference

Example resumption:

```python
# Resolve the checkpoint
workflow.resolve_checkpoint(execution_id, decision={
    "value": "proceed"  # or "cancel", or provide new input
})

# Workflow automatically resumes from where it paused
```

## Logging

All workflow execution is logged to:

```
data/logs/{execution_id}.log
```

Logs are formatted as JSON lines (one JSON object per line) for easy parsing and analysis:

```json
{"timestamp": "2024-11-02T12:00:00.000Z", "level": "INFO", "step": "navigate_to_login", "message": "Starting step", "action": "navigate"}
{"timestamp": "2024-11-02T12:00:01.000Z", "level": "INFO", "step": "navigate_to_login", "message": "Step completed", "duration_ms": 1200}
{"timestamp": "2024-11-02T12:00:02.000Z", "level": "INFO", "step": "fill_username", "message": "Starting step"}
```

## Testing

The LoginWorkflow includes comprehensive unit and integration tests:

### Unit Tests
- **File**: `tests/workflows/unit/test_login_workflow.py`
- **Coverage**: 
  - Step execution order
  - Input validation
  - Error handling scenarios
  - Retry behavior
  - State persistence

### Integration Tests
- **File**: `tests/workflows/integration/test_login_workflow_integration.py`
- **Coverage**:
  - Full workflow with mock server
  - Concurrent workflow execution
  - State persistence and recovery
  - End-to-end error scenarios

### Running Tests

```bash
# Run only LoginWorkflow tests
uv run pytest tests/workflows/unit/test_login_workflow.py -v

# Run integration tests
uv run pytest tests/workflows/integration/test_login_workflow_integration.py -v

# Run all tests with coverage
uv run pytest tests/ --cov=src --cov-report=html
```

## Advanced Topics

### Customizing the Workflow

To create a similar workflow for a different application:

1. Extend the `Workflow` base class
2. Define your own `Input` and `Output` dataclasses
3. Implement workflow steps using the `@step` decorator
4. Implement the `run()` method to orchestrate steps

```python
from src.framework.workflow import Workflow, step
from dataclasses import dataclass

@dataclass
class CustomInput:
    # Your input fields
    pass

@dataclass
class CustomOutput:
    # Your output fields
    pass

class CustomWorkflow(Workflow):
    def __init__(self, base_url: str):
        super().__init__("CustomWorkflow", base_url)
    
    @step
    async def step1(self):
        # Implement step logic
        pass
    
    async def run(self) -> CustomOutput:
        # Orchestrate steps
        await self.step1()
        # Return output
        return CustomOutput()
```

### Adding Checkpoints

To add a human-in-the-loop checkpoint during workflow execution:

```python
@step
async def approve_action(self):
    """Wait for human approval before proceeding."""
    decision = await self.checkpoint(
        question="Approve this action?",
        options=["proceed", "cancel"]
    )
    
    if decision["value"] == "cancel":
        raise WorkflowCancelled("User cancelled the workflow")
```

## Troubleshooting

### "Selector not found" Error
- Verify the web page has fully loaded before the step executes
- Check that element selectors match the current page structure
- Increase the `timeout_seconds` parameter

### "Invalid credentials" Error
- Verify username and password are correct
- Check if the target application is available
- Verify the login form structure hasn't changed

### "Workflow timeout" Error
- Increase the `timeout_seconds` parameter in LoginInput
- Check network connectivity to the target application
- Verify browser process is running correctly

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
