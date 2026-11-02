# CLI Guide - Playwright Workflows

The `src/cli` folder contains command-line interfaces for running and managing Playwright workflows. This guide explains each CLI tool and how to use them.

## Overview

| Tool | File | Purpose |
|------|------|---------|
| **Workflow Runner** | `workflow_runner.py` | Run single workflow with parameters |
| **Batch Runner** | `batch_runner.py` | Run multiple workflows in parallel |
| **MCP Server Runner** | `mcp_server_runner.py` | Run MCP server for external control |
| **Resume Workflow** | `resume_workflow.py` | Resume paused or failed workflows |

## 1. Workflow Runner

**File:** `src/cli/workflow_runner.py`

Run a single workflow with specified parameters.

### Basic Usage

```bash
python -m src.cli.workflow_runner \
    --workflow-type login \
    --url https://example.com \
    --username testuser \
    --password testpass
```

### Parameters

```bash
python -m src.cli.workflow_runner \
    --workflow-type <type>          # Type of workflow (e.g., "login")
    --url <url>                     # Target URL
    --username <username>           # Login username
    --password <password>           # Login password
    --log-dir <path>               # Directory for logs (optional)
    --output-format <format>       # Output format: "json" or "text" (default: json)
```

### Output

**JSON Format (default):**
```json
{
  "status": "success",
  "workflow_type": "login",
  "execution_id": "abc-123",
  "result": {
    "logged_in": true,
    "user_id": "user-456"
  }
}
```

**Text Format:**
```
Workflow: login
Status: SUCCESS
Result:
  - Logged in: Yes
  - User ID: user-456
```

### Examples

#### Login to a website
```bash
python -m src.cli.workflow_runner \
    --workflow-type login \
    --url https://example.com/login \
    --username myuser \
    --password mypass \
    --output-format json
```

#### Run workflow with logging
```bash
python -m src.cli.workflow_runner \
    --workflow-type login \
    --url https://example.com \
    --username user \
    --password pass \
    --log-dir ./logs
```

#### Check exit code
```bash
python -m src.cli.workflow_runner \
    --workflow-type login \
    --url https://example.com \
    --username user \
    --password pass

echo $?  # 0 for success, non-zero for failure
```

### Exit Codes

- **0**: Success - workflow executed successfully
- **1**: Error - workflow failed or error occurred

## 2. Batch Runner

**File:** `src/cli/batch_runner.py`

Run multiple workflows in parallel with concurrency control.

### Basic Usage

```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 5
```

### Parameters

```bash
python -m src.cli.batch_runner \
    --input <file>                 # JSON file with workflow definitions
    --max-concurrent <num>         # Max parallel executions (default: 5)
    --log-dir <path>              # Directory for logs (optional)
    --output-format <format>      # Output format: "json" or "text"
```

### Input JSON Format

**workflows.json:**
```json
[
  {
    "execution_id": "exec-001",
    "workflow_type": "login",
    "params": {
      "url": "https://example.com",
      "username": "user1",
      "password": "pass1"
    }
  },
  {
    "execution_id": "exec-002",
    "workflow_type": "login",
    "params": {
      "url": "https://example.com",
      "username": "user2",
      "password": "pass2"
    }
  }
]
```

### Output

**Summary:**
```json
{
  "total_workflows": 2,
  "succeeded": 2,
  "failed": 0,
  "total_time_seconds": 15.34,
  "success": true,
  "summary": "2 succeeded, 0 failed",
  "results": [
    {
      "execution_id": "exec-001",
      "status": "completed",
      "success": true,
      "elapsed_seconds": 7.5
    },
    {
      "execution_id": "exec-002",
      "status": "completed",
      "success": true,
      "elapsed_seconds": 7.84
    }
  ]
}
```

### Examples

#### Run 100 parallel workflows
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 50 \
    --log-dir ./batch-logs
```

#### Run with text output
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 10 \
    --output-format text
```

#### Process results with jq
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 5 | jq '.results | map(select(.success == false))'
```

### Concurrency Control

The batch runner automatically controls concurrency:

```python
# Max 5 concurrent workflows
python -m src.cli.batch_runner --input workflows.json --max-concurrent 5

# Results:
# Execution 1-5: Running (0.0s)
# Execution 6 starts when one of 1-5 completes (7.5s)
# Execution 7 starts when another completes (15s)
# ...
```

### Performance Tips

- **Small workflows**: `--max-concurrent 50-100` (fast, resource-light)
- **Medium workflows**: `--max-concurrent 20-30` (balanced)
- **Large workflows**: `--max-concurrent 5-10` (resource-intensive)
- **Monitor**: Check logs and memory usage for optimal settings

## 3. MCP Server Runner

**File:** `src/cli/mcp_server_runner.py`

Run the MCP (Model Context Protocol) server for external control via JSON-RPC 2.0.

### Basic Usage

```bash
python -m src.cli.mcp_server_runner
```

The server runs on stdin/stdout and listens for JSON-RPC 2.0 requests.

### Available Tools

#### start_workflow
Start a new workflow execution.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "start_workflow",
    "arguments": {
      "workflow_type": "login",
      "input_params": {
        "url": "https://example.com",
        "username": "user",
        "password": "pass"
      },
      "max_retries": 3
    }
  }
}
```

#### resolve_checkpoint
Resume workflow from checkpoint with human/AI decision.

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "resolve_checkpoint",
    "arguments": {
      "execution_id": "exec-123",
      "checkpoint_id": "cp-456",
      "decision": {"approved": true},
      "agent_id": "human_agent"
    }
  }
}
```

#### get_execution_status
Get current status of an execution.

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "get_execution_status",
    "arguments": {
      "execution_id": "exec-123"
    }
  }
}
```

#### get_execution_logs
Retrieve execution logs with optional filtering.

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "get_execution_logs",
    "arguments": {
      "execution_id": "exec-123",
      "level": "info",
      "limit": 100
    }
  }
}
```

### Examples

#### Run with MCP Inspector
```bash
# Start server and open MCP Inspector
mcp dev src/cli/mcp_server_runner.py
```

#### Programmatic usage
```python
import asyncio
from src.mcp_server.server import create_server

async def main():
    server = create_server()
    await server.run()  # Runs on stdio

asyncio.run(main())
```

## 4. Resume Workflow

**File:** `src/cli/resume_workflow.py`

Resume a paused or failed workflow execution with smart strategy selection.

### Basic Usage

```bash
python -m src.cli.resume_workflow exec-123
```

### Parameters

```bash
python -m src.cli.resume_workflow <execution_id> \
    --execution-dir <path>        # Custom execution directory
    --verbose                     # Enable verbose logging
```

### Resume Strategies

#### Quick Resume (< 5 minutes paused)
- Keeps browser context alive
- Resumes from last checkpoint
- Minimal browser operations
- **Speed**: 1-3 seconds

#### Slow Resume (> 5 minutes paused)
- Replays all previous steps
- Detects authentication failures
- Re-authenticates if needed
- **Speed**: Full workflow duration

### Examples

#### Resume workflow automatically
```bash
python -m src.cli.resume_workflow abc-123
```

**Output:**
```
============================================================
RESUMPTION INFO
============================================================
Execution ID:    abc-123
Status:          paused_at_checkpoint
Workflow Type:   login
Strategy:        QUICK
Session Age:     120s
Progress:        3/5 steps
Last Checkpoint: cp-456
============================================================

ℹ  QUICK RESUME (< 5 min)
Strategy: Keep browser context alive, continue from checkpoint

Proceed with resumption? [Y/n]: y

Initiating resumption workflow...

✓ Resumption initiated with quick strategy

Next steps:
1. The execution will be marked as resuming
2. Execution engine will continue from the checkpoint
3. Monitor execution with: get-execution-status abc-123
```

#### Resume with custom directory
```bash
python -m src.cli.resume_workflow abc-123 \
    --execution-dir /data/my-executions
```

#### Resume with verbose logging
```bash
python -m src.cli.resume_workflow abc-123 \
    --verbose
```

### How It Works

1. **Load State**: Retrieves execution state from disk
2. **Determine Strategy**: Analyzes pause time and execution state
3. **Prepare**: Sets up browser context and checkpoint info
4. **Execute**: Runs resumption with selected strategy
5. **Monitor**: Returns immediately; execution continues async

## Complete Workflow Example

### Single Workflow
```bash
# 1. Run a single workflow
python -m src.cli.workflow_runner \
    --workflow-type login \
    --url https://example.com \
    --username user \
    --password pass \
    --output-format json > result.json

# 2. Check result
cat result.json | jq '.status'
```

### Batch Workflow
```bash
# 1. Create workflows.json with 100 workflows
python << 'EOF'
import json

workflows = [
    {
        "execution_id": f"exec-{i:04d}",
        "workflow_type": "login",
        "params": {
            "url": "https://example.com",
            "username": f"user{i}",
            "password": f"pass{i}"
        }
    }
    for i in range(100)
]

with open("workflows.json", "w") as f:
    json.dump(workflows, f)
EOF

# 2. Run batch with 10 concurrent workflows
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 10 \
    --log-dir ./logs > batch_result.json

# 3. Check summary
cat batch_result.json | jq '{total: .total_workflows, succeeded: .succeeded, failed: .failed}'
```

### MCP Server Integration
```bash
# 1. Start MCP server in background
python -m src.cli.mcp_server_runner &
MCP_PID=$!

# 2. Send JSON-RPC request (from external client)
# Client sends:
# {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {...}}

# 3. Shutdown server
kill $MCP_PID
```

## Advanced Usage

### Custom Workflow Input

Extend workflow runner to support custom workflows:

```python
# src/cli/workflow_runner.py

def _get_workflow(self):
    if self.workflow_type == "login":
        return LoginWorkflow()
    elif self.workflow_type == "custom":
        return MyCustomWorkflow()  # Add custom workflow
    else:
        raise ValueError(f"Unknown workflow type: {self.workflow_type}")
```

### Batch Configuration File

Create a configuration file for batch runs:

```yaml
# batch_config.yaml
batch:
  max_concurrent: 10
  log_dir: ./logs
  timeout_seconds: 3600
  
workflows:
  - execution_id: exec-001
    workflow_type: login
    params:
      url: https://example.com
      username: user1
      password: pass1
  - execution_id: exec-002
    workflow_type: form_filling
    params:
      url: https://example.com/form
```

### Error Handling

All CLI tools return appropriate exit codes:

```bash
# Success
python -m src.cli.workflow_runner ... 
echo $?  # 0

# Failure
python -m src.cli.workflow_runner --workflow-type invalid
echo $?  # 1
```

### Logging

All tools support logging to files:

```bash
# Single workflow
python -m src.cli.workflow_runner \
    --workflow-type login \
    ... \
    --log-dir ./logs

# Check logs
tail -f ./logs/login.log

# Batch
python -m src.cli.batch_runner \
    --input workflows.json \
    --log-dir ./batch-logs

# Each execution has its log
tail -f ./batch-logs/exec-001.log
```

## Best Practices

1. **Single Workflows**: Use `workflow_runner.py` for one-off executions
2. **Batch Operations**: Use `batch_runner.py` for multiple workflows
3. **External Control**: Use `mcp_server_runner.py` for AI/agent control
4. **Resumption**: Use `resume_workflow.py` for failed/paused workflows
5. **Concurrency**: Start with `max_concurrent=5`, tune based on resources
6. **Logging**: Always enable logging for debugging failures
7. **Output Format**: Use JSON for programmatic processing, text for humans

## Troubleshooting

### Workflows timeout
```bash
# Increase timeout or check if workflow is stuck
python -m src.cli.workflow_runner \
    --workflow-type login \
    ... \
    --log-dir ./logs

# Check logs
cat ./logs/login.log
```

### High memory usage with batch
```bash
# Reduce max concurrent
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 5  # Lower from 20

# Monitor memory
watch -n 1 'ps aux | grep workflow_runner'
```

### MCP server not responding
```bash
# Check server is running
ps aux | grep mcp_server_runner

# Run with verbose output
python -m src.cli.mcp_server_runner --verbose
```

## See Also

- [TESTING_GUIDE.md](TESTING_GUIDE.md) - How to test workflows
- [docs/architecture.md](docs/architecture.md) - System architecture
- [docs/performance-tuning.md](docs/performance-tuning.md) - Performance optimization
