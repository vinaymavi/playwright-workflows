# CLI Format Summary - All Tools Use JSON Input

This document shows the correct CLI format for all tools in the `src/cli` folder.

## Core Principle

**All CLI tools use consistent JSON input via `--input` parameter, not individual flags.**

```bash
# ✅ CORRECT FORMAT
python -m src.cli.workflow_runner <workflow_type> --input '<json_parameters>'

# ❌ OLD FORMAT (don't use)
python -m src.cli.workflow_runner --workflow-type <type> --url <url> --username <user>
```

---

## 1. Workflow Runner

Run a single workflow with JSON input.

### Format
```bash
python -m src.cli.workflow_runner <type> \
    --input '<json>' \
    [--output-format {json,text}] \
    [--log-dir <path>]
```

### Examples

**Login workflow:**
```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"user","password":"pass"}'
```

**Form filling workflow:**
```bash
python -m src.cli.workflow_runner form_filling \
    --input '{"url":"https://example.com/form","fields":{"name":"John","email":"john@example.com"}}'
```

**With all options:**
```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"user","password":"pass"}' \
    --output-format json \
    --log-dir ./logs
```

**Using file input (easier for complex JSON):**
```bash
# Create input file
cat > input.json << 'EOF'
{
  "url": "https://example.com",
  "username": "testuser",
  "password": "testpass"
}
EOF

# Run with file
python -m src.cli.workflow_runner login \
    --input "$(cat input.json | jq -c .)" \
    --log-dir ./logs
```

### Parameters

| Parameter | Short | Type | Required | Default |
|-----------|-------|------|----------|---------|
| `workflow_type` | N/A | string | ✅ Yes | N/A |
| `--input` | `-i` | JSON | ✅ Yes | N/A |
| `--output-format` | `-f` | json\|text | No | json |
| `--log-dir` | `-l` | path | No | data/logs |

---

## 2. Batch Runner

Run multiple workflows in parallel from a JSON file.

### Format
```bash
python -m src.cli.batch_runner \
    --input <workflows.json> \
    [--max-concurrent <num>] \
    [--output-format {json,text}] \
    [--log-dir <path>]
```

### Input File Format (workflows.json)
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

### Examples

**Run 10 workflows with 5 concurrent:**
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 5
```

**Generate workflows file and run:**
```bash
# Generate workflows
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

# Run batch
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 10 \
    --log-dir ./logs
```

**With text output and logging:**
```bash
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 5 \
    --output-format text \
    --log-dir ./batch-logs
```

### Parameters

| Parameter | Short | Type | Required | Default |
|-----------|-------|------|----------|---------|
| `--input` | `-i` | file path | ✅ Yes | N/A |
| `--max-concurrent` | N/A | integer | No | 5 |
| `--output-format` | `-f` | json\|text | No | json |
| `--log-dir` | `-l` | path | No | data/logs |

---

## 3. MCP Server Runner

Run MCP server for external control via JSON-RPC 2.0.

### Format
```bash
python -m src.cli.mcp_server_runner
```

### Examples

**Start server:**
```bash
python -m src.cli.mcp_server_runner
```

**In background:**
```bash
python -m src.cli.mcp_server_runner &
MCP_PID=$!

# ... do work ...

kill $MCP_PID
```

**With Docker:**
```dockerfile
CMD ["python", "-m", "src.cli.mcp_server_runner"]
```

### Available Tools (via JSON-RPC)

All tools require JSON-RPC 2.0 format.

**start_workflow:**
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
      }
    }
  }
}
```

**resolve_checkpoint:**
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

### Parameters

None - server accepts JSON-RPC 2.0 on stdin/stdout

---

## 4. Resume Workflow

Resume a paused or failed workflow.

### Format
```bash
python -m src.cli.resume_workflow <execution_id> \
    [--execution-dir <path>] \
    [--verbose]
```

### Examples

**Resume with auto strategy selection:**
```bash
python -m src.cli.resume_workflow exec-123
```

**With custom directory:**
```bash
python -m src.cli.resume_workflow exec-123 \
    --execution-dir /data/executions
```

**With verbose logging:**
```bash
python -m src.cli.resume_workflow exec-123 \
    --verbose
```

### Parameters

| Parameter | Short | Type | Required | Default |
|-----------|-------|------|----------|---------|
| `execution_id` | N/A | string | ✅ Yes | N/A |
| `--execution-dir` | N/A | path | No | data/executions |
| `--verbose` | N/A | flag | No | false |

---

## JSON Input Examples

### Login Workflow
```json
{
  "url": "https://example.com/login",
  "username": "testuser",
  "password": "testpass"
}
```

### Form Filling Workflow
```json
{
  "url": "https://example.com/form",
  "fields": {
    "name": "John Doe",
    "email": "john@example.com",
    "message": "Hello World"
  }
}
```

### File Upload Workflow
```json
{
  "url": "https://example.com/upload",
  "file_path": "/path/to/file.pdf",
  "upload_field": "document"
}
```

---

## Common Patterns

### Using Environment Variables
```bash
export WORKFLOW_USER="testuser"
export WORKFLOW_PASS="testpass"

INPUT=$(jq -n \
  --arg url "https://example.com" \
  --arg username "$WORKFLOW_USER" \
  --arg password "$WORKFLOW_PASS" \
  '{url: $url, username: $username, password: $password}')

python -m src.cli.workflow_runner login --input "$INPUT"
```

### Reading JSON from File
```bash
python -m src.cli.workflow_runner login \
    --input "$(cat input.json | jq -c .)" \
    --log-dir ./logs
```

### Processing Batch Results
```bash
# Run batch and save results
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 10 > results.json

# Find failed workflows
jq '.results | map(select(.success == false))' results.json

# Get summary statistics
jq '{
  total: .total_workflows,
  succeeded: .succeeded,
  failed: .failed,
  avg_time: (.results | map(.elapsed_seconds) | add / length)
}' results.json
```

### Retry Failed Workflows
```bash
# Get failed executions
FAILED=$(python -m src.cli.batch_runner \
    --input workflows.json | \
    jq '.results | map(select(.success == false)) | map(.execution_id)')

# For each failed, re-run...
for exec_id in $FAILED; do
  # Find original params and retry
done
```

---

## Key Points

1. **Always use `--input` for parameters** - No individual flags like `--url`, `--username`
2. **JSON must be properly escaped** - Use single quotes for bash, double-escape if needed
3. **Use `jq` for validation** - `cat file.json | jq .` validates JSON
4. **Batch uses file input** - `batch_runner` reads workflows.json, not command-line parameters
5. **Single workflows use inline JSON** - `workflow_runner` takes JSON as string parameter
6. **All tools support `--log-dir`** - Always use for debugging
7. **Check exit codes** - `echo $?` shows success (0) or failure (non-zero)

---

## Help & Examples

Get help from any tool:
```bash
python -m src.cli.workflow_runner --help
python -m src.cli.batch_runner --help
python -m src.cli.resume_workflow --help
```

---

## Related Documentation

- [CLI_GUIDE.md](CLI_GUIDE.md) - Complete guide with detailed examples
- [CLI_RUNBOOK.md](CLI_RUNBOOK.md) - Deep dive into why `-m` module execution works
- [MODULE_EXECUTION_CHEATSHEET.md](MODULE_EXECUTION_CHEATSHEET.md) - Quick reference for `-m` flag
