# Error Handling Guide

## Overview

The Playwright Workflows framework provides comprehensive error handling mechanisms to distinguish between transient failures (recoverable) and permanent errors (requiring intervention). This guide explains the error hierarchy, handling strategies, and recovery patterns.

## Error Hierarchy

### Framework Error Classes

```
Exception
├── WorkflowException (Base for all workflow errors)
│   ├── StepExecutionError
│   │   ├── TransientError
│   │   │   ├── NetworkError
│   │   │   ├── TimeoutError
│   │   │   └── RateLimitError
│   │   │
│   │   └── PermanentError
│   │       ├── AuthenticationError
│   │       ├── ValidationError
│   │       ├── ElementNotFoundError
│   │       └── ApplicationError
│   │
│   ├── CheckpointError
│   ├── ResumptionError
│   └── StateError
│
└── PlaywrightError (From Playwright library)
```

## Error Classification

### Transient Errors (Automatically Retried)

**Characteristics**:
- Temporary network/system issues
- Retry-safe (idempotent operations)
- May succeed on retry without intervention

**Examples**:

| Error | Cause | Retry Strategy |
|-------|-------|---|
| `NetworkError` | Connection timeout, DNS failure | Exponential backoff (3x retry) |
| `TimeoutError` | Page load timeout, element wait timeout | Backoff 1s, 2s, 4s |
| `RateLimitError` | HTTP 429 response | Backoff + jitter |
| `BrowserCrashError` | Browser process crashed | Restart browser, retry from checkpoint |

**Retry Configuration**:

```python
# Global retry policy
workflow.config.max_retries = 3
workflow.config.retry_backoff_base = 1.0  # seconds
workflow.config.retry_backoff_multiplier = 2.0

# Or per-action
result = await self.invoke_action(
    'MyAction',
    max_retries=5,
    retry_backoff=2.0
)
```

**Retry Flow**:

```
Attempt 1: Immediate
    ↓ (fails)
Wait 1s
Attempt 2
    ↓ (fails)
Wait 2s
Attempt 3
    ↓ (fails)
Wait 4s
Attempt 4
    ↓ (fails)
Raise TransientError after max retries
    ↓
Checkpoint (pause for intervention)
```

### Permanent Errors (Require Intervention)

**Characteristics**:
- Logic/configuration issues
- Retry will not help without intervention
- Require human/AI decision or code fix

**Examples**:

| Error | Cause | Recovery |
|-------|-------|---|
| `AuthenticationError` | Invalid credentials, expired session | Update credentials, retry |
| `ValidationError` | Invalid input parameters | Fix input, rerun |
| `ElementNotFoundError` | Selector mismatch, page changed | Fix selector, rerun from checkpoint |
| `ApplicationError` | Server error (5xx), API failure | Check server, retry or abort |
| `AccessDenied` | Insufficient permissions | Escalate or choose alternate path |

**Permanent Error Flow**:

```
Permanent error detected
    ↓
Log error with full context
    ↓
Automatic checkpoint
    ↓
Emit notification (Slack, webhook, etc.)
    ↓
Wait for external intervention
    ↓
Resume with user-provided fix
    ↓
Continue from checkpoint
```

## Handling Patterns

### 1. Automatic Retry (Default)

Transient errors automatically retry with backoff:

```python
class MyWorkflow(Workflow):
    @step
    async def fetch_data(self):
        # Automatically retries on network timeout
        # Max 3 retries with exponential backoff
        result = await self.invoke_action('FetchDataAction', url='...')
        return result
```

**When to use**: Most network operations, page interactions

### 2. Explicit Error Handling

Catch and handle specific errors:

```python
from playwright_workflows.errors import (
    TransientError, 
    PermanentError,
    ElementNotFoundError
)

class MyWorkflow(Workflow):
    @step
    async def navigate_with_fallback(self):
        try:
            await self.page.goto('https://example.com/page1')
        except ElementNotFoundError as e:
            # Element not found - try alternate page
            await self.page.goto('https://example.com/page2')
        except TransientError as e:
            # Network issue - log and checkpoint
            self.logger.error(f"Network error: {e}")
            await self.checkpoint("network_unavailable")
```

### 3. Selective Retry

Retry only for specific error types:

```python
class MyWorkflow(Workflow):
    @step
    async def resilient_login(self):
        retries = 0
        max_retries = 3
        
        while retries < max_retries:
            try:
                return await self.invoke_action(
                    'LoginAction', 
                    username='user', 
                    password='pass'
                )
            except TransientError:
                # Network issue - retry
                retries += 1
                await asyncio.sleep(2 ** retries)
                continue
            except AuthenticationError as e:
                # Auth failed - stop retrying
                await self.checkpoint(
                    "authentication_failed",
                    data={'error': str(e)}
                )
                break
```

### 4. Optional Operations

Don't fail workflow if optional operation fails:

```python
class MyWorkflow(Workflow):
    @step
    async def process_with_screenshot(self):
        # Do main work
        result = await self.invoke_action('ProcessAction')
        
        # Take screenshot (optional, don't fail if it errors)
        try:
            await self.take_screenshot('process-complete')
        except Exception as e:
            self.logger.warning(f"Screenshot failed: {e}")
        
        return result
```

### 5. Validation Before Attempt

Validate inputs before action to avoid permanent errors:

```python
class FormFillingAction(Action):
    async def execute(self, context, form_data):
        # Validate early
        if not form_data or 'email' not in form_data:
            raise ValidationError("Missing required field: email")
        
        if not self._is_valid_email(form_data['email']):
            raise ValidationError("Invalid email format")
        
        # Now proceed with form filling
        return await self._fill_form(form_data)
    
    def _is_valid_email(self, email):
        return '@' in email and '.' in email
```

### 6. Graceful Degradation

Use fallbacks for non-critical operations:

```python
class MyWorkflow(Workflow):
    @step
    async def process_with_fallback(self):
        try:
            # Preferred method
            data = await self.invoke_action('FetchFromPrimaryAPI')
        except PermanentError:
            # Fallback
            self.logger.info("Primary API failed, using secondary")
            data = await self.invoke_action('FetchFromSecondaryAPI')
        
        return data
```

## Retry Strategy & Configuration

### Exponential Backoff

Default backoff formula: `delay = base * (multiplier ^ attempt)`

```python
# Default: base=1.0, multiplier=2.0
attempt 1: delay = 1.0 * (2.0 ^ 0) = 1.0s
attempt 2: delay = 1.0 * (2.0 ^ 1) = 2.0s
attempt 3: delay = 1.0 * (2.0 ^ 2) = 4.0s
```

### Jitter to Avoid Thundering Herd

```python
# Add jitter for distributed retries
delay = base * (multiplier ^ attempt) * (0.5 + random())
# Prevents all retries from happening simultaneously
```

### Timeout Handling

```python
class MyWorkflow(Workflow):
    config.step_timeout = 30.0  # seconds per step
    config.action_timeout = 10.0  # seconds per action
    config.page_load_timeout = 15.0  # seconds for page.goto()
    
    @step
    async def step_with_timeout(self):
        # This step must complete within 30 seconds
        # If it exceeds, raises TimeoutError
        result = await self.invoke_action('LongRunningAction')
        return result
```

## Error Examples & Recovery

### Example 1: Network Timeout

**Error**: 
```
TimeoutError: Timeout waiting for response
  at page.goto('https://api.example.com/data')
```

**Root Cause**: Network connectivity issue

**Recovery**:
```python
try:
    data = await self.page.goto('https://api.example.com/data')
except TimeoutError:
    # Automatically retried by framework
    # If still fails after max retries:
    await self.checkpoint("network_timeout")
    # External system will retry
```

### Example 2: Invalid Credentials

**Error**:
```
AuthenticationError: Invalid username or password
  at LoginAction.execute()
```

**Root Cause**: Incorrect credentials in workflow

**Recovery**:
```python
try:
    await self.invoke_action('LoginAction', 
                            username=username, 
                            password=password)
except AuthenticationError as e:
    await self.checkpoint("auth_failed", data={
        'error': str(e),
        'last_attempted_user': username
    })
    # External system updates credentials and resumes
```

### Example 3: Missing Page Element

**Error**:
```
ElementNotFoundError: Selector not found: #login-button
  at wait_for_selector('#login-button')
```

**Root Cause**: Page layout changed, selector outdated

**Recovery**:
```python
try:
    await self.page.wait_for_selector('#login-button')
except ElementNotFoundError:
    # Checkpoint with screenshot for debugging
    await self.take_screenshot('element-not-found')
    await self.checkpoint("element_not_found", data={
        'selector': '#login-button',
        'page_url': self.page.url
    })
    # External system reviews screenshot, updates selector
```

### Example 4: Rate Limiting

**Error**:
```
RateLimitError: HTTP 429 Too Many Requests
  Retry-After: 60
```

**Root Cause**: Too many requests in short time

**Recovery**:
```python
try:
    result = await self.invoke_action('FetchDataAction')
except RateLimitError as e:
    # Retry with longer backoff (framework handles this)
    # Respects Retry-After header
    # Max 3 retries with exponential backoff
    pass
```

### Example 5: Browser Crash

**Error**:
```
BrowserCrashError: Browser process crashed unexpectedly
```

**Root Cause**: Browser process exited

**Recovery**:
```python
# Framework automatically:
# 1. Detects browser crash
# 2. Restarts browser
# 3. Resumes from last checkpoint
# 4. Navigates back to last URL
# 5. Retries last action
```

## Observability & Debugging

### Error Logging

Errors logged with full context:

```json
{
  "timestamp": "2024-01-15T10:05:00Z",
  "execution_id": "exec-123",
  "level": "ERROR",
  "message": "Step failed after 3 retries",
  "step": "login",
  "error": {
    "type": "TransientError",
    "message": "Timeout waiting for page",
    "retry_count": 3,
    "last_delay": 4.0
  },
  "context": {
    "page_url": "https://example.com",
    "screenshot_on_error": "error-001.png"
  }
}
```

### Screenshot on Error

Automatically capture page state on error:

```python
config.screenshot_on_error = True  # Default: True
# Failed action automatically captures screenshot
# Saved as: data/artifacts/{execution_id}/error-{timestamp}.png
```

### Query Errors in Logs

```python
# Get logs with errors
logs = execution.get_logs(level='ERROR')
for log in logs:
    print(f"{log['step']}: {log['error']['message']}")

# Filter by error type
timeout_errors = execution.get_logs(
    level='ERROR',
    error_type='TimeoutError'
)
```

## Best Practices

1. **Validate Early**: Check inputs before attempting action
   ```python
   if not email or '@' not in email:
       raise ValidationError("Invalid email")
   ```

2. **Use Transient-Safe Operations**: Ensure actions are idempotent
   ```python
   # Good: idempotent
   await self.fill_form({'email': 'user@example.com'})
   
   # Bad: not idempotent
   await self.page.click('#increment-button')  # Increments value
   ```

3. **Set Appropriate Timeouts**: Match operation complexity
   ```python
   config.page_load_timeout = 15.0  # for fast pages
   config.action_timeout = 30.0  # for complex actions
   ```

4. **Checkpoint on Permanent Errors**: Allow intervention
   ```python
   except PermanentError as e:
       await self.checkpoint("intervention_needed", data={'error': str(e)})
   ```

5. **Log Context**: Include relevant state in logs
   ```python
   self.logger.error(
       "Login failed",
       extra={
           'username': username,
           'page_url': self.page.url,
           'page_title': self.page.title
       }
   )
   ```

6. **Test Error Paths**: Verify error handling works
   ```python
   # Test transient error retry
   workflow.simulate_network_error()
   result = workflow.run()  # Should succeed after retry
   ```

## Summary

Error handling in Playwright Workflows:
- **Automatic retry** for transient errors with exponential backoff
- **Checkpoint and wait** for permanent errors requiring intervention
- **Flexible patterns** for custom error handling
- **Full observability** with structured logging and screenshots
- **Graceful degradation** for non-critical operations

This design balances reliability (automatic recovery) with human oversight (checkpoints for intervention).
