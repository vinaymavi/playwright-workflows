# Logging and Debugging Guide

## Overview

The Playwright Workflows framework provides structured JSON logging for all workflow executions. This guide explains how to configure logging, query logs, and debug failed workflows.

## Structured Logging Format

All logs are written in JSON format for easy parsing and querying:

```json
{
  "timestamp": "2024-01-15T10:05:23.456Z",
  "execution_id": "exec-123abc",
  "level": "INFO",
  "message": "Step execution completed",
  "step": "login",
  "component": "workflow",
  "duration_ms": 2340,
  "metadata": {
    "action": "LoginAction",
    "status": "success",
    "page_url": "https://example.com/login"
  }
}
```

### Log Levels

| Level | Usage | Severity |
|-------|-------|----------|
| DEBUG | Detailed diagnostic information | Lowest |
| INFO | General workflow progress | ↓ |
| WARNING | Potential issues, non-fatal errors | ↓ |
| ERROR | Action failed, requires retry/intervention | ↓ |
| CRITICAL | Workflow terminated, unrecoverable | Highest |

### Standard Fields

Every log entry contains:
- `timestamp`: ISO 8601 timestamp (UTC)
- `execution_id`: Unique execution identifier
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `message`: Human-readable message
- `component`: Source component (workflow, action, mcp_server, etc.)
- `metadata`: Component-specific data (optional)

## Log Configuration

### Configuration Options

```python
from playwright_workflows.logging import LogConfig

config = LogConfig(
    level='INFO',                              # Minimum log level
    format='json',                             # json or text
    output_file='data/executions/{id}.log',   # Log file path (supports {id})
    structured=True,                           # Structured JSON format
    include_metadata=True,                     # Include extra metadata
    max_log_size_mb=10,                        # Rotate logs at this size
    backup_count=5,                            # Keep 5 backup logs
    colored_output=False                       # Terminal colors (text format only)
)

workflow.logging.configure(config)
```

### Per-Workflow Configuration

```python
class MyWorkflow(Workflow):
    class Config:
        log_level = 'DEBUG'
        log_output_file = 'my_workflow.log'
        include_step_metadata = True
        include_page_state = True
```

### Environment Variables

```bash
# Set log level via environment
export WORKFLOW_LOG_LEVEL=DEBUG

# Set log file location
export WORKFLOW_LOG_FILE=data/logs/{execution_id}.log

# Enable structured logging
export WORKFLOW_STRUCTURED_LOGGING=1
```

## Log Structure by Component

### Workflow Logs

**Lifecycle events**:
```json
{
  "timestamp": "2024-01-15T10:00:00Z",
  "execution_id": "exec-123",
  "level": "INFO",
  "message": "Workflow execution started",
  "component": "workflow",
  "metadata": {
    "workflow_class": "LoginWorkflow",
    "workflow_file": "workflows/login.py"
  }
}
```

**Step execution**:
```json
{
  "timestamp": "2024-01-15T10:05:00Z",
  "execution_id": "exec-123",
  "level": "INFO",
  "message": "Step execution started",
  "component": "workflow",
  "step": "login",
  "metadata": {
    "step_number": 2,
    "total_steps": 5,
    "action": "LoginAction"
  }
}
```

**Checkpoint**:
```json
{
  "timestamp": "2024-01-15T10:06:00Z",
  "execution_id": "exec-123",
  "level": "INFO",
  "message": "Checkpoint reached",
  "component": "workflow",
  "step": "login",
  "metadata": {
    "reason": "awaiting_user_input",
    "data": {
      "user_prompt": "Enter MFA code",
      "page_url": "https://example.com/mfa"
    }
  }
}
```

### Action Logs

**Action execution**:
```json
{
  "timestamp": "2024-01-15T10:05:10Z",
  "execution_id": "exec-123",
  "level": "INFO",
  "message": "Action execution started",
  "component": "action",
  "step": "login",
  "metadata": {
    "action": "LoginAction",
    "parameters": {
      "username": "user@example.com"
    }
  }
}
```

**Action success**:
```json
{
  "timestamp": "2024-01-15T10:05:23Z",
  "execution_id": "exec-123",
  "level": "INFO",
  "message": "Action execution completed",
  "component": "action",
  "step": "login",
  "duration_ms": 13500,
  "metadata": {
    "action": "LoginAction",
    "status": "success",
    "result": {
      "authenticated": true,
      "user_id": "user123"
    }
  }
}
```

**Action failure**:
```json
{
  "timestamp": "2024-01-15T10:05:45Z",
  "execution_id": "exec-123",
  "level": "ERROR",
  "message": "Action execution failed",
  "component": "action",
  "step": "login",
  "metadata": {
    "action": "LoginAction",
    "status": "failed",
    "error": {
      "type": "AuthenticationError",
      "message": "Invalid credentials",
      "retry_count": 3,
      "exception_traceback": "..."
    }
  }
}
```

### Browser/Page Logs

**Navigation**:
```json
{
  "timestamp": "2024-01-15T10:05:00Z",
  "execution_id": "exec-123",
  "level": "DEBUG",
  "message": "Page navigation",
  "component": "browser",
  "metadata": {
    "action": "goto",
    "url": "https://example.com/login",
    "wait_until": "networkidle",
    "duration_ms": 2340
  }
}
```

**Element interaction**:
```json
{
  "timestamp": "2024-01-15T10:05:05Z",
  "execution_id": "exec-123",
  "level": "DEBUG",
  "message": "Element interaction",
  "component": "browser",
  "metadata": {
    "action": "click",
    "selector": "button#login",
    "element_found": true,
    "duration_ms": 50
  }
}
```

## Querying Logs

### Using Execution API

```python
from playwright_workflows.execution import ExecutionManager

manager = ExecutionManager()
execution = manager.get_execution('exec-123')

# Get all logs
all_logs = execution.get_logs()

# Filter by level
errors = execution.get_logs(level='ERROR')
warnings = execution.get_logs(level='WARNING')

# Filter by component
action_logs = execution.get_logs(component='action')
browser_logs = execution.get_logs(component='browser')

# Filter by step
login_logs = execution.get_logs(step='login')

# Filter by time range
from datetime import datetime, timedelta
start = datetime.now() - timedelta(minutes=5)
end = datetime.now()
recent_logs = execution.get_logs(start_time=start, end_time=end)

# Combine filters
failed_login_logs = execution.get_logs(
    step='login',
    level='ERROR',
    component='action'
)
```

### Querying with MCP Server

```python
# Via MCP tool: get_execution_logs
logs = mcp_client.call('get_execution_logs', {
    'execution_id': 'exec-123',
    'level': 'ERROR',
    'step': 'login',
    'limit': 50
})
```

### Command-Line Querying

```bash
# View all logs for execution
python -m playwright_workflows logs exec-123

# Filter by level
python -m playwright_workflows logs exec-123 --level ERROR

# Filter by step
python -m playwright_workflows logs exec-123 --step login

# Filter by time
python -m playwright_workflows logs exec-123 --since 2024-01-15T10:00:00

# Tail logs (live)
python -m playwright_workflows logs exec-123 --tail

# Format output
python -m playwright_workflows logs exec-123 --format table
python -m playwright_workflows logs exec-123 --format json
```

## Debugging Failed Workflows

### Step 1: Identify the Failure

```python
execution = manager.get_execution('exec-123')

# Check execution status
print(f"Status: {execution.status}")
print(f"Current step: {execution.current_step}")
print(f"Error: {execution.error}")
```

### Step 2: Review Error Logs

```python
# Get all error-level logs
error_logs = execution.get_logs(level='ERROR')

for log in error_logs:
    print(f"\n{log['timestamp']} - {log['message']}")
    print(f"Step: {log.get('step', 'N/A')}")
    print(f"Details: {log.get('metadata', {})}")
```

### Step 3: Check Screenshot on Error

```python
# Get artifact captured at error
artifacts = execution.get_artifacts()
error_screenshots = [a for a in artifacts if 'error' in a['name']]

for artifact in error_screenshots:
    print(f"Screenshot: {artifact['name']}")
    print(f"Time: {artifact['created_at']}")
    print(f"Path: {artifact['file_path']}")
```

### Step 4: Review Step-by-Step Logs

```python
# Get logs for the failing step
failing_step = execution.current_step
step_logs = execution.get_logs(step=failing_step)

# Print chronological log
for log in sorted(step_logs, key=lambda l: l['timestamp']):
    if log['level'] != 'DEBUG':
        print(f"[{log['level']}] {log['message']}")
```

### Step 5: Inspect Page State

```python
# Get page state from checkpoint
checkpoint_data = execution.checkpoint_data
if checkpoint_data:
    print(f"Page URL: {checkpoint_data.get('page_url')}")
    print(f"Page title: {checkpoint_data.get('page_title')}")
    print(f"Cookies: {checkpoint_data.get('cookies')}")
```

## Common Debugging Scenarios

### Scenario 1: Element Not Found

**Symptoms**:
- ElementNotFoundError in logs
- Step times out
- Screenshot shows different page layout

**Debugging**:
```python
# Get the specific log
error_logs = execution.get_logs(
    step='fill_form',
    error_type='ElementNotFoundError'
)

for log in error_logs:
    selector = log['metadata'].get('selector')
    print(f"Expected selector: {selector}")

# Check screenshot
artifacts = execution.get_artifacts()
error_shot = [a for a in artifacts 
              if 'error' in a['name'] and 'fill' in a['name']][0]
print(f"Review: {error_shot['file_path']}")

# Fix and resume
execution.resume(state_patch={
    'steps_data': {'fill_form': {'selector': '.new-selector'}}
})
```

### Scenario 2: Authentication Timeout

**Symptoms**:
- TimeoutError on login step
- RateLimitError (HTTP 429)
- Connection refused errors

**Debugging**:
```python
# Check network logs
network_logs = execution.get_logs(component='browser')
for log in network_logs:
    if 'status' in str(log.get('metadata', {})):
        print(log)

# Check retry history
login_logs = execution.get_logs(step='login')
retry_count = sum(1 for l in login_logs 
                  if 'retry' in l.get('message', '').lower())
print(f"Retries: {retry_count}")

# Resolution options
if any('429' in str(l) for l in login_logs):
    print("Rate limited - increase retry delay")
```

### Scenario 3: Memory or Performance Issues

**Symptoms**:
- High duration_ms values
- Process becomes slow
- Out of memory error

**Debugging**:
```python
# Check step durations
logs = execution.get_logs()
for log in logs:
    if 'duration_ms' in log:
        duration = log['duration_ms']
        if duration > 5000:  # >5 seconds
            print(f"{log['step']}: {duration}ms")

# Check resource usage
artifacts = execution.get_artifacts()
total_size = sum(a['file_size_bytes'] for a in artifacts)
print(f"Total artifacts: {total_size / 1024 / 1024:.1f}MB")
```

### Scenario 4: Inconsistent Results

**Symptoms**:
- Same workflow succeeds sometimes, fails other times
- Random element not found
- Intermittent timeouts

**Debugging**:
```python
# Compare multiple executions
executions = manager.list_executions(workflow_class='LoginWorkflow')

for exec in executions[-5:]:  # Last 5
    logs = exec.get_logs(level='WARNING')
    print(f"{exec.id}: {len(logs)} warnings, status={exec.status}")

# Look for patterns
error_patterns = {}
for exec in executions:
    errors = exec.get_logs(level='ERROR')
    for error in errors:
        error_type = error['metadata'].get('error', {}).get('type')
        error_patterns[error_type] = error_patterns.get(error_type, 0) + 1

print("Error patterns:", error_patterns)
```

## Best Practices

1. **Check Logs First**: Always review logs before debugging
   ```python
   errors = execution.get_logs(level='ERROR')
   print(f"Found {len(errors)} errors - check details")
   ```

2. **Enable Debug Logging During Troubleshooting**:
   ```python
   workflow.logging.set_level('DEBUG')
   # More detailed information
   ```

3. **Capture Screenshots on Error**: Automatically enabled
   ```python
   # Check error screenshots for visual clues
   error_artifacts = execution.get_artifacts(type='screenshot')
   ```

4. **Correlate Logs with State**: Use execution_id to tie everything together
   ```python
   # All logs, state changes, artifacts share execution_id
   execution = manager.get_execution('exec-123')
   ```

5. **Save Logs for Analysis**: Export and analyze locally
   ```bash
   python -m playwright_workflows logs exec-123 --export logs.json
   # Analyze in external tools (ELK, Splunk, etc.)
   ```

## Integration with External Logging

### Ship Logs to ELK Stack

```python
import logging
from pythonjsonlogger import jsonlogger

# Configure JSON logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)
```

### Ship Logs to Datadog

```python
from datadog import initialize, api
from datadog.api import logs

options = {
    'api_key': 'your_api_key',
    'app_key': 'your_app_key'
}
initialize(**options)

# Logs automatically sent if using JSON format
```

### CloudWatch Integration

```python
import boto3
import watchtower

logs_client = boto3.client('logs')
handler = watchtower.CloudWatchLogHandler()
logging.getLogger().addHandler(handler)
```

## Summary

Structured JSON logging provides:
- **Complete audit trail** of workflow execution
- **Easy querying** and filtering
- **Integration** with external logging systems
- **Debugging** support with detailed context
- **Performance monitoring** with timing data
- **Error diagnosis** with full stack traces

Combined with screenshots and state snapshots, logging enables fast root-cause analysis and resolution of workflow failures.
