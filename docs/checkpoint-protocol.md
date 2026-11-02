# Checkpoint Protocol Guide

## Overview

The checkpoint protocol enables Playwright workflows to pause at decision points and request approval or guidance from AI agents or human operators. This document describes the protocol structure, timeout behavior, decision validation, and resumption strategies.

## Core Concepts

### Checkpoint
A checkpoint is a **named pause point** in a workflow where execution halts and waits for an external decision:
- Example: "Approve form submission" or "Confirm login credentials"
- Duration: Soft timeout at 2 minutes, hard timeout at 5 minutes
- State: Preserved on disk during pause; resumed from exact position on resume

### CheckpointQuestion
Structured question sent to an agent at a checkpoint.

**JSON Schema**:
```json
{
  "question_text": "Ready to submit the login form?",
  "question_type": "single_choice",
  "options": ["proceed", "cancel"],
  "metadata": {
    "current_page": "http://localhost:8000/login",
    "form_data": {
      "username": "testuser",
      "password": "***"
    }
  }
}
```

**Question Types**:
- `single_choice`: Agent selects one option (field: `choice`)
- `multi_choice`: Agent selects multiple options (field: `choices`)
- `yes_no`: Boolean confirmation (field: `confirmed`)
- `free_text`: Open-ended response (field: `text`)

### CheckpointDecision
Response from an agent to a checkpoint question.

**JSON Schema**:
```json
{
  "choice": "proceed",
  "confirmed": false,
  "metadata": {
    "reason": "Form data looks correct",
    "reviewed_by": "agent@example.com"
  }
}
```

**Validation Rules**:
- At least one field must be populated: `choice`, `choices`, `text`, or `confirmed`
- `choice` must be in the question's `options` list (if provided)
- `confirmed` must be boolean (true/false)
- `choices` must be a list of options from the question

### CheckpointRequest
Full request sent to MCP server when workflow pauses.

**JSON Schema**:
```json
{
  "checkpoint_id": "cp_550e8400-e29b-41d4-a716-446655440000",
  "execution_id": "exec_550e8400-e29b-41d4-a716-446655440001",
  "workflow": "LoginWorkflow",
  "step": "Request Approval",
  "question": {
    "question_text": "Ready to submit the login form?",
    "question_type": "single_choice",
    "options": ["proceed", "cancel"],
    "metadata": { "current_page": "..." }
  },
  "timeout_seconds": 300,
  "context": {
    "execution_state": "paused",
    "steps_completed": ["navigate", "fill_username", "fill_password"]
  }
}
```

### CheckpointResponse
Response sent back from agent via MCP when decision is made.

**JSON Schema**:
```json
{
  "checkpoint_id": "cp_550e8400-e29b-41d4-a716-446655440000",
  "execution_id": "exec_550e8400-e29b-41d4-a716-446655440001",
  "decision": {
    "choice": "proceed",
    "confirmed": false,
    "metadata": {
      "reason": "Form looks correct",
      "reviewed_by": "dev_agent"
    }
  },
  "timestamp": "2026-11-02T09:27:40.122+05:30"
}
```

## Timeout Behavior

Checkpoints enforce a two-tier timeout strategy:

### Soft Timeout (2 minutes)
- Workflow **continues** after soft timeout
- Agent has ~2 minutes to respond
- If no response: workflow applies default decision (typically "proceed")
- Logged as warning with `checkpoint_soft_timeout` event
- Allows unresponsive agents to not block production

**Scenario**: Agent is busy; checkpoint auto-proceeds after 2 minutes

### Hard Timeout (5 minutes)
- Workflow **fails** after hard timeout
- Total wall-clock time from checkpoint to failure is 5 minutes
- Execution status changes to `failed`
- Error code: `checkpoint_hard_timeout`
- Logged as error with full context

**Scenario**: Agent doesn't respond for 5 minutes; workflow fails; can be manually resumed

### Implementation

```python
# In workflow code
try:
    decision = await self.checkpoint(
        question=CheckpointQuestion(...),
        timeout_seconds=300,  # 5 minutes hard timeout
        allow_skip=False      # Fail on hard timeout
    )
except WorkflowCheckpointTimeout as e:
    # Hard timeout reached - execution paused
    # Can be resumed later with manual decision
    raise
```

## Decision Validation

### Validation Process

1. **Presence Check**: At least one decision field is populated
2. **Type Check**: Field types match schema (string, list, boolean)
3. **Option Check**: `choice` value is in question's `options` (if options provided)
4. **Metadata Check**: Metadata is dict (if provided)

### Example Validation

```python
# Valid decision
decision = CheckpointDecision(choice="proceed")
assert decision.is_valid() == True

# Invalid decision (no fields set)
decision = CheckpointDecision()
assert decision.is_valid() == False

# Invalid choice (not in options)
question = CheckpointQuestion(
    question_type="single_choice",
    options=["yes", "no"]
)
# This would fail validation:
decision = CheckpointDecision(choice="maybe")  # Not in options
```

### Custom Validation

Workflows can implement custom validation:

```python
class CustomCheckpoint(Checkpoint):
    def validate_decision(self, decision: CheckpointDecision) -> bool:
        if decision.choice:
            # Example: Only allow "proceed" if form is complete
            return self.form_complete
        return True

checkpoint = CustomCheckpoint(...)
decision = await checkpoint.request_decision()
```

## Resumption Strategy

### Quick Resume (≤5 minutes)

**Scenario**: Checkpoint triggered, agent responds within 5 minutes

**Flow**:
1. Workflow pauses at checkpoint → execution state saved to disk
2. Checkpoint request sent to MCP server
3. Agent receives notification → responds with decision
4. Workflow resumed from checkpoint with decision applied
5. Workflow continues from exact pause point

**Browser Session**: Preserved (same cookies, storage, navigation)  
**Execution State**: Preserved (all prior steps accessible)  
**Network**: Assumed still valid (no re-auth needed)

**Example**:
```
t=0s:   Checkpoint triggered, session saved
t=120s: Agent responds with decision
t=122s: Workflow resumes, browser still logged in
t=180s: Workflow completes
```

### Slow Resume (>5 minutes)

**Scenario**: Hard timeout reached; manual resume after long delay

**Flow**:
1. Workflow pauses at checkpoint
2. 5 minutes pass without response → workflow marked as failed
3. Administrator/agent manually responds to checkpoint
4. Workflow is explicitly resumed with manual decision
5. Browser session likely expired → session recovery triggered
6. If session expired: re-login or session refresh applied
7. Workflow continues from checkpoint

**Browser Session**: Likely expired (cookies stale or invalidated)  
**Execution State**: Preserved (but may need re-auth)  
**Network**: Session recovery protocol applied (see Session Recovery below)

**Example**:
```
t=0s:    Checkpoint triggered, session saved
t=300s:  Hard timeout reached, execution marked FAILED
t=+15m:  Manual resume with decision
t=+16m:  Session recovery check → re-auth needed
t=+20m:  After re-auth, workflow resumes
t=+30m:  Workflow completes
```

### Session Recovery

When resuming after timeout, the session recovery protocol is applied:

1. **Check Session Validity**
   - Attempt to navigate to checkpoint page
   - If 401/403 detected → session invalid

2. **Recover Session**
   - Apply stored session cookies/storage
   - Attempt to access protected resource
   - If still fails → trigger re-auth

3. **Re-authenticate**
   - Use stored credentials (from credential manager)
   - Re-submit login form
   - Re-acquire session cookies

4. **Resume Workflow**
   - Continue from checkpoint with fresh session
   - Proceed with original decision

See [Session Recovery Guide](./session-recovery.md) for details.

## API Usage Examples

### Creating a Checkpoint in a Workflow

```python
from src.framework.checkpoint import CheckpointQuestion, CheckpointDecision

class MyWorkflow(Workflow):
    @step(name="Verify Form")
    async def verify_and_submit(self):
        # Fill form
        await self.fill("#username", self.input.username)
        await self.fill("#password", self.input.password)
        
        # Create checkpoint question
        question = CheckpointQuestion(
            question_text="Ready to submit the login form?",
            question_type="single_choice",
            options=["proceed", "cancel"],
            metadata={
                "current_page": self._page.url,
                "form_fields": ["username", "password"]
            }
        )
        
        # Request decision (blocks until response or timeout)
        decision = await self.checkpoint(
            question=question,
            timeout_seconds=300,
            allow_skip=False
        )
        
        # Handle decision
        if decision.choice == "proceed":
            await self.click("button[type='submit']")
        elif decision.choice == "cancel":
            raise WorkflowCancelled("User cancelled submission")
```

### Implementing Custom Question Types

```python
# Multi-choice question
question = CheckpointQuestion(
    question_text="Which fields contain incorrect data?",
    question_type="multi_choice",
    options=["username", "password", "email"],
    metadata={"submitted_values": {...}}
)

decision = await self.checkpoint(question, timeout_seconds=120)
if decision.choices:
    for field in decision.choices:
        # Clear and re-fill incorrect fields
        await self.clear(f"#{field}")

# Free-text question
question = CheckpointQuestion(
    question_text="What should the form submit URL be?",
    question_type="free_text",
    metadata={"detected_urls": [...]}
)

decision = await self.checkpoint(question)
# Use decision.text as form action URL
```

### Handling Checkpoint Errors

```python
from src.framework.errors import WorkflowCheckpointTimeout, WorkflowError

try:
    decision = await self.checkpoint(question, timeout_seconds=300)
except WorkflowCheckpointTimeout as e:
    # Hard timeout reached
    logger.error(f"Checkpoint timeout: {e.checkpoint_id}")
    # Execution is paused; can be resumed later manually
    raise
except WorkflowError as e:
    # Other error (invalid decision, connection failure, etc)
    logger.error(f"Checkpoint error: {e}")
    raise
```

## MCP Integration

### Sending Checkpoint Request via MCP

```python
# Workflow sends request to MCP server
request = CheckpointRequest(
    checkpoint_id=str(uuid.uuid4()),
    execution_id=execution.execution_id,
    workflow_name=self.__class__.__name__,
    step_name=current_step,
    question=question,
    timeout_seconds=300,
    context=execution.get_state()
)

# Convert to MCP JSON-RPC format
mcp_params = request.to_mcp_request()

# Send via MCP client
response = await mcp_client.call_tool("request_checkpoint", {
    "checkpoint_request": mcp_params
})
```

### Receiving Checkpoint Response via MCP

```python
# Agent sends response back via MCP
response_data = {
    "checkpoint_id": "cp_...",
    "execution_id": "exec_...",
    "decision": {
        "choice": "proceed",
        "metadata": {"reason": "Form looks correct"}
    },
    "timestamp": "2026-11-02T09:27:40.122+05:30"
}

# Convert from MCP to CheckpointResponse
response = CheckpointResponse.from_mcp_response(response_data)

# Validate and apply decision
if response.decision.is_valid():
    # Resume workflow with decision
    return response.decision
```

## Best Practices

### 1. Clear Question Text
- Write questions that are **actionable** and **unambiguous**
- Include **context** (current page, form state, detected issues)
- ✅ Good: "Username field is empty. Proceed without username or cancel to retry?"
- ❌ Bad: "Continue?"

### 2. Metadata for Context
- Include **form data** (masked passwords)
- Include **page URL** and **step name**
- Include **validation errors** if form validation failed
- Help agent make informed decisions

### 3. Timeout Tuning
- Soft timeout: 2-5 minutes (typical)
- Hard timeout: 5-15 minutes (depending on expected agent response time)
- **Never** set hard timeout < soft timeout
- **Always** set `allow_skip=False` for critical decisions (default)

### 4. Error Handling
- **Always** catch `WorkflowCheckpointTimeout`
- **Never** silently ignore checkpoint errors
- Log checkpoint ID for debugging resumed executions
- Provide rollback strategy if decision fails

### 5. Session Management
- Assume session may expire after hard timeout
- Re-authenticate if needed after slow resume
- Store credentials securely (see [Credential Manager](./credential-manager.md))
- Test session recovery in your workflow scenarios

## Troubleshooting

### Checkpoint Not Triggered

**Symptom**: Workflow skips checkpoint, proceeds without agent decision

**Causes**:
- `allow_skip=True` in checkpoint call
- Execution not initialized (`workflow._execution is None`)
- Checkpoint timeout set to 0

**Solution**:
- Verify `allow_skip=False` (default)
- Call `workflow.set_execution(execution)` after creating execution
- Set reasonable timeout (>0, typically 300)

### Invalid Decision Error

**Symptom**: "Decision validation failed"

**Causes**:
- `choice` value not in question's `options`
- No decision fields populated
- Decision type mismatch (string vs array)

**Solution**:
- Verify `choice` is in `options` list
- Populate at least one field: `choice`, `choices`, `text`, or `confirmed`
- Match decision type to question type (single_choice → choice, multi_choice → choices, etc.)

### Session Expired After Resume

**Symptom**: Workflow resumes but 401/403 error on first action

**Causes**:
- Checkpoint took > 5 minutes to resolve
- Session cookies expired
- Server invalidated session

**Solution**:
- Enable session recovery protocol (automatic re-auth)
- Reduce soft timeout if agents respond quickly
- Store credentials for re-auth (see Credential Manager)
- Test resumption scenarios in your workflow

### Checkpoint Timeout vs Hard Timeout Confusion

**Question**: What's the difference between `timeout_seconds` and hard timeout?

**Answer**:
- `timeout_seconds`: Parameter in checkpoint call (typically 300)
- Hard timeout: System-enforced limit (always 300 = 5 minutes)
- `timeout_seconds` ≤ hard timeout (protocol enforces this)
- If you set `timeout_seconds=600`, it will be capped at 300

## See Also

- [Workflow Guide](./workflow-guide.md) - Creating workflows with checkpoints
- [Session Recovery](./session-recovery.md) - Handling session expiry during slow resume
- [Credential Manager](./credential-manager.md) - Storing credentials for re-auth
- [MCP Server Integration](./mcp-server-guide.md) - Integrating checkpoint protocol with MCP
- [Scenario B Quickstart](../specs/001-workflow-orchestration/quickstart.md#scenario-b) - Live example
