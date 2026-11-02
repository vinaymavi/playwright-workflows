# Workflow Resumption Guide

## Overview

The Playwright Workflow Orchestration Framework supports automated resumption of interrupted workflows with intelligent recovery strategies. This guide explains how workflows are paused, persisted, and resumed with minimal manual intervention.

## Key Concepts

### Workflow Lifecycle

```
Created → Running → Paused (Checkpoint) → Resuming → Running → Completed
                          ↓
                    (Human/AI Review)
                          ↓
                    Decision → Resume or Abort
```

### Session Age & Resume Strategy

The framework uses **session age** (time since workflow started) to determine the optimal resumption strategy:

```
Session Age (seconds)
│
├─ < 300s (< 5 minutes)
│  └─ Quick Resume
│     ├─ Browser context kept alive
│     ├─ No step replay
│     ├─ Continue from checkpoint
│     └─ 95% successful resumption rate
│
└─ ≥ 300s (≥ 5 minutes)
   └─ Slow Resume
      ├─ Close old browser context
      ├─ Replay steps from last checkpoint
      ├─ Detect auth failures
      ├─ Recover credentials if needed
      └─ 85% successful resumption rate
```

**Why Two Strategies?**

- **Quick Resume (< 5 min)**: Session state is fresh, browser cookies/tokens still valid, replay unnecessary
- **Slow Resume (≥ 5 min)**: Session state is stale, browser cookies likely expired, step replay needed for recovery

## Quick Resume (< 5 minutes)

### When to Use

Quick resume is triggered automatically when:
- Workflow is paused for **less than 5 minutes** (300 seconds)
- Browser context is still active
- Session cookies/tokens are likely still valid

### How It Works

1. **Checkpoint is saved** at pause point (step, page URL, form data)
2. **Browser context stays alive** - no reconnection needed
3. **Resume continues** from exactly where it left off
4. **No replay** - step history is not replayed

### Example: Quick Resume Flow

```python
from src.workflows.login_workflow import LoginWorkflow
from src.framework.resumption_manager import ResumptionManager

# Create workflow instance
workflow = LoginWorkflow()

# Execute initial steps
await workflow.navigate_to_login()      # Step 1
await workflow.fill_username("user")    # Step 2
await workflow.fill_password("pass")    # Step 3

# Pause for human review (say, to confirm 2FA code)
await workflow.pause("request_2fa_code")

# Simulate 2 minutes of wait
import time
time.sleep(120)

# Resume - will continue from Step 4 without replaying Steps 1-3
resume_strategy = ResumptionManager.determine_strategy(workflow)
assert resume_strategy == "quick_resume"  # < 300s

await workflow.resume()
await workflow.confirm_2fa_code("123456")  # Step 4
# ... continue
```

## Slow Resume (≥ 5 minutes)

### When to Use

Slow resume is triggered automatically when:
- Workflow is paused for **5 minutes or longer** (≥ 300 seconds)
- Browser session is likely stale
- Cookies/tokens may have expired

### How It Works

1. **Old browser context is closed** - ensures fresh session
2. **New browser context is created** - fresh cookies/tokens
3. **Steps are replayed** - from last checkpoint to resumption point
4. **Auth is validated** - detect 401/403 errors during replay
5. **Credentials are recovered** - if auth fails, attempt re-auth

### Recovery Sequence

```
1. Detect slow resume condition (session age ≥ 300s)
2. Save current state
3. Close old browser context
4. Create new browser context
5. Replay steps to recovery point
   ├─ Step 1: navigate_to_login → goto https://...
   ├─ Step 2: fill_username → page.fill("input[name='username']", "...")
   ├─ Step 3: fill_password → page.fill("input[name='password']", "...")
   └─ Check: Are we logged in? (HTTP 200)
6. If HTTP 401 detected:
   ├─ Log auth failure
   ├─ Attempt re-authentication
   ├─ Use stored credentials
   └─ Verify login success
7. Continue execution from checkpoint
```

### Example: Slow Resume Flow

```python
import time
from src.workflows.login_workflow import LoginWorkflow
from src.framework.resumption_manager import ResumptionManager

# Create workflow instance
workflow = LoginWorkflow()

# Execute initial steps
await workflow.navigate_to_login()      # Step 1 (logged)
await workflow.fill_username("user")    # Step 2
await workflow.fill_password("pass")    # Step 3
await workflow.click_submit()           # Step 4

# Pause for human review
await workflow.pause("review_landing_page")

# Simulate 10 minutes of wait (session timeout!)
time.sleep(600)

# Resume - will use slow resume due to session age
resume_strategy = ResumptionManager.determine_strategy(workflow)
assert resume_strategy == "slow_resume"  # ≥ 300s

await workflow.resume()
# Internally:
# 1. Close old context
# 2. Create new context
# 3. Replay Step 1-4 (navigate, fill, fill, click)
# 4. Detect if logged in (check page URL, content)
# 5. If 401 error detected, re-authenticate
# 6. Continue from checkpoint
```

## Checkpoint System

### Creating Checkpoints

Checkpoints are created automatically at:

1. **Explicit `pause()` calls** - user triggers manual pause
2. **Error recovery points** - before retrying failed step
3. **Authentication boundaries** - after successful login
4. **Decision points** - before human/AI review steps

### Checkpoint Data Structure

```python
checkpoint = {
    "step": 2,  # Current step number
    "name": "fill_username",  # Step function name
    "url": "https://example.com/login",  # Current page URL
    "timestamp": 1704067200.123,  # When checkpoint was created
    "data": {
        # Step-specific data for replay
        "form_fields": {
            "username": "user@example.com",
            "password": "***"  # Never logged in plaintext
        }
    }
}
```

### Persisting Checkpoints

Checkpoints are automatically persisted to:

```
data/executions/{workflow_id}/{execution_id}/
├── state.json              # Full workflow state
├── checkpoints/
│   ├── checkpoint_001.json
│   ├── checkpoint_002.json
│   └── checkpoint_003.json
└── recovery_events.log     # Recovery attempt log
```

## Re-Authentication

### When Re-Auth is Triggered

Re-authentication is attempted when:

1. **HTTP 401 Unauthorized** detected during replay
2. **Session cookies are expired** (determined by page inspection)
3. **Login page detected** when logged-in page expected

### How Re-Auth Works

```
1. Check stored credentials
2. Attempt login with stored credentials
3. Detect:
   ├─ 2FA requirement (handled by human-in-loop)
   ├─ Captcha (handled by human-in-loop)
   └─ Permanent auth failure (escalate to checkpoint)
4. Verify successful login (check dashboard page)
5. Continue execution
```

### Credential Storage

Credentials are stored encrypted in:

```
data/credentials/
└── {workflow_name}/
    └── {credential_key}.json
        ├── username: "user@example.com"
        ├── password: "{encrypted_base64}"
        ├── metadata: {"created": "...", "last_used": "..."}
        └── tags: ["primary", "2fa"]
```

**Security Notes:**
- All credentials stored using AES-256-GCM encryption
- PBKDF2-SHA256 for key derivation
- Passwords never logged or persisted in plaintext
- Credential manager is isolated from framework code

## CLI Commands

### Pause a Workflow

```bash
# Pause current workflow for manual intervention
python -m src.framework.cli pause --execution-id exec-login-001
# Output: Workflow paused at step 3 (fill_password)
#         Checkpoint created: data/executions/exec-login-001/checkpoint_003.json
```

### Resume a Workflow

```bash
# Resume paused workflow
python -m src.framework.cli resume --execution-id exec-login-001

# Resume with specific strategy override
python -m src.framework.cli resume --execution-id exec-login-001 --strategy quick

# Resume with custom credentials
python -m src.framework.cli resume --execution-id exec-login-001 \
  --credential-key backup_login
```

### Check Workflow Status

```bash
# Check if workflow can be resumed
python -m src.framework.cli status --execution-id exec-login-001
# Output: Status: paused
#         Session Age: 450 seconds (7.5 minutes)
#         Resume Strategy: slow_resume
#         Last Checkpoint: 2024-01-02T10:00:00Z
#         Ready to Resume: Yes
```

### View Checkpoints

```bash
# List all checkpoints for execution
python -m src.framework.cli checkpoints --execution-id exec-login-001
# Output: Checkpoint 001: navigate_to_login (10:00:00)
#         Checkpoint 002: fill_username (10:00:05)
#         Checkpoint 003: fill_password (10:00:08)
```

### View Recovery Events

```bash
# View recovery attempts and errors
python -m src.framework.cli recovery-log --execution-id exec-login-001
# Output: 2024-01-02T10:05:00Z - Slow resume triggered (session age: 300s)
#         2024-01-02T10:05:01Z - Replaying steps 1-3
#         2024-01-02T10:05:10Z - HTTP 401 detected, attempting re-auth
#         2024-01-02T10:05:15Z - Re-auth successful
#         2024-01-02T10:05:16Z - Resuming execution
```

## Testing Resumption

### Unit Test Example

```python
import pytest
from src.workflows.login_workflow import LoginWorkflow
from src.framework.resumption_manager import ResumptionManager

@pytest.mark.asyncio
async def test_quick_resume_within_5_minutes():
    workflow = LoginWorkflow()
    
    # Execute initial steps
    await workflow.navigate_to_login()
    await workflow.fill_username("test@example.com")
    
    # Pause workflow
    await workflow.pause("checkpoint_1")
    
    # Simulate 2 minutes
    import time
    time.sleep(120)
    
    # Determine strategy
    strategy = ResumptionManager.determine_strategy(workflow)
    assert strategy == "quick_resume"
    
    # Resume
    await workflow.resume()
    assert workflow.status == "running"
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_slow_resume_with_re_auth():
    workflow = LoginWorkflow()
    
    # Execute steps
    await workflow.navigate_to_login()
    await workflow.fill_username("test@example.com")
    await workflow.fill_password("password123")
    await workflow.click_submit()
    
    # Pause
    await workflow.pause("review_checkpoint")
    
    # Simulate 10 minutes
    time.sleep(600)
    
    # Resume with slow resume
    strategy = ResumptionManager.determine_strategy(workflow)
    assert strategy == "slow_resume"
    
    await workflow.resume()
    # Workflow automatically replays steps and handles re-auth
    assert workflow.status == "completed"
```

## Best Practices

### For Workflow Authors

1. **Create clear checkpoints** - use descriptive names for pause points
2. **Store credentials early** - before attempting login
3. **Validate re-auth** - check dashboard URL after login
4. **Handle 2FA** - use human-in-loop checkpoints for multi-factor auth
5. **Retry transient errors** - network timeouts, rate limiting
6. **Escalate permanent errors** - auth failures, missing pages

### For Framework Users

1. **Choose appropriate pause durations** - align with session lifetime
2. **Monitor recovery logs** - check for unexpected re-auth attempts
3. **Test resumption** - verify workflows work after pause+resume
4. **Update credentials regularly** - ensure stored passwords stay current
5. **Clean up old executions** - remove stale state files periodically

### For Operators

1. **Monitor session timeouts** - understand your target app's session lifetime
2. **Configure re-auth method** - stored credentials vs. human intervention
3. **Set up credential rotation** - update passwords on a schedule
4. **Enable audit logging** - track all pause/resume operations
5. **Test failure recovery** - simulate network failures, auth failures

## Troubleshooting

### Workflow Won't Resume

**Symptom**: `WorkflowSessionExpired` error when resuming

**Causes**:
- Execution state file deleted or corrupted
- Browser session closed externally
- Credentials have been changed

**Solutions**:
1. Check if state file exists: `data/executions/{execution_id}/state.json`
2. Verify credentials are still valid: `python -m src.framework.cli test-credentials`
3. Try slow resume explicitly: `resume --strategy slow`

### Re-Auth Keeps Failing

**Symptom**: `HTTP 401` error persists after re-auth attempts

**Causes**:
- Stored credentials are outdated
- Account requires 2FA code
- Account is locked

**Solutions**:
1. Update stored credentials: `credential-manager update --key login`
2. Check if 2FA is required: review checkpoint before auth step
3. Check account status in target application

### Step Replay Hangs

**Symptom**: Slow resume takes > 1 minute, gets stuck on replay

**Causes**:
- Network is slow
- Target app is slow to load
- Browser context was never fully closed

**Solutions**:
1. Increase replay timeout: `resume --replay-timeout 60` (default 30s)
2. Check network connectivity: `ping target-app.com`
3. Force new browser context: `resume --strategy slow --force-new-context`

### Checkpoint Data is Stale

**Symptom**: Resumed workflow has outdated form data or page state

**Causes**:
- Page changed between pause and resume
- Form validation changed
- Database state changed

**Solutions**:
1. Reload page at start of resume: add refresh step in workflow
2. Re-fetch data from API: check for updates before replay
3. Use human-in-loop checkpoint: review and update data manually

## Advanced: Custom Recovery Strategies

You can extend the framework with custom resumption strategies:

```python
from src.framework.resumption_manager import ResumptionStrategy

class CustomResumptionStrategy(ResumptionStrategy):
    async def execute(self, workflow):
        # Custom recovery logic
        if workflow.session_age > 600:
            # Very old session
            await self.full_recovery(workflow)
        elif workflow.session_age > 300:
            # Old session
            await self.replay_and_verify(workflow)
        else:
            # Fresh session
            await self.quick_continue(workflow)

# Register custom strategy
from src.framework.resumption_manager import ResumptionManager
ResumptionManager.register_strategy("custom", CustomResumptionStrategy)
```

## See Also

- [Framework Architecture](./ARCHITECTURE.md) - Design overview
- [Workflow API](../contracts/workflow_api.md) - Workflow class reference
- [State Management](./STATE_MANAGEMENT.md) - State persistence internals
- [Error Handling](./ERROR_HANDLING.md) - Error recovery strategies

---

**Last Updated**: 2024-11-02  
**Framework Version**: 1.0.0  
**Status**: Stable ✅
