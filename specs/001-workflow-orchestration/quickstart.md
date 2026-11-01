# Quickstart Validation Guide

**Status**: Phase 1 Design  
**Purpose**: Validate end-to-end feature completeness before implementation  
**Target Audience**: QA, integration testers, feature reviewers

---

## Overview

This guide documents 5 runnable validation scenarios that prove the workflow orchestration framework works end-to-end. Each scenario tests a distinct feature area:

1. **Scenario A**: Basic workflow execution (happy path)
2. **Scenario B**: Checkpoint pause/resume within timeout window (quick resume)
3. **Scenario C**: Checkpoint pause/resume after timeout (slow resume + session recovery)
4. **Scenario D**: Concurrent parallel execution
5. **Scenario E**: Error handling and retry behavior

All scenarios assume a local development environment with:
- Python 3.10+
- Playwright installed and chromium/firefox browser binaries available
- MCP server running on stdio
- Test web application available (e.g., localhost:8000 or https://example.com/test-sandbox)

---

## Scenario A: Basic Workflow Execution (Happy Path)

**Feature**: Single workflow runs to completion without checkpoints  
**Expected Duration**: < 30 seconds  
**Success Criteria**: Execution status is `completed`, result is returned

### Prerequisites

```bash
# Start test web server (if using local test app)
cd tests/fixtures/web_server
python3 server.py --port 8000

# In another terminal, start MCP server
cd src/mcp_server
python3 run_stdio_server.py
```

### Setup

```bash
# 1. Export test environment
export PLAYWRIGHT_TEST_WEB_URL="http://localhost:8000"
export WORKFLOW_FRAMEWORK_ENV="test"

# 2. Prepare test data
mkdir -p data/executions data/logs data/artifacts

# 3. Clear prior execution state
rm -f data/executions/*.json data/logs/*.log
```

### Run

```bash
# Execute happy-path workflow (provided in tests/workflows/simple_form_fill.py)
python3 -m src.cli.workflow_runner \
  --workflow simple_form_fill \
  --input '{"form_url": "http://localhost:8000/simple-form", "name": "Test User", "email": "test@example.com"}' \
  --output-format json

# Expected output (within 30 seconds):
# {
#   "execution_id": "12345678-1234-1234-1234-123456789abc",
#   "status": "completed",
#   "result": {
#     "submitted": true,
#     "confirmation_message": "Form submitted successfully"
#   },
#   "duration_seconds": 12.5,
#   "steps_completed": 5,
#   "checkpoints_paused": 0
# }
```

### Verify

```bash
# 1. Check execution log
cat data/logs/12345678-1234-1234-1234-123456789abc.log
# Expected: JSON array of events (execution_started, step_started, step_completed, execution_completed)

# 2. Validate execution state file
cat data/executions/12345678-1234-1234-1234-123456789abc.json | python3 -m json.tool
# Expected: Complete execution context (all steps, no pending checkpoints, status: completed)

# 3. Query via MCP server
python3 -c "
import json
import subprocess

result = subprocess.run([
    'python3', '-m', 'src.mcp_server.client',
    'get_execution_status',
    '--execution-id', '12345678-1234-1234-1234-123456789abc'
], capture_output=True, text=True)

print(json.dumps(json.loads(result.stdout), indent=2))
# Expected: status: completed, error: null, pending_checkpoint: null
"
```

---

## Scenario B: Checkpoint Pause/Resume (Quick Resume ≤5 min)

**Feature**: Workflow pauses at checkpoint; agent decides within 5 minutes; workflow resumes from same session  
**Expected Duration**: 2-5 minutes total (30 seconds run + ~3 minutes pause + 30 seconds resume)  
**Success Criteria**: Browser session preserved, no re-login required, workflow completes

### Prerequisites

Same as Scenario A, plus:
- MCP server must be running and able to send checkpoint notification to client
- Client (test harness) must be able to receive and respond to checkpoint notification

### Setup

```bash
# 1. Export environment
export PLAYWRIGHT_TEST_WEB_URL="http://localhost:8000"
export WORKFLOW_FRAMEWORK_ENV="test"
export MCP_CHECKPOINT_TIMEOUT_SOFT_SECONDS="120"  # 2 min soft timeout
export MCP_CHECKPOINT_TIMEOUT_HARD_SECONDS="300"  # 5 min hard timeout

# 2. Prepare test data
mkdir -p data/executions data/logs data/artifacts
rm -f data/executions/*.json data/logs/*.log
```

### Run (Part 1: Trigger Checkpoint)

```bash
# Start workflow that will pause at checkpoint
python3 -m src.cli.workflow_runner \
  --workflow multi_step_form_with_checkpoint \
  --input '{
    "form_url": "http://localhost:8000/multi-step-form",
    "step_1_data": {"name": "Alice", "email": "alice@example.com"},
    "step_2_data": {"address": "123 Main St"},
    "require_agent_confirmation": true
  }' \
  --output-format json \
  --background &

EXECUTION_ID="<captured from background job or via polling>"

# Wait for checkpoint notification (should arrive ~10 seconds into execution)
sleep 15

# Poll checkpoint status
python3 -c "
import json
import subprocess

result = subprocess.run([
    'python3', '-m', 'src.mcp_server.client',
    'get_execution_status',
    '--execution-id', '$EXECUTION_ID'
], capture_output=True, text=True)

status = json.loads(result.stdout)
print(f\"Status: {status['status']}\")
print(f\"Pending Checkpoint: {status.get('pending_checkpoint')}\")
# Expected: status: paused, pending_checkpoint: {...with question and timeout_seconds}
"
```

### Run (Part 2: Resolve Checkpoint)

```bash
# Agent (or test harness) sends decision to resume
python3 -m src.mcp_server.client \
  resolve_checkpoint \
  --execution-id "$EXECUTION_ID" \
  --checkpoint-id "<from pending_checkpoint.checkpoint_id>" \
  --decision '{"value": "proceed", "agent_reason": "Form looks correct"}'

# Expected response:
# {
#   "execution_id": "...",
#   "status": "running",
#   "resolved_at": "2026-11-01T12:34:56Z"
# }
```

### Verify

```bash
# 1. Check execution completed within 5 minutes of resumption
sleep 45  # Allow time to complete

python3 -c "
import json
import subprocess
from datetime import datetime

result = subprocess.run([
    'python3', '-m', 'src.mcp_server.client',
    'get_execution_status',
    '--execution-id', '$EXECUTION_ID'
], capture_output=True, text=True)

status = json.loads(result.stdout)
print(f\"Final Status: {status['status']}\")
print(f\"Completed Steps: {status['completed_steps']} / {status['total_steps']}\")
# Expected: status: completed, all steps done, no error
"

# 2. Verify session was preserved (no re-login in logs)
grep "session_recovered\|re_auth\|login" data/logs/$EXECUTION_ID.log
# Expected: No matches (session was kept alive)

# 3. Verify checkpoint resolution recorded
cat data/executions/$EXECUTION_ID.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
cp = [c for c in data.get('checkpoints', []) if c.get('resolved_at')]
if cp:
    print(f\"Checkpoint resolved at: {cp[0]['resolved_at']}\")
    print(f\"Resolution time from creation: {(datetime.fromisoformat(cp[0]['resolved_at']) - datetime.fromisoformat(cp[0]['created_at'])).total_seconds()} seconds\")
"
```

---

## Scenario C: Checkpoint Timeout + Session Recovery

**Feature**: Workflow pauses at checkpoint; agent does not respond within 5 minutes; workflow state persists; workflow is manually resumed with session recovery (re-auth)  
**Expected Duration**: 5+ minutes total (30 seconds run + 5 min wait + 30 seconds resume + re-auth)  
**Success Criteria**: After timeout, execution marked as failed; on manual resume, session is recovered (re-auth triggered), workflow completes

### Prerequisites

Same as Scenario B, plus:
- Credentials file configured with test user password
- Test web server supports 401/403 detection and re-auth flow

### Setup

```bash
# 1. Export environment
export PLAYWRIGHT_TEST_WEB_URL="http://localhost:8000"
export WORKFLOW_FRAMEWORK_ENV="test"
export MCP_CHECKPOINT_TIMEOUT_SOFT_SECONDS="120"
export MCP_CHECKPOINT_TIMEOUT_HARD_SECONDS="300"  # 5 min hard timeout

# 2. Prepare test data
mkdir -p data/executions data/logs data/artifacts data/credentials
rm -f data/executions/*.json data/logs/*.log

# 3. Store encrypted test credentials
python3 -m src.utils.credential_manager \
  --action store \
  --key "test_user_login" \
  --username "test_user" \
  --password "test_password_123" \
  --master-password "dev_master_123"
```

### Run (Part 1: Trigger Checkpoint & Wait for Timeout)

```bash
# Start workflow that will pause at checkpoint
python3 -m src.cli.workflow_runner \
  --workflow multi_step_secure_form \
  --input '{
    "form_url": "http://localhost:8000/secure-form",
    "auth_required": true,
    "cred_key": "test_user_login",
    "require_agent_confirmation_step_2": true
  }' \
  --output-format json \
  --background &

EXECUTION_ID="<captured>"
sleep 15  # Wait for checkpoint

# Verify checkpoint is pending
python3 -c "
import json, subprocess
result = subprocess.run([
    'python3', '-m', 'src.mcp_server.client',
    'get_execution_status', '--execution-id', '$EXECUTION_ID'
], capture_output=True, text=True)
print(json.loads(result.stdout).get('pending_checkpoint', {}).get('time_remaining_seconds'))
"

# DO NOT resolve checkpoint - let it timeout
# Wait for hard timeout (5 minutes)
sleep 300

# Verify execution is now marked as failed
python3 -c "
import json, subprocess
result = subprocess.run([
    'python3', '-m', 'src.mcp_server.client',
    'get_execution_status', '--execution-id', '$EXECUTION_ID'
], capture_output=True, text=True)
status = json.loads(result.stdout)
print(f\"Status: {status['status']}\")
print(f\"Error: {status.get('error', {}).get('code')}\")
# Expected: status: failed, error code: CHECKPOINT_TIMEOUT
"
```

### Run (Part 2: Resume with Session Recovery)

```bash
# Framework detects session expired (401/403) and replays steps + re-authenticates
python3 -m src.cli.workflow_runner \
  --execution-id "$EXECUTION_ID" \
  --action resume \
  --recovery-strategy replay_and_reauth \
  --master-password "dev_master_123" \
  --output-format json \
  --background &

sleep 30  # Allow re-auth and replay

# Poll for completion
python3 -c "
import json, subprocess, time
for _ in range(10):
    result = subprocess.run([
        'python3', '-m', 'src.mcp_server.client',
        'get_execution_status', '--execution-id', '$EXECUTION_ID'
    ], capture_output=True, text=True)
    status = json.loads(result.stdout)
    if status['status'] == 'completed':
        print(f\"Resumed and completed! Steps: {status['completed_steps']}/{status['total_steps']}\")
        break
    print(f\"Status: {status['status']}, waiting...\")
    time.sleep(5)
"
```

### Verify

```bash
# 1. Check final status is completed
python3 -c "
import json, subprocess
result = subprocess.run([
    'python3', '-m', 'src.mcp_server.client',
    'get_execution_status', '--execution-id', '$EXECUTION_ID'
], capture_output=True, text=True)
status = json.loads(result.stdout)
print(f\"Final Status: {status['status']}\")
# Expected: status: completed
"

# 2. Verify session recovery events in logs
grep -c "session_expired\|session_recovered\|re_auth" data/logs/$EXECUTION_ID.log
# Expected: >= 2 (at least session_expired and re_auth events)

# 3. Verify replay was performed
grep "step_replayed\|replay_mode" data/logs/$EXECUTION_ID.log
# Expected: At least one step replayed event

# 4. Check execution state for recovery metadata
cat data/executions/$EXECUTION_ID.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Recovery count: {data.get('recovery_metadata', {}).get('recovery_count', 0)}\")
print(f\"Last recovery method: {data.get('recovery_metadata', {}).get('last_method')}\")
# Expected: recovery_count: 1, last_method: replay_and_reauth
"
```

---

## Scenario D: Concurrent Parallel Execution

**Feature**: Multiple workflows execute in parallel; framework respects concurrency limits (e.g., max 5 concurrent)  
**Expected Duration**: ~1-2 minutes (10 x 15-second workflows running in groups of 5)  
**Success Criteria**: All executions complete successfully; no resource contention; browser contexts isolated

### Prerequisites

```bash
# Ensure test server can handle concurrent requests
cd tests/fixtures/web_server
python3 server.py --port 8000 --workers 10

# Verify MCP server is running and supports concurrent client connections
```

### Setup

```bash
# Export environment
export PLAYWRIGHT_TEST_WEB_URL="http://localhost:8000"
export WORKFLOW_FRAMEWORK_ENV="test"
export MCP_CONCURRENT_WORKFLOWS_LIMIT="5"
export MCP_BROWSER_CONTEXT_POOL_SIZE="5"

# Prepare test data
mkdir -p data/executions data/logs data/artifacts
rm -f data/executions/*.json data/logs/*.log
```

### Run

```bash
# Start 10 simple form-fill workflows in rapid succession
EXECUTION_IDS=()
for i in {1..10}; do
  python3 -m src.cli.workflow_runner \
    --workflow simple_form_fill \
    --input "{
      \"form_url\": \"http://localhost:8000/simple-form\",
      \"name\": \"User $i\",
      \"email\": \"user$i@example.com\"
    }" \
    --output-format json \
    --background > /tmp/exec_$i.out 2>&1 &
  
  EXECUTION_IDS+=($!)
  sleep 1  # 1 second stagger to simulate real-world timing
done

# Wait for all to complete (should take ~2 minutes even though each is 15 seconds)
# because max 5 run concurrently
wait ${EXECUTION_IDS[@]}

# Extract execution IDs from background job outputs
grep -h "execution_id" /tmp/exec_*.out | jq -r .execution_id | sort > /tmp/execution_ids.txt
```

### Verify

```bash
# 1. Verify all 10 executions completed
COMPLETED=$(grep -l '"status": "completed"' data/executions/*.json | wc -l)
echo "Completed: $COMPLETED / 10"
# Expected: 10

# 2. Check concurrency limits were respected (no more than 5 simultaneous)
python3 -c "
import json
from pathlib import Path

executions = []
for f in Path('data/executions').glob('*.json'):
    with open(f) as fp:
        data = json.load(fp)
        executions.append({
            'id': data['execution_id'],
            'started': data['started_at'],
            'ended': data['ended_at']
        })

# Sort by start time
executions.sort(key=lambda x: x['started'])

# Check max concurrent at any point
from datetime import datetime, timedelta
max_concurrent = 0
for i, exec in enumerate(executions):
    started = datetime.fromisoformat(exec['started'].replace('Z', '+00:00'))
    ended = datetime.fromisoformat(exec['ended'].replace('Z', '+00:00'))
    
    concurrent = sum(
        1 for other in executions
        if datetime.fromisoformat(other['started'].replace('Z', '+00:00')) <= started
        and datetime.fromisoformat(other['ended'].replace('Z', '+00:00')) >= started
    )
    max_concurrent = max(max_concurrent, concurrent)

print(f'Max concurrent: {max_concurrent}')
# Expected: 5 (respects limit)
"

# 3. Verify no browser context conflicts (each execution isolated)
grep "browser_context_created\|browser_context_closed" data/logs/*.log | wc -l
# Expected: 20 (2 per execution: created and closed)

# 4. Summary statistics
python3 -c "
import json
from pathlib import Path
import statistics

durations = []
for f in Path('data/executions').glob('*.json'):
    with open(f) as fp:
        data = json.load(fp)
        started = __import__('datetime').datetime.fromisoformat(data['started_at'].replace('Z', '+00:00'))
        ended = __import__('datetime').datetime.fromisoformat(data['ended_at'].replace('Z', '+00:00'))
        durations.append((ended - started).total_seconds())

print(f'Min duration: {min(durations):.1f}s')
print(f'Max duration: {max(durations):.1f}s')
print(f'Mean duration: {statistics.mean(durations):.1f}s')
print(f'Total time (wall clock): ~120-150 seconds (queue effect)')
"
```

---

## Scenario E: Error Handling and Retry Behavior

**Feature**: Transient errors trigger auto-retry; permanent errors escalate to checkpoint; framework classifies errors correctly  
**Expected Duration**: 1-2 minutes  
**Success Criteria**: Transient errors are retried; permanent errors show checkpoint; retry counts match config

### Prerequisites

```bash
# Test server must support simulating failures
# (e.g., /api/fail-once endpoint that fails first, succeeds second attempt)
cd tests/fixtures/web_server
python3 server.py --port 8000 --enable-failure-simulation

# Verify MCP server running
```

### Setup

```bash
# Export environment
export PLAYWRIGHT_TEST_WEB_URL="http://localhost:8000"
export WORKFLOW_FRAMEWORK_ENV="test"

# Prepare test data
mkdir -p data/executions data/logs data/artifacts
rm -f data/executions/*.json data/logs/*.log
```

### Run (Part 1: Test Transient Error Retry)

```bash
# Workflow with a step that fails once, then succeeds
python3 -m src.cli.workflow_runner \
  --workflow form_with_transient_error \
  --input '{
    "form_url": "http://localhost:8000/form-that-fails-once",
    "expected_retry_count": 1,
    "error_type": "timeout"
  }' \
  --output-format json > /tmp/scenario_e_transient.json

# Expected: status: completed (retried and succeeded)
EXECUTION_ID_1=$(jq -r .execution_id /tmp/scenario_e_transient.json)
echo "Transient error execution: $EXECUTION_ID_1"
```

### Run (Part 2: Test Permanent Error Escalation)

```bash
# Workflow with permanent error that requires agent decision
python3 -m src.cli.workflow_runner \
  --workflow form_with_permanent_error \
  --input '{
    "form_url": "http://localhost:8000/form-validation-fails",
    "error_type": "validation_error",
    "expected_checkpoint": true
  }' \
  --output-format json \
  --background > /tmp/scenario_e_permanent.json &

sleep 10  # Wait for checkpoint

EXECUTION_ID_2=$(jq -r .execution_id /tmp/scenario_e_permanent.json)

# Verify checkpoint created for permanent error
python3 -c "
import json, subprocess
result = subprocess.run([
    'python3', '-m', 'src.mcp_server.client',
    'get_execution_status', '--execution-id', '$EXECUTION_ID_2'
], capture_output=True, text=True)
status = json.loads(result.stdout)
print(f\"Status: {status['status']}\")
print(f\"Checkpoint present: {status.get('pending_checkpoint') is not None}\")
# Expected: status: paused, pending_checkpoint: {...}
"

# Agent skips this workflow
python3 -m src.mcp_server.client \
  resolve_checkpoint \
  --execution-id "$EXECUTION_ID_2" \
  --checkpoint-id "$(python3 -c "import json; f=open('data/executions/$EXECUTION_ID_2.json'); d=json.load(f); print([c['id'] for c in d.get('checkpoints',[]) if c.get('status')=='pending'][0])")" \
  --decision '{"value": "skip", "reason": "Permanent validation error, cannot auto-fix"}'

sleep 5  # Wait for completion

# Verify execution completed (skipped)
python3 -c "
import json, subprocess
result = subprocess.run([
    'python3', '-m', 'src.mcp_server.client',
    'get_execution_status', '--execution-id', '$EXECUTION_ID_2'
], capture_output=True, text=True)
status = json.loads(result.stdout)
print(f\"Final Status: {status['status']}\")
# Expected: status: completed (or failed, depending on skip behavior)
"
```

### Verify

```bash
# 1. Check transient error execution has retry events
grep "retry\|attempt" data/logs/$EXECUTION_ID_1.log | jq .
# Expected: At least 2 events (attempt 1, retry, attempt 2)

# 2. Verify retry counts match config
python3 -c "
import json
with open('data/executions/$EXECUTION_ID_1.json') as f:
    data = json.load(f)
    for step in data['steps']:
        if step.get('retried'):
            print(f\"Step {step['name']}: retried {step['retry_count']} times\")
            print(f\"  Attempts: {len(step['attempts'])}\")
            # Expected: retry_count matches number of attempts - 1
"

# 3. Verify permanent error step has error classification
grep "error_type\|classification" data/logs/$EXECUTION_ID_2.log | jq '.context | {error_type, classification}'
# Expected: classification: "permanent" or "escalate_to_checkpoint"

# 4. Check checkpoint created for permanent error
python3 -c "
import json
with open('data/executions/$EXECUTION_ID_2.json') as f:
    data = json.load(f)
    checkpoints = [c for c in data.get('checkpoints', []) if c.get('reason_code') == 'STEP_ERROR']
    if checkpoints:
        print(f\"Found {len(checkpoints)} checkpoint(s) for step error\")
        print(f\"Error: {checkpoints[0].get('context', {}).get('error')}\")
"

# 5. Compare retry behavior across both executions
echo "=== Scenario E Summary ==="
echo "Transient Error (should retry and complete):"
jq '.status' /tmp/scenario_e_transient.json
echo ""
echo "Permanent Error (should pause at checkpoint):"
python3 -c "
import json, subprocess
result = subprocess.run([
    'python3', '-m', 'src.mcp_server.client',
    'get_execution_status', '--execution-id', '$EXECUTION_ID_2'
], capture_output=True, text=True)
print(json.loads(result.stdout)['status'])
"
```

---

## Validation Checklist

After running all 5 scenarios, verify:

- [ ] **Scenario A**: Simple workflow completes in < 30s
- [ ] **Scenario B**: Checkpoint pause/resume within 5 min preserves session (no re-login)
- [ ] **Scenario C**: Hard timeout at 5 min marks execution as failed; manual resume recovers session with re-auth
- [ ] **Scenario D**: 10 concurrent workflows respect max 5 concurrency limit; all complete successfully
- [ ] **Scenario E**: Transient errors auto-retry; permanent errors escalate to checkpoint

**Quality Gates**:
- [ ] No corrupted execution state files (all valid JSON)
- [ ] All logs properly formatted (valid JSON lines)
- [ ] No dangling browser processes (cleanup verified)
- [ ] No file descriptor leaks
- [ ] All timestamps in ISO8601 format
- [ ] All UUIDs are valid v4 format

**Performance Baseline** (for future regression detection):
- [ ] Simple workflow: 10-20 seconds (including browser startup)
- [ ] Checkpoint resolution: < 2 seconds
- [ ] Concurrent execution throughput: 5 workflows / minute (with concurrency limit)
- [ ] Session recovery: < 10 seconds (replay + re-auth)

---

## Troubleshooting

### Common Issues

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| Test server not responding | `curl http://localhost:8000/health` | Start test server in prerequisites |
| MCP server not responsive | Check stderr for errors | Restart with verbose logging: `MCP_LOG_LEVEL=debug python3 run_stdio_server.py` |
| Browser not starting | Check playwright install | Run `playwright install chromium` |
| Execution state corrupted | Parse error on `*.json` file | Check file permissions and atomic write logs |
| Checkpoint timeout not firing | Check `MCP_CHECKPOINT_TIMEOUT_HARD_SECONDS` env var | Ensure it's set to 300+ seconds |
| Session recovery fails | Check credential manager keys | Verify `data/credentials/` directory and master password |

### Debug Mode

```bash
# Run any scenario with verbose logging
export MCP_LOG_LEVEL="debug"
export PLAYWRIGHT_DEBUG="true"

# Inspect execution state at any point
python3 -c "
import json
from pathlib import Path

for exec_file in sorted(Path('data/executions').glob('*.json')):
    print(f'\n=== {exec_file.name} ===')
    with open(exec_file) as f:
        data = json.load(f)
        print(f\"Status: {data['status']}\")
        print(f\"Steps: {len(data.get('steps', []))}\")
        print(f\"Checkpoints: {len(data.get('checkpoints', []))}\")
        if data.get('error'):
            print(f\"Error: {data['error']}\")
"
```

---

## References

- **MCP Tools Schema**: See [`contracts/mcp_tools.json`](./contracts/mcp_tools.json)
- **Python API Contract**: See [`contracts/workflow_api.md`](./contracts/workflow_api.md)
- **Data Model**: See [`data-model.md`](./data-model.md)
- **Implementation Plan**: See [`plan.md`](./plan.md)

---

**Quickstart validation guide complete. Ready for Phase 2 (tasks.md generation).**
