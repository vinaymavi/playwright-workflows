# Python API Client Documentation

This document explains how to use the `WorkflowController` API to programmatically control Playwright workflow automation in Python.

## Table of Contents

- [Overview](#overview)
- [Installation & Setup](#installation--setup)
- [WorkflowController API](#workflowcontroller-api)
  - [start() / start_async()](#start--start_async)
  - [get_status() / get_status_async()](#get_status--get_status_async)
  - [resolve_checkpoint() / resolve_checkpoint_async()](#resolve_checkpoint--resolve_checkpoint_async)
  - [get_logs() / get_logs_async()](#get_logs--get_logs_async)
- [Sync vs Async](#sync-vs-async)
- [Error Handling](#error-handling)
- [Examples](#examples)
  - [Simple Login Workflow](#simple-login-workflow)
  - [Long-Running Workflow with Polling](#long-running-workflow-with-polling)
  - [Async Workflow Control](#async-workflow-control)
  - [Batch Workflow Execution](#batch-workflow-execution)

## Overview

The `WorkflowController` is a Python API client that provides direct access to workflow execution control. Unlike the MCP server (which is designed for external clients), the WorkflowController:

- **Eliminates MCP overhead** - Calls workflow tools directly
- **Provides sync and async interfaces** - Use whichever fits your architecture
- **Integrates with Python tooling** - Use in CLI, servers, scripts, or applications
- **Supports error handling** - Proper exceptions and logging

### Use Cases

- **Orchestration scripts** - Control multiple workflows from a single script
- **CLI tools** - Build command-line workflow automation tools
- **Middleware integration** - Embed workflow control in applications
- **Testing & automation** - Test workflows programmatically
- **AI agent control** - Use in LLM-based automation systems

## Installation & Setup

### Prerequisites

- Python 3.10+
- Project dependencies installed (`uv sync` or `pip install -e .`)

### Basic Setup

```python
from src.api.workflow_controller import WorkflowController

# Create controller instance
controller = WorkflowController()
```

### With Custom Configuration

```python
from src.api.workflow_controller import WorkflowController

# Controller is stateless and uses internal tool functions
# No additional configuration needed
controller = WorkflowController()
```

## WorkflowController API

### start() / start_async()

Start a new workflow execution.

#### Async Version

```python
async def start_async(
    workflow_type: str,
    input_params: dict,
    max_retries: int = 3,
    timeout_seconds: int = 300
) -> dict
```

**Parameters:**
- `workflow_type` (str): Type of workflow to execute (e.g., 'login_workflow')
- `input_params` (dict): Input parameters specific to the workflow
- `max_retries` (int, optional): Maximum retry attempts on failure. Default: 3
- `timeout_seconds` (int, optional): Execution timeout in seconds. Default: 300

**Returns:** Dictionary containing:
- `execution_id` (str): UUID of the created execution
- `workflow_type` (str): The workflow type that was started
- `status` (str): Initial status ("pending" or "running")
- `started_at` (str): ISO 8601 timestamp of start time

**Raises:**
- `ValueError`: If workflow_type is invalid or required params are missing
- `RuntimeError`: If called from non-async context (async version only)

**Example:**

```python
import asyncio

async def main():
    controller = WorkflowController()
    result = await controller.start_async(
        workflow_type="login_workflow",
        input_params={
            "url": "https://example.com",
            "username": "user@example.com",
            "password": "secret123"
        },
        timeout_seconds=600
    )
    print(f"Execution started: {result['execution_id']}")
    return result['execution_id']

execution_id = asyncio.run(main())
```

#### Sync Version

```python
def start(
    workflow_type: str,
    input_params: dict,
    max_retries: int = 3,
    timeout_seconds: int = 300
) -> dict
```

Synchronous wrapper around `start_async()`. Same parameters and return value.

**Raises:**
- `ValueError`: If workflow_type is invalid or required params are missing
- `RuntimeError`: If called from within an async context

**Example:**

```python
from src.api.workflow_controller import WorkflowController

controller = WorkflowController()
result = controller.start(
    workflow_type="login_workflow",
    input_params={
        "url": "https://example.com",
        "username": "user@example.com",
        "password": "secret123"
    }
)
print(f"Execution started: {result['execution_id']}")
```

### get_status() / get_status_async()

Get the current status and progress of a workflow execution.

#### Async Version

```python
async def get_status_async(execution_id: str) -> dict
```

**Parameters:**
- `execution_id` (str): UUID of the execution to query

**Returns:** Dictionary containing:
- `execution_id` (str): The queried execution ID
- `workflow_type` (str): Type of workflow being executed
- `status` (str): Current status (pending, running, paused, completed, failed)
- `started_at` (str): ISO 8601 timestamp of start time
- `ended_at` (str or None): ISO 8601 timestamp of end time (None if still running)
- `completed_steps` (int): Number of completed workflow steps
- `total_steps` (int): Total number of steps in workflow
- `current_step_name` (str): Name of current step
- `pending_checkpoint` (dict or None): Checkpoint information if paused, None otherwise
  - `checkpoint_id` (str): UUID of checkpoint
  - `question` (str): Checkpoint question for agent/human
  - `options` (list): Available decision options
- `error` (str or None): Error message if status is "failed"

**Raises:**
- `ValueError`: If execution_id is not found

**Example:**

```python
import asyncio

async def monitor_execution(execution_id):
    controller = WorkflowController()
    status = await controller.get_status_async(execution_id)
    
    print(f"Status: {status['status']}")
    print(f"Progress: {status['completed_steps']}/{status['total_steps']}")
    
    if status['pending_checkpoint']:
        print(f"Waiting for checkpoint: {status['pending_checkpoint']['question']}")
        print(f"Options: {status['pending_checkpoint']['options']}")
    
    return status
```

#### Sync Version

```python
def get_status(execution_id: str) -> dict
```

Synchronous wrapper around `get_status_async()`. Same parameters and return value.

**Example:**

```python
controller = WorkflowController()
status = controller.get_status("550e8400-e29b-41d4-a716-446655440000")
print(f"Current status: {status['status']}")
```

### resolve_checkpoint() / resolve_checkpoint_async()

Provide a decision to resume a workflow from a checkpoint.

#### Async Version

```python
async def resolve_checkpoint_async(
    execution_id: str,
    checkpoint_id: str,
    decision: dict,
    agent_id: str = "unknown"
) -> dict
```

**Parameters:**
- `execution_id` (str): UUID of the execution to resume
- `checkpoint_id` (str): UUID of the checkpoint to resolve
- `decision` (dict): Agent's decision response. Structure depends on checkpoint type:
  - For approval checkpoints: `{"decision": "approved"}` or `{"decision": "rejected"}`
  - For form verification: `{"form_data": {...}, "verified": True}`
  - For CAPTCHA: `{"captcha_solution": "...", "attempt": 1}`
  - Custom structures depend on checkpoint implementation
- `agent_id` (str, optional): Identifier of the agent making the decision (for audit trail). Default: "unknown"

**Returns:** Dictionary containing:
- `execution_id` (str): The execution ID
- `checkpoint_id` (str): The resolved checkpoint ID
- `status` (str): New status after resolution (typically "running")
- `resolved_at` (str): ISO 8601 timestamp of resolution

**Raises:**
- `ValueError`: If execution_id or checkpoint_id is not found, or decision format is invalid
- `RuntimeError`: If checkpoint is not actually pending

**Example:**

```python
import asyncio

async def approve_form(execution_id, checkpoint_id):
    controller = WorkflowController()
    result = await controller.resolve_checkpoint_async(
        execution_id=execution_id,
        checkpoint_id=checkpoint_id,
        decision={
            "form_data": {
                "name": "John Doe",
                "email": "john@example.com"
            },
            "verified": True
        },
        agent_id="claude-3-opus"
    )
    print(f"Checkpoint resolved at {result['resolved_at']}")
    return result
```

#### Sync Version

```python
def resolve_checkpoint(
    execution_id: str,
    checkpoint_id: str,
    decision: dict,
    agent_id: str = "unknown"
) -> dict
```

Synchronous wrapper around `resolve_checkpoint_async()`. Same parameters and return value.

**Example:**

```python
controller = WorkflowController()
result = controller.resolve_checkpoint(
    execution_id="550e8400-e29b-41d4-a716-446655440000",
    checkpoint_id="660f9511-f40c-52e5-b827-557766551111",
    decision={"decision": "approved"},
    agent_id="user-123"
)
```

### get_logs() / get_logs_async()

Retrieve structured logs from a workflow execution with optional filtering.

#### Async Version

```python
async def get_logs_async(
    execution_id: str,
    event_type: str = None,
    level: str = None,
    limit: int = 100,
    offset: int = 0
) -> dict
```

**Parameters:**
- `execution_id` (str): UUID of the execution
- `event_type` (str, optional): Filter by event type (e.g., "step_started", "checkpoint_requested")
- `level` (str, optional): Filter by log level ("DEBUG", "INFO", "WARNING", "ERROR")
- `limit` (int, optional): Maximum logs to return. Default: 100
- `offset` (int, optional): Pagination offset. Default: 0

**Returns:** Dictionary containing:
- `execution_id` (str): The execution ID
- `total_logs` (int): Total number of logs matching filters
- `returned_logs` (int): Number of logs in this response
- `logs` (list): Array of log entries, each containing:
  - `timestamp` (str): ISO 8601 timestamp
  - `event_type` (str): Type of event
  - `level` (str): Log level (DEBUG, INFO, WARNING, ERROR)
  - `message` (str): Log message
  - `step_name` (str or None): Name of workflow step if applicable
  - `data` (dict or None): Additional event data

**Raises:**
- `ValueError`: If execution_id is not found

**Example:**

```python
import asyncio

async def get_checkpoint_logs(execution_id):
    controller = WorkflowController()
    logs = await controller.get_logs_async(
        execution_id=execution_id,
        event_type="checkpoint_requested",
        limit=50
    )
    
    print(f"Found {logs['total_logs']} checkpoint logs")
    for log in logs['logs']:
        print(f"[{log['timestamp']}] {log['message']}")
    
    return logs
```

#### Sync Version

```python
def get_logs(
    execution_id: str,
    event_type: str = None,
    level: str = None,
    limit: int = 100,
    offset: int = 0
) -> dict
```

Synchronous wrapper around `get_logs_async()`. Same parameters and return value.

**Example:**

```python
controller = WorkflowController()
logs = controller.get_logs(
    execution_id="550e8400-e29b-41d4-a716-446655440000",
    level="ERROR",
    limit=10
)
for log in logs['logs']:
    print(f"ERROR: {log['message']}")
```

## Sync vs Async

### When to Use Sync

- **Simple scripts** - Linear execution where blocking is acceptable
- **CLI tools** - Command-line programs without concurrency requirements
- **Backwards compatibility** - Existing code that doesn't use async

**Example:**

```python
# Simple CLI workflow trigger
def cli_start_workflow():
    controller = WorkflowController()
    
    result = controller.start(
        workflow_type="login_workflow",
        input_params={"url": "https://example.com", ...}
    )
    
    while True:
        status = controller.get_status(result['execution_id'])
        print(f"Status: {status['status']}")
        
        if status['pending_checkpoint']:
            # Handle checkpoint
            controller.resolve_checkpoint(...)
        
        if status['status'] in ['completed', 'failed']:
            break
        
        time.sleep(1)
```

### When to Use Async

- **High-concurrency applications** - Web servers, API gateways
- **Multiple parallel workflows** - Running many workflows simultaneously
- **Modern Python applications** - FastAPI, asyncio-based systems
- **Resource-efficient monitoring** - Polling many executions without blocking threads

**Example:**

```python
import asyncio

async def monitor_multiple_workflows(execution_ids):
    controller = WorkflowController()
    
    # Poll all executions concurrently
    tasks = [
        controller.get_status_async(eid)
        for eid in execution_ids
    ]
    
    statuses = await asyncio.gather(*tasks)
    return statuses
```

### Important Notes on Event Loop Handling

**For Python 3.14+:**

The synchronous methods handle event loop management automatically:

```python
# This works fine - sync wrapper creates its own event loop
controller = WorkflowController()
status = controller.get_status("execution-id")

# This will raise RuntimeError - cannot create nested event loop
async def async_func():
    controller = WorkflowController()
    status = controller.get_status("execution-id")  # ❌ RuntimeError
    
    # Use async method instead
    status = await controller.get_status_async("execution-id")  # ✓ OK
```

**Error message pattern:**

If you accidentally call a sync method from async context, you'll get:

```
RuntimeError: Sync method cannot be called from within async context. Use the _async variant instead.
```

## Error Handling

### Common Exceptions

All methods raise standard Python exceptions:

```python
from src.api.workflow_controller import WorkflowController

controller = WorkflowController()

try:
    result = controller.start(
        workflow_type="invalid_workflow",
        input_params={}
    )
except ValueError as e:
    print(f"Invalid workflow type: {e}")

try:
    status = controller.get_status("invalid-uuid")
except ValueError as e:
    print(f"Execution not found: {e}")

try:
    # Calling sync method from async context
    async def wrong_usage():
        status = controller.get_status("exec-id")
except RuntimeError as e:
    print(f"Event loop error: {e}")
```

### Error Handling Best Practices

1. **Always wrap critical operations in try-except:**

```python
def safe_get_status(execution_id):
    controller = WorkflowController()
    try:
        return controller.get_status(execution_id)
    except ValueError:
        print(f"Execution {execution_id} not found")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
```

2. **Implement retry logic for transient failures:**

```python
import time
from src.api.workflow_controller import WorkflowController

def get_status_with_retry(execution_id, max_retries=3):
    controller = WorkflowController()
    
    for attempt in range(max_retries):
        try:
            return controller.get_status(execution_id)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

3. **Log all errors for debugging:**

```python
import logging

logger = logging.getLogger(__name__)

def log_and_reraise(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            raise
    return wrapper

@log_and_reraise
def control_workflow(workflow_type, params):
    controller = WorkflowController()
    return controller.start(workflow_type, params)
```

## Examples

### Simple Login Workflow

```python
#!/usr/bin/env python3
"""Simple synchronous workflow control example."""

from src.api.workflow_controller import WorkflowController
import time

def main():
    controller = WorkflowController()
    
    # 1. Start workflow
    print("Starting login workflow...")
    result = controller.start(
        workflow_type="login_workflow",
        input_params={
            "url": "https://example.com/login",
            "username": "user@example.com",
            "password": "secure_password"
        }
    )
    execution_id = result['execution_id']
    print(f"✓ Execution started: {execution_id}")
    
    # 2. Monitor execution
    print("\nMonitoring execution...")
    while True:
        status = controller.get_status(execution_id)
        print(f"Status: {status['status']} ({status['completed_steps']}/{status['total_steps']})")
        
        # 3. Handle checkpoint if needed
        if status['pending_checkpoint']:
            checkpoint = status['pending_checkpoint']
            print(f"\n⏸️  Checkpoint: {checkpoint['question']}")
            print(f"   Options: {checkpoint['options']}")
            
            # In real scenario, get decision from user/agent
            decision = {"decision": "verified"}
            
            controller.resolve_checkpoint(
                execution_id=execution_id,
                checkpoint_id=checkpoint['checkpoint_id'],
                decision=decision,
                agent_id="user-cli"
            )
            print("✓ Checkpoint resolved, resuming...")
        
        # 4. Check for completion
        if status['status'] == 'completed':
            print("\n✓ Workflow completed successfully!")
            break
        elif status['status'] == 'failed':
            print(f"\n✗ Workflow failed: {status['error']}")
            
            # Get failure logs
            logs = controller.get_logs(execution_id, level="ERROR")
            for log in logs['logs']:
                print(f"  - {log['message']}")
            break
        
        time.sleep(1)
    
    # 5. Retrieve final logs
    print("\nFinal logs:")
    logs = controller.get_logs(execution_id, limit=10)
    for log in logs['logs']:
        print(f"  [{log['level']}] {log['message']}")

if __name__ == "__main__":
    main()
```

### Long-Running Workflow with Polling

```python
#!/usr/bin/env python3
"""Example: Start workflow and poll until completion."""

from src.api.workflow_controller import WorkflowController
import time
import sys

def wait_for_completion(execution_id, timeout_seconds=600, poll_interval=5):
    """Wait for workflow to complete with timeout."""
    controller = WorkflowController()
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        status = controller.get_status(execution_id)
        
        if status['status'] == 'completed':
            return True, status
        elif status['status'] == 'failed':
            return False, status
        
        elapsed = time.time() - start_time
        print(f"[{elapsed:.0f}s] Still running... ({status['completed_steps']}/{status['total_steps']})")
        time.sleep(poll_interval)
    
    raise TimeoutError(f"Workflow did not complete within {timeout_seconds} seconds")

def main():
    controller = WorkflowController()
    
    # Start workflow
    execution = controller.start(
        workflow_type="form_filling_workflow",
        input_params={
            "url": "https://example.com/form",
            "form_data": {"name": "John", "email": "john@example.com"}
        }
    )
    
    print(f"Started execution: {execution['execution_id']}")
    
    # Wait for completion
    try:
        success, final_status = wait_for_completion(
            execution['execution_id'],
            timeout_seconds=300
        )
        
        if success:
            print("✓ Workflow completed successfully")
        else:
            print(f"✗ Workflow failed: {final_status['error']}")
            sys.exit(1)
    except TimeoutError as e:
        print(f"✗ {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Async Workflow Control

```python
#!/usr/bin/env python3
"""Example: Async workflow control for high-concurrency scenarios."""

import asyncio
from src.api.workflow_controller import WorkflowController

async def run_workflow_async(workflow_type, input_params):
    """Start and monitor a workflow asynchronously."""
    controller = WorkflowController()
    
    # Start workflow
    execution = await controller.start_async(
        workflow_type=workflow_type,
        input_params=input_params
    )
    print(f"Started: {execution['execution_id']}")
    
    # Monitor execution
    while True:
        status = await controller.get_status_async(execution['execution_id'])
        
        if status['status'] == 'completed':
            print(f"✓ {workflow_type} completed")
            return True
        elif status['status'] == 'failed':
            print(f"✗ {workflow_type} failed: {status['error']}")
            return False
        
        await asyncio.sleep(1)

async def run_multiple_workflows():
    """Run multiple workflows concurrently."""
    workflows = [
        ("login_workflow", {"url": "https://app1.com", "username": "user1"}),
        ("login_workflow", {"url": "https://app2.com", "username": "user2"}),
        ("form_filling_workflow", {"url": "https://form.com", "field_1": "value"}),
    ]
    
    tasks = [
        run_workflow_async(workflow_type, params)
        for workflow_type, params in workflows
    ]
    
    results = await asyncio.gather(*tasks)
    print(f"\nResults: {sum(results)}/{len(results)} succeeded")

if __name__ == "__main__":
    asyncio.run(run_multiple_workflows())
```

### Batch Workflow Execution

```python
#!/usr/bin/env python3
"""Example: Execute workflows in batch with progress tracking."""

from src.api.workflow_controller import WorkflowController
import csv
import time

def process_batch_from_csv(csv_file):
    """Process batch of workflows from CSV file."""
    controller = WorkflowController()
    executions = []
    
    # Start all workflows
    print(f"Starting workflows from {csv_file}...")
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            execution = controller.start(
                workflow_type=row['workflow_type'],
                input_params={
                    "url": row['url'],
                    "username": row['username'],
                    "password": row['password']
                }
            )
            executions.append({
                "id": execution['execution_id'],
                "workflow": row['workflow_type'],
                "url": row['url'],
                "status": "running"
            })
    
    print(f"Started {len(executions)} workflows")
    
    # Monitor all executions
    completed = 0
    failed = 0
    
    while completed + failed < len(executions):
        for exec_info in executions:
            if exec_info['status'] not in ['completed', 'failed']:
                status = controller.get_status(exec_info['id'])
                
                if status['status'] == 'completed':
                    exec_info['status'] = 'completed'
                    completed += 1
                    print(f"✓ {exec_info['workflow']}: {exec_info['url']}")
                elif status['status'] == 'failed':
                    exec_info['status'] = 'failed'
                    failed += 1
                    print(f"✗ {exec_info['workflow']}: {status['error']}")
        
        time.sleep(2)
    
    print(f"\nBatch complete: {completed} succeeded, {failed} failed")

if __name__ == "__main__":
    process_batch_from_csv("workflows.csv")
```

---

**For more information:**
- See [MCP Protocol Guide](./mcp-protocol.md) for server protocol details
- See [Checkpoint Protocol Guide](./checkpoint-protocol.md) for checkpoint design
- See [Custom Actions Guide](./custom-actions-guide.md) for extending workflows
