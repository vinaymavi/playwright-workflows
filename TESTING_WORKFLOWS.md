# Testing Workflows - Quick Start Guide

## Prerequisites
Ensure Playwright browsers are installed:
```bash
uv run playwright install chromium
```

## Running a Workflow

### 1. Login Workflow Example
The example login workflow uses these selectors:
- `#login-form` - Login form container
- `#username` - Username input field
- `#password` - Password input field
- `#submit-btn` - Submit button
- `#user-info` - Dashboard indicator (after login)

### 2. Test with Local Server
For testing locally, you need a website/application with the above selectors.

**Option A: Create a test HTML page**
```bash
# Create data/test_login.html with:
<form id="login-form">
  <input id="username" type="text" placeholder="Username">
  <input id="password" type="password" placeholder="Password">
  <button id="submit-btn" type="submit">Login</button>
</form>
<div id="user-info" style="display:none;">Welcome User</div>
```

**Option B: Use any real website with matching selectors**

### 3. Run Workflow
```bash
# Format: python -m src.cli.workflow_runner <workflow_type> --input '<JSON>'

uv run python -m src.cli.workflow_runner login \
    --input '{"url":"http://localhost:8000/login","username":"testuser","password":"testpass"}'
```

### 4. Output Formats

**JSON (default):**
```bash
uv run python -m src.cli.workflow_runner login \
    --input '{"url":"http://localhost:8000","username":"test","password":"pass"}' \
    --output-format json
```

**Text output:**
```bash
uv run python -m src.cli.workflow_runner login \
    --input '{"url":"http://localhost:8000","username":"test","password":"pass"}' \
    --output-format text
```

**With logs:**
```bash
uv run python -m src.cli.workflow_runner login \
    --input '{"url":"http://localhost:8000","username":"test","password":"pass"}' \
    --log-dir data/logs
```

## Workflow Execution Flow

1. **Browser Launch**: Chromium headless browser starts
2. **Session Restoration**: SessionManager checks for saved session (cookies, etc.)
3. **Page Creation**: New page instance created
4. **Navigation**: First step navigates to specified URL
5. **Step Execution**: Each workflow step executes with retries
6. **Checkpoint**: If workflow has checkpoints, it waits for agent response
7. **Completion**: Returns success/failure with results

## Troubleshooting

### Error: "Page not initialized"
✅ **FIXED** - Browser initialization now happens before workflow execution

### Error: "Selector not found"
The website doesn't have the expected selector. Check:
- Is the URL correct?
- Does the page have `#login-form`?
- Is the page fully loaded? (workflow waits for "load" event)

### Error: "Executable doesn't exist"
Install Playwright browsers:
```bash
uv run playwright install chromium
```

### Browser doesn't close
Workflows use async context managers for proper cleanup. If a workflow hangs:
```bash
# Kill the process
pkill -f "playwright"
```

## Logging

Logs are structured JSON format with:
- timestamp (ISO format)
- level (info, warning, error)
- message
- logger (module name)
- execution_id (traces which workflow execution)

View logs:
```bash
tail -f data/logs/login.log
```

Parse logs:
```bash
cat data/logs/login.log | jq '.level'
```

## Workflow State

Execution state is saved to:
```
data/executions/{execution_id}.json
```

This includes:
- Execution ID and state
- Input parameters
- Step results and outputs
- Checkpoint data
- Artifacts (screenshots, PDFs)
- Timestamps

## Creating Custom Workflows

To add a new workflow:

1. **Create workflow class** in `src/workflows/`
```python
from src.framework import Workflow, step

class MyWorkflow(Workflow):
    workflow_type = "my_workflow"
    
    async def run(self, input_data):
        await self.navigate("https://example.com")
        # ... workflow logic
        return {"success": True}
```

2. **Register in CLI** - Add to `workflow_runner.py`:
```python
def _get_workflow(self):
    if self.workflow_type == "my_workflow":
        return MyWorkflow()
```

3. **Run it**:
```bash
uv run python -m src.cli.workflow_runner my_workflow \
    --input '{"url":"https://example.com"}'
```

## API Reference

### Workflow Methods
- `navigate(url)` - Navigate to URL
- `click(selector)` - Click element
- `fill(selector, text)` - Fill form field
- `select(selector, value)` - Select dropdown
- `get_text(selector)` - Extract text
- `wait_for_selector(selector)` - Wait for element
- `take_screenshot(name)` - Capture screenshot
- `checkpoint(question, timeout_seconds)` - Wait for agent decision

### CLI Arguments
- `workflow_type` - Type of workflow (positional)
- `--input, -i` - JSON input parameters (required)
- `--output-format, -f` - json or text (default: json)
- `--log-dir, -l` - Log directory (default: data/logs)

## Examples

### Login and Take Screenshot
```python
@step(name="Take Screenshot After Login")
async def take_screenshot(self):
    path = await self.take_screenshot("after_login.png")
    print(f"Screenshot saved: {path}")
```

### With Checkpoint
```python
@step(name="Approve Form Submission")
async def approve_submission(self):
    decision = await self.checkpoint(
        question=CheckpointQuestion(
            question_text="Ready to submit form?",
            options=["proceed", "cancel"]
        ),
        timeout_seconds=300
    )
    if decision.choice == "cancel":
        raise WorkflowError("User cancelled")
```

### Error Handling
```python
try:
    await self.click("#button")
except WorkflowError as e:
    self.logger.error(f"Failed: {e}")
    # Handle error, retry, or propagate
```
