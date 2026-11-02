# Architecture Guide

## Overview

The Playwright Workflows framework is designed to automate web interactions through a composable, extensible system. This guide explains the core architecture, data flow, and component interactions.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Python Application Layer                     │
│  (Workflow Definitions, Custom Actions, Business Logic)         │
└────────────────┬────────────────────────────────────┬───────────┘
                 │                                    │
         ┌───────▼────────┐               ┌──────────▼──────┐
         │   Workflow     │               │  Action         │
         │   Base Class   │               │  Registry       │
         │                │               │                 │
         │  - Execution   │               │  - Register     │
         │  - Lifecycle   │               │  - Resolve      │
         │  - Checkpoints │               │  - Invoke       │
         └───────┬────────┘               └──────────┬──────┘
                 │                                   │
                 └────────────┬──────────────────────┘
                              │
                 ┌────────────▼──────────────┐
                 │  Execution Context        │
                 │                           │
                 │  - State management       │
                 │  - Checkpoint handling    │
                 │  - Resumption logic       │
                 │  - Resource tracking      │
                 └────────────┬──────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐        ┌──────▼──────┐      ┌──────▼────┐
   │ Browser  │        │  Execution  │      │  Resource │
   │ Manager  │        │  Manager    │      │  Manager  │
   │          │        │             │      │           │
   │ - Pool   │        │ - Persist   │      │ - Track   │
   │ - Context│        │ - Retrieve  │      │ - Artifact│
   │ - Session│        │ - Resume    │      │ - Store   │
   └────┬─────┘        └──────┬──────┘      └──────┬────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                 ┌────────────▼──────────────┐
                 │  Persistence Layer        │
                 │  (JSON State Files)       │
                 │                           │
                 │  - data/executions/       │
                 │  - data/artifacts/        │
                 └────────────┬──────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼───┐        ┌───────▼────┐       ┌────────▼──┐
   │  MCP   │        │   Logging  │       │  External │
   │ Server │        │   System   │       │ Integrations
   │        │        │            │       │            │
   │- Tools │        │- Structured│       │- HTTP API  │
   │- Resources
   │        │        │- JSON logs │       │- Webhooks  │
   └────────┘        └────────────┘       └────────────┘
```

## Core Components

### 1. Workflow Base Class (`src/framework/workflow.py`)

The `Workflow` class is the foundation for all workflow definitions. It provides:

- **Step Execution**: Methods decorated with `@step` are executed in order
- **Lifecycle Management**: Setup, execution, cleanup phases
- **State Persistence**: Automatic state tracking between steps
- **Checkpointing**: Pause execution for human/AI intervention
- **Screenshots & PDFs**: Capture web state as artifacts
- **Error Handling**: Transient vs permanent error classification

**Key Methods**:
- `run()`: Execute workflow from start
- `checkpoint()`: Pause for intervention
- `resume()`: Continue from checkpoint
- `take_screenshot()`: Capture current page state
- `export_to_pdf()`: Export page as PDF

**State Structure**:
```python
{
  "id": "exec-123",
  "workflow_class": "LoginWorkflow",
  "status": "checkpointed",
  "current_step": 3,
  "steps_completed": ["login", "navigate"],
  "last_updated": "2024-01-15T10:30:00Z",
  "checkpoint_reason": "awaiting_user_input",
  "resources": [...],
  "logs": [...]
}
```

### 2. Execution Context & Manager (`src/framework/execution.py`, `src/framework/resource_manager.py`)

**ExecutionContext**:
- Holds current workflow execution state
- Manages checkpoint/resumption flow
- Tracks step completion
- Exposes APIs for workflow code

**ExecutionManager**:
- Persistence layer for execution state
- JSON file storage in `data/executions/`
- State retrieval and validation
- Concurrent execution isolation

**ResourceManager**:
- Tracks artifacts (screenshots, PDFs)
- Stores in `data/artifacts/{execution_id}/`
- Metadata: file size, MIME type, timestamp
- Integration with MCP server for serving

### 3. Action System (`src/framework/action.py`, `src/framework/action_registry.py`)

**Action Classes**:
- Base `Action` class for all custom actions
- Shared library: `src/shared_steps/` contains common actions
- Examples: `LoginAction`, `FormFillingAction`

**Action Registry**:
- Central registration point for all actions
- Runtime resolution by action name
- Type safety: validates action parameters

**Pattern**:
```python
class LoginAction(Action):
    async def execute(self, context, username, password):
        # Action implementation
        return result

# Register
registry.register(LoginAction)

# Use in workflow
class MyWorkflow(Workflow):
    @step
    async def login_step(self):
        result = await self.invoke_action('LoginAction', 
                                         username='user', 
                                         password='pass')
```

### 4. Browser Management (`src/framework/browser_manager.py`)

- **Context Pooling**: Reuse browser contexts for efficiency
- **Session Isolation**: Each execution gets isolated session
- **Resource Cleanup**: Automatic context/page cleanup on completion
- **Concurrency**: Thread-safe pool for parallel executions

### 5. Resumption System (`src/framework/resumption_manager.py`)

**Checkpoint Protocol**:
1. Workflow calls `checkpoint(reason)`
2. State saved to JSON file
3. Workflow pauses execution
4. External system updates state (e.g., user input)
5. `resume()` called with updated state
6. Workflow restores state and continues

**State Patches**:
- JSON Merge Patch (RFC 7386) for partial updates
- Full state replacement also supported
- Validation on resume: checks execution_id, current step match

### 6. MCP Server Integration (`src/mcp_server/`)

Exposes workflow management capabilities to MCP clients:

**Tools**:
- `create_workflow`: Create new execution
- `get_execution`: Retrieve execution state
- `list_executions`: List all executions
- `checkpoint_workflow`: Trigger checkpoint
- `resume_workflow`: Resume from checkpoint
- `get_execution_logs`: Query execution logs

**Resources**:
- `execution://...`: Execution state resources
- `artifact://...`: Screenshot/PDF resources
- Auto-discovery of available executions and artifacts

## Data Flow: Workflow Execution

### 1. Initial Execution

```
User Code
    │
    ├─ workflow = MyWorkflow()
    │
    ├─ execution = workflow.run()
    │   │
    │   ├─ Create ExecutionContext
    │   ├─ Create Browser context
    │   ├─ Execute @step methods sequentially
    │   │
    │   ├─ Step 1: Navigate
    │   │   ├─ Execute step code
    │   │   ├─ Update execution.state['current_step']
    │   │   └─ Save state to data/executions/{id}.json
    │   │
    │   ├─ Step 2: Login
    │   │   └─ [Same pattern]
    │   │
    │   └─ Return Execution object
    │
    └─ Print execution.state
```

### 2. Checkpoint Flow

```
Workflow Code
    │
    ├─ await self.checkpoint("awaiting_user_input")
    │   │
    │   ├─ Save current state to JSON
    │   ├─ Emit notification (if configured)
    │   └─ Pause execution (raise CheckpointException)
    │
    ├─ State file location: data/executions/{execution_id}.json
    │
    └─ External system reads state file
```

### 3. Resumption Flow

```
User/MCP Client
    │
    ├─ Call resume_workflow(execution_id, state_patch)
    │   │
    │   ├─ Load saved state
    │   ├─ Apply patch (e.g., set user_input)
    │   ├─ Restore ExecutionContext
    │   ├─ Restore Browser (if still available)
    │   │   └─ Or navigate back to last page
    │   │
    │   ├─ Resume from current_step
    │   │   ├─ Skip completed steps
    │   │   ├─ Execute remaining steps
    │   │   └─ Save state after each step
    │   │
    │   └─ Return updated Execution
    │
    └─ Logs stored in data/executions/{execution_id}.log
```

### 4. Artifact Creation & Serving

```
Workflow Code
    │
    ├─ await self.take_screenshot()
    │   │
    │   ├─ Capture page via Playwright
    │   ├─ Save to data/artifacts/{execution_id}/{name}.png
    │   ├─ Create Resource metadata
    │   ├─ Append to execution.state['resources']
    │   └─ Save execution state
    │
    └─ MCP Client
        │
        ├─ Call list_artifact_resources(execution_id)
        │   ├─ Query execution state
        │   └─ Return artifact metadata + URLs
        │
        └─ Call get_artifact_resource(execution_id, name)
            ├─ Read file from disk
            └─ Return bytes + MIME type
```

## Concurrency & Resource Management

### Process Model

- **Main Process**: Python asyncio event loop
- **Browser Processes**: Managed by Playwright, isolated per context
- **Thread Safety**: Use asyncio locks for shared state access

### Resource Isolation

```
Execution 1         Execution 2         Execution 3
    │                   │                   │
    ├─ Browser Context  ├─ Browser Context  ├─ Browser Context
    ├─ State File       ├─ State File       ├─ State File
    │                   │                   │
    ├─ data/executions/ │                   │
    │   /exec-001.json  │                   │
    ├─ data/artifacts/  │                   │
    │   /exec-001/      │                   │
    │
    └─ No shared state (complete isolation)
```

### Context Pooling

```
BrowserManager Pool
    │
    ├─ Available Contexts [Context1, Context2, ...]
    │
    ├─ When execution needs context:
    │   ├─ Acquire from pool (wait if none available)
    │   ├─ Use context for steps
    │   └─ Release back to pool
    │
    └─ Concurrent executions share pool efficiently
```

## Persistence & State Management

### File Structure

```
project/
├─ data/
│  ├─ executions/
│  │  ├─ exec-001.json      # Execution state
│  │  ├─ exec-001.log       # Structured logs
│  │  ├─ exec-002.json
│  │  └─ exec-002.log
│  │
│  └─ artifacts/
│     ├─ exec-001/
│     │  ├─ screenshot-1.png
│     │  ├─ screenshot-2.png
│     │  └─ report.pdf
│     │
│     └─ exec-002/
│        ├─ screenshot-1.png
│        └─ report.pdf
```

### State Persistence

**Automatic**: After each step completes
- Current step counter incremented
- Step result stored
- Timestamp updated
- State written to JSON

**Checkpoints**: Explicit pause points
- All execution data persisted
- Notifications sent to external systems
- State can be externally modified
- Resume recreates context from saved state

### State Format

```json
{
  "id": "exec-123",
  "workflow_class": "LoginWorkflow",
  "workflow_file": "workflows/login.py",
  "status": "in_progress",
  "current_step": 2,
  "steps_completed": ["init", "navigate"],
  "step_results": {
    "init": {"result": "success"},
    "navigate": {"url": "https://example.com"}
  },
  "checkpoint_data": null,
  "started_at": "2024-01-15T10:00:00Z",
  "last_updated": "2024-01-15T10:05:00Z",
  "completed_at": null,
  "error": null,
  "resources": [
    {
      "id": "res-001",
      "execution_id": "exec-123",
      "name": "login-page",
      "resource_type": "screenshot",
      "file_path": "data/artifacts/exec-123/login-page.png",
      "file_size_bytes": 245632,
      "created_at": "2024-01-15T10:03:00Z"
    }
  ],
  "logs": [...]
}
```

## Error Handling & Recovery

### Error Classification

**Transient Errors** (retry-safe):
- Network timeouts
- Temporary page load failures
- Rate limiting (HTTP 429)

**Permanent Errors** (require intervention):
- Authentication failures
- Missing page elements
- Application errors (5xx)
- Invalid input

### Recovery Strategy

1. **Immediate Retry**: For transient errors
   - Exponential backoff
   - Max 3 retries default

2. **Checkpoint for Intervention**: For permanent errors
   - Save state at error point
   - Notify external system
   - Wait for manual intervention
   - Resume when fixed

3. **Graceful Degradation**: For optional operations
   - Screenshot failed? Continue anyway
   - Log warning, continue workflow

## Performance Characteristics

### Throughput

- **Simple workflows**: ~100-200 workflows/minute
- **Complex workflows**: ~10-50 workflows/minute
- **Concurrency**: Limited by browser process count (typical: 5-10 parallel)

### Latency

- **Checkpoint decision**: <2 seconds
- **State persistence**: <100ms (JSON write)
- **Resumption**: <5 seconds (context restore + navigate back)

### Memory

- **Per execution**: ~50MB baseline (Playwright context)
- **Artifacts**: PNG ~2-5MB, PDF ~5-20MB
- **State files**: <1MB JSON per execution

## Extension Points

### 1. Custom Actions

Extend `Action` class and register:

```python
class MyCustomAction(Action):
    async def execute(self, context, param1, param2):
        # Custom logic
        return result

registry.register(MyCustomAction)
```

### 2. Custom Workflows

Extend `Workflow` class:

```python
class MyWorkflow(Workflow):
    @step
    async def step1(self):
        await self.invoke_action('MyCustomAction')
    
    @step
    async def step2(self):
        await self.take_screenshot()
```

### 3. Checkpoint Handlers

React to checkpoints via notifications:

```python
executor.on_checkpoint(lambda exec: notify_slack(exec))
```

### 4. Logging Integration

Structured JSON logs for external systems:

```json
{
  "timestamp": "2024-01-15T10:05:00Z",
  "execution_id": "exec-123",
  "level": "INFO",
  "message": "Step completed",
  "step": "login",
  "duration_ms": 2340
}
```

## Summary

The architecture balances:
- **Simplicity**: Easy to write workflows and actions
- **Extensibility**: Custom actions and workflows
- **Reliability**: Checkpoint/resumption for fault tolerance
- **Concurrency**: Browser context pooling and isolation
- **Observability**: Structured logging and artifact storage

Each component has a clear responsibility, with minimal coupling between layers. The persistence layer enables resumption and debugging, while the MCP integration allows external control and monitoring.
