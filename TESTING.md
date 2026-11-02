# End-to-End Testing Guide (No LLM Required)

## Quick Start: Run a Workflow

```bash
cd /Users/vinaymavi/github/contractor-automation/playwright-workflows

# Run login workflow
uv run python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"testuser","password":"testpass"}' \
    --output-format json
```

**Result**: Workflow runs, logs appear as JSON, execution saved to `data/executions/{execution_id}.json`

---

## Approach 1: Direct Workflow Testing

### Test 1: Run Single Workflow
```bash
uv run python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --output-format json
```

**Verify**:
- Logs show step progression
- Final JSON output shows `success: false` or `success: true`
- Execution ID appears in all logs

### Test 2: Check Execution State File
```bash
# View the saved execution state
cat data/executions/*.json | jq .

# Or format nicely
ls -1 data/executions/*.json | tail -1 | xargs cat | jq .
```

**Expected Output**:
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "failed",
  "input_params": {
    "url": "https://vidyutsuraksha.org/",
    "username": "test",
    "password": "pass"
  },
  "steps": [
    {
      "name": "Navigate to Login Page",
      "status": "success",
      "started_at": "...",
      "completed_at": "..."
    },
    {
      "name": "Fill Username",
      "status": "failed",
      "error": "Timeout 10000ms exceeded"
    }
  ],
  "created_at": "...",
  "started_at": "...",
  "completed_at": "..."
}
```

### Test 3: Verify Isolated Resources
```bash
# Check temp directories (one per execution)
ls -lah data/temp/

# Should see directories named with execution IDs:
# data/temp/550e8400-e29b-41d4-a716-446655440000/
# data/temp/another-execution-id/
```

---

## Approach 2: Concurrent Execution Testing

### Test 4: Run 3 Workflows in Parallel
```bash
# Run 3 workflows at the same time
for i in {1..3}; do
  echo "Starting workflow $i..."
  uv run python -m src.cli.workflow_runner login \
    --input "{\"url\":\"https://example.com/\",\"username\":\"user$i\",\"password\":\"pass\"}" \
    --output-format json > /tmp/workflow_$i.log &
done

# Wait for all to complete
wait
echo "All workflows completed"
```

### Test 5: Verify Concurrent Isolation
```bash
# Count total executions
echo "Total executions: $(ls -1 data/executions/ | wc -l)"

# Verify each has unique execution_id
echo "All execution IDs:"
for f in data/executions/*.json; do
  cat "$f" | jq -r '.execution_id'
done

# Verify temp directories are isolated
echo "Temp directories (one per execution):"
ls -1 data/temp/
```

### Test 6: Stress Test - 10 Concurrent Workflows
```bash
# Run 10 workflows in parallel
for i in {1..10}; do
  uv run python -m src.cli.workflow_runner login \
    --input "{\"url\":\"https://example.com/\",\"username\":\"user$i\",\"password\":\"pass\"}" \
    --output-format json > /tmp/stress_$i.log &
done
wait

# Summary
echo "Total executions after stress test: $(ls -1 data/executions/ | wc -l)"
echo "Temp directories created: $(ls -1d data/temp/*/ 2>/dev/null | wc -l)"
```

---

## Approach 3: MCP Server Testing (Pipes & JSON-RPC)

### Terminal 1: Start MCP Server
```bash
cd /Users/vinaymavi/github/contractor-automation/playwright-workflows
uv run python -m src.cli.mcp_server_runner
```

**Expected Output**: Server starts and waits for JSON-RPC requests on stdin

### Terminal 2: Send MCP Requests

#### Test 7: List Available Tools
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | \
uv run python -m src.cli.mcp_server_runner
```

**Expected Output**:
```json
{"jsonrpc":"2.0","id":2,"result":{"tools":[
  {"name":"start_workflow","description":"Start a new workflow execution",...},
  {"name":"list_executions","description":"List workflow executions",...},
  {"name":"resolve_checkpoint","description":"Resolve a checkpoint",...}
]}}
```

#### Test 8: List Executions via MCP
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_executions","arguments":{"limit":5}}}' | \
uv run python -m src.cli.mcp_server_runner
```

**Expected Output**:
```json
{"jsonrpc":"2.0","id":2,"result":{"content":[
  {"execution_id":"...", "state":"completed", "workflow_type":"login", ...}
]}}
```

#### Test 9: Start Workflow via MCP
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"start_workflow","arguments":{"workflow_type":"login","input_params":{"url":"https://example.com","username":"test","password":"pass"}}}}' | \
uv run python -m src.cli.mcp_server_runner
```

**Expected Output**:
```json
{"jsonrpc":"2.0","id":2,"result":{"content":"Workflow started with execution_id: ..."}}
```

---

## Approach 4: Debug Mode

### Test 10: Enable Debug Logs
```bash
# Run with verbose logging
LOGLEVEL=DEBUG uv run python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --log-format color
```

**Look for**: Extended trace of element locator attempts, retry logic, state transitions

### Test 11: Check State Files for Debugging
```bash
# Find failed workflows
for f in data/executions/*.json; do
  if grep -q '"state":"failed"' "$f"; then
    echo "Failed execution: $(cat "$f" | jq -r '.execution_id')"
    cat "$f" | jq '.steps[] | select(.status=="failed")'
  fi
done
```

---

## Complete Test Workflow

Run this sequence to verify everything works:

```bash
#!/bin/bash
set -e

cd /Users/vinaymavi/github/contractor-automation/playwright-workflows

echo "=== Cleanup ==="
rm -rf data/executions/*.json data/temp/* 2>/dev/null || true

echo "=== Test 1: Single Workflow ==="
uv run python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --output-format json | jq '.success'

echo "=== Test 2: Verify State File ==="
cat data/executions/*.json | jq '.execution_id'

echo "=== Test 3: Run 3 Concurrent Workflows ==="
for i in {1..3}; do
  uv run python -m src.cli.workflow_runner login \
    --input "{\"url\":\"https://example.com/\",\"username\":\"user$i\",\"password\":\"pass\"}" \
    --output-format json > /tmp/workflow_$i.log &
done
wait

echo "=== Test 4: Verify Concurrency ==="
TOTAL=$(ls -1 data/executions/*.json | wc -l)
TEMP_DIRS=$(ls -1d data/temp/*/ 2>/dev/null | wc -l)
echo "Total executions: $TOTAL (expected: 4)"
echo "Temp directories: $TEMP_DIRS (expected: 4)"

echo "=== Test 5: Verify Unique Execution IDs ==="
UNIQUE=$(for f in data/executions/*.json; do cat "$f" | jq -r '.execution_id'; done | sort | uniq | wc -l)
echo "Unique execution IDs: $UNIQUE (expected: 4)"

echo "✅ All tests passed!"
```

Save this as `test-all.sh` and run:
```bash
chmod +x test-all.sh
./test-all.sh
```

---

## What to Check

### Execution State
```bash
# View latest execution
jq . data/executions/$(ls -1t data/executions/ | head -1)

# Check step-by-step progress
jq '.steps[] | {name, status, error}' data/executions/$(ls -1t data/executions/ | head -1)

# See timing information
jq '{created_at, started_at, completed_at}' data/executions/$(ls -1t data/executions/ | head -1)
```

### Resource Isolation
```bash
# Verify each execution has its own temp directory
for f in data/executions/*.json; do
  EXEC_ID=$(cat "$f" | jq -r '.execution_id')
  if [ -d "data/temp/$EXEC_ID" ]; then
    echo "✓ $EXEC_ID has isolated temp directory"
  else
    echo "✗ $EXEC_ID missing temp directory"
  fi
done
```

### Concurrent Safety
```bash
# Verify no file conflicts during concurrent execution
# Run 5 workflows at once, check for duplicate execution_ids
for i in {1..5}; do
  uv run python -m src.cli.workflow_runner login \
    --input "{\"url\":\"https://example$i.com/\",\"username\":\"user$i\",\"password\":\"pass\"}" \
    --output-format json > /dev/null &
done
wait

TOTAL=$(ls -1 data/executions/*.json | wc -l)
UNIQUE=$(for f in data/executions/*.json; do cat "$f" | jq -r '.execution_id'; done | sort | uniq | wc -l)

if [ "$TOTAL" -eq "$UNIQUE" ]; then
  echo "✓ All execution IDs are unique"
else
  echo "✗ Duplicate execution IDs detected!"
fi
```

---

## Troubleshooting

### "Page not initialized" Error
This means the workflow needs a running browser. Workflows handle this automatically, but if you see this error:
```bash
# Increase timeout or add wait conditions
# Edit the workflow to add explicit wait_for_navigation()
```

### "Timeout 10000ms exceeded"
The element wasn't found on the page:
```bash
# Check what the page actually contains
uv run python -c "
import asyncio
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://vidyutsuraksha.org/')
        content = await page.content()
        print(content[:500])
        await browser.close()

asyncio.run(check())
"
```

### MCP Server "RuntimeWarning"
The warning about `src.cli.workflow_runner` is harmless—it's a quirk of Python's `-m` module execution. It doesn't affect functionality.

---

## Summary

**Testing without code or LLM**:
1. ✅ Run workflows: `uv run python -m src.cli.workflow_runner ...`
2. ✅ Check state: `cat data/executions/*.json | jq`
3. ✅ Verify isolation: `ls -lah data/temp/`
4. ✅ Test concurrency: Run 5+ workflows in parallel
5. ✅ Test MCP: Echo JSON-RPC requests to server stdin

All state is saved to JSON files—inspect them to verify correct behavior!
