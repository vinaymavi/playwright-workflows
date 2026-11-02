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

Run a single workflow with JSON input parameters.

### Basic Usage

```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"testuser","password":"testpass"}'
```

### Parameters

```bash
python -m src.cli.workflow_runner <workflow_type> \
    --input, -i <json>              # JSON input parameters (required)
    --output-format, -f {json,text} # Output format (default: json)
    --log-dir, -l <path>            # Directory for logs (default: data/logs)
```

### Input Format

The `--input` parameter accepts JSON with workflow-specific fields:

**Login Workflow:**
```json
{
  "url": "https://example.com",
  "username": "testuser",
  "password": "testpass"
}
```

**Form Filling Workflow:**
```json
{
  "url": "https://example.com/form",
  "fields": {
    "name": "John Doe",
    "email": "john@example.com",
    "message": "Hello!"
  }
}
```

### Output

**JSON Format (default):**
```json
{
  "success": true,
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
✓ SUCCESS: Login workflow completed
Dashboard URL: https://example.com/dashboard
```

### Examples

#### Login to a website (JSON)
```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com/login","username":"myuser","password":"mypass"}'
```

#### Login with text output
```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"user","password":"pass"}' \
    --output-format text
```

#### Login with logging to file
```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"user","password":"pass"}' \
    --log-dir ./logs
```

#### Login with all options
```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"user","password":"pass"}' \
    --output-format json \
    --log-dir ./logs
```

#### Check exit code
```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"user","password":"pass"}'

echo $?  # 0 for success, non-zero for failure
```

#### Using file for input (easier for complex JSON)
```bash
# Create input.json
cat > input.json << 'EOF'
{
  "url": "https://example.com",
  "username": "testuser",
  "password": "testpass"
}
EOF

# Run with jq to convert file to JSON string
python -m src.cli.workflow_runner login \
    --input "$(cat input.json | jq -c .)"
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

#### Create workflow input file
```bash
# Create workflows.json with 10 login workflows
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
    for i in range(10)
]

with open("workflows.json", "w") as f:
    json.dump(workflows, f, indent=2)
EOF
```

#### Run 10 parallel workflows
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 5 \
    --log-dir ./batch-logs
```

#### Run with text output
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 10 \
    --output-format text
```

#### Run with custom concurrency
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 20
```

#### Process results with jq (find only failures)
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 5 | jq '.results | map(select(.success == false))'
```

#### Save results to file
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 5 > results.json

cat results.json | jq '.summary'
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

### Single Workflow

```bash
# 1. Run a single login workflow with JSON parameters
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"testuser","password":"testpass"}' \
    --output-format json > result.json

# 2. Check result
cat result.json | jq '.result'
```

### Single Workflow from File

```bash
# 1. Create input.json with workflow parameters
cat > input.json << 'EOF'
{
  "url": "https://example.com",
  "username": "testuser",
  "password": "testpass"
}
EOF

# 2. Run workflow with input from file
python -m src.cli.workflow_runner login \
    --input "$(cat input.json | jq -c .)" \
    --log-dir ./logs

# 3. Check logs
cat logs/login.log
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
    json.dump(workflows, f, indent=2)
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

### Using Shell Variables for Sensitive Data

```bash
# Set environment variables for sensitive data
export WORKFLOW_USER="testuser"
export WORKFLOW_PASS="testpass"

# Create JSON input using shell variables
INPUT=$(jq -n \
  --arg url "https://example.com" \
  --arg username "$WORKFLOW_USER" \
  --arg password "$WORKFLOW_PASS" \
  '{url: $url, username: $username, password: $password}')

# Run workflow with JSON from shell variable
python -m src.cli.workflow_runner login --input "$INPUT"
```

### Processing Large Batch Files

```bash
# Split large workflows.json into chunks
split -l 100 workflows.json workflows_chunk_

# Run each chunk with concurrency
for chunk in workflows_chunk_*; do
  python -m src.cli.batch_runner \
    --input "$chunk" \
    --max-concurrent 10 &
done

# Wait for all to complete
wait
```

### Filtering and Transforming Results

```bash
# Run batch and save results
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 10 > results.json

# Get only failed executions
jq '.results | map(select(.success == false))' results.json

# Get execution times for performance analysis
jq '.results | map({execution_id, elapsed_seconds})' results.json

# Generate summary report
jq '{
  total: .total_workflows,
  succeeded: .succeeded,
  failed: .failed,
  avg_time: (.results | map(.elapsed_seconds) | add / length),
  min_time: (.results | map(.elapsed_seconds) | min),
  max_time: (.results | map(.elapsed_seconds) | max)
}' results.json
```

### Custom Workflow Input Validation

```bash
# Validate JSON before running
python << 'EOF'
import json
import sys

try:
    with open('input.json') as f:
        data = json.load(f)
    
    # Validate required fields
    required = ['url', 'username', 'password']
    for field in required:
        if field not in data:
            print(f"Error: Missing required field '{field}'", file=sys.stderr)
            sys.exit(1)
    
    print("✓ Input validation passed")
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON: {e}", file=sys.stderr)
    sys.exit(1)
EOF
```

### Parallel Workflow Execution Script

```bash
#!/bin/bash
# run_all_workflows.sh

set -e  # Exit on error

INPUT_DIR="./inputs"
LOG_DIR="./logs"
MAX_CONCURRENT=10

mkdir -p "$LOG_DIR"

# Counter for tracking
TOTAL=0
COMPLETED=0

# Run all .json files in inputs directory
for input_file in "$INPUT_DIR"/*.json; do
    workflow_name=$(basename "$input_file" .json)
    
    python -m src.cli.workflow_runner login \
        --input "$(cat "$input_file" | jq -c .)" \
        --log-dir "$LOG_DIR" \
        --output-format json > "$LOG_DIR/$workflow_name.result.json" &
    
    TOTAL=$((TOTAL + 1))
    
    # Limit concurrency
    if (( TOTAL % MAX_CONCURRENT == 0 )); then
        wait
    fi
done

# Wait for remaining
wait

echo "✓ All $TOTAL workflows completed"
```

### Error Handling in Batch Processing

```bash
# Check for failed workflows and retry
python << 'EOF'
import json
import subprocess
import sys

# Run batch
result = subprocess.run([
    'python', '-m', 'src.cli.batch_runner',
    '--input', 'workflows.json',
    '--max-concurrent', '10'
], capture_output=True, text=True)

data = json.loads(result.stdout)

# Find failed executions
failed = [r for r in data['results'] if not r['success']]

if failed:
    print(f"Found {len(failed)} failed workflows:")
    for f in failed:
        print(f"  - {f['execution_id']}: {f.get('error', 'Unknown error')}")
    
    # Retry failed workflows
    print("\nRetrying failed workflows...")
    for f in failed:
        print(f"  Retrying {f['execution_id']}...")
        # Re-run just this one
EOF
```

## Logging

All tools support logging to files:

```bash
# Single workflow with logging
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"user","password":"pass"}' \
    --log-dir ./logs

# Check logs
tail -f ./logs/login.log

# Batch with logging
python -m src.cli.batch_runner \
    --input workflows.json \
    --log-dir ./batch-logs

# Each execution has its log
tail -f ./batch-logs/exec-001.log

# Filter logs
grep "ERROR" ./batch-logs/*.log
grep "SUCCESS" ./batch-logs/*.log | wc -l
```

## Best Practices

1. **Single Workflows**: Use `workflow_runner` with `--input` JSON parameter
   ```bash
   python -m src.cli.workflow_runner <type> --input '<json>'
   ```

2. **Batch Operations**: Use `batch_runner` with JSON file
   ```bash
   python -m src.cli.batch_runner --input workflows.json --max-concurrent 10
   ```

3. **External Control**: Use `mcp_server_runner` for AI/agent control
   ```bash
   python -m src.cli.mcp_server_runner
   ```

4. **Resumption**: Use `resume_workflow` for failed/paused workflows
   ```bash
   python -m src.cli.resume_workflow <execution_id>
   ```

5. **Input Format**: Always use JSON parameters via `--input` flag
   - Single workflow: Pass JSON as string with proper escaping
   - Batch: Create workflows.json with array of objects

6. **Concurrency**: Start with `--max-concurrent 5`, tune based on resources
   - Light workflows: 50-100 concurrent
   - Medium workflows: 20-30 concurrent
   - Heavy workflows: 5-10 concurrent

7. **Logging**: Always enable `--log-dir` for production and debugging
   ```bash
   python -m src.cli.workflow_runner login --input '...' --log-dir ./logs
   ```

8. **Output Format**: Use `--output-format json` for scripts, `text` for humans

## Troubleshooting

### Invalid JSON input error
```bash
# Error: Invalid JSON input
python -m src.cli.workflow_runner login --input '{"url":"example.com"}'

# Fix: Ensure JSON is properly formatted and escaped
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"user","password":"pass"}'

# Validate JSON first using jq
cat input.json | jq . > /dev/null
python -m src.cli.workflow_runner login --input "$(cat input.json | jq -c .)"
```

### Workflow execution not starting
```bash
# 1. Enable logging to see errors
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"user","password":"pass"}' \
    --log-dir ./logs

# 2. Check log file for error details
cat logs/login.log

# 3. Verify input parameters are complete
python << 'EOF'
import json
data = json.loads('{"url":"https://example.com","username":"user","password":"pass"}')
print("Input parameters:", json.dumps(data, indent=2))
EOF
```

### Workflows timeout
```bash
# Check if workflow is actually running
tail -f ./logs/login.log

# Enable more verbose logging
export LOG_LEVEL=DEBUG
python -m src.cli.workflow_runner login --input '...' --log-dir ./logs
```

### High memory usage with batch
```bash
# Reduce max concurrent executions
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 5  # Lower from current value

# Monitor memory and CPU
watch -n 1 'ps aux | grep python | grep workflow'

# Kill batch runner if needed
pkill -f "src.cli.batch_runner"
```

### MCP server not responding
```bash
# Check if server is running
ps aux | grep mcp_server_runner

# Try restarting
pkill -f "src.cli.mcp_server_runner"
python -m src.cli.mcp_server_runner &
```

## See Also

- [TESTING_GUIDE.md](TESTING_GUIDE.md) - How to test workflows
- [docs/architecture.md](docs/architecture.md) - System architecture
- [docs/performance-tuning.md](docs/performance-tuning.md) - Performance optimization
