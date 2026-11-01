# Data Model: Playwright Workflow Orchestration Framework

**Feature**: Workflow Orchestration  
**Date**: 2026-11-01  
**Status**: Phase 1 Output - Design artifacts

---

## Entity Definitions

### 1. Workflow

**Purpose**: Defines a reusable automation logic that developers extend and execute.

| Field | Type | Description |
|-------|------|-------------|
| `workflow_type` | `string` | Unique identifier (e.g., "login_workflow", "form_filling") |
| `version` | `string` | Semantic version (e.g., "1.0.0") |
| `entry_point` | `string` | Python module path to entry class (e.g., "src.workflows.login.LoginWorkflow") |
| `description` | `string` | Human-readable description of what this workflow does |
| `created_at` | `ISO8601 timestamp` | When workflow was first registered |
| `updated_at` | `ISO8601 timestamp` | Last modification time |

**Relationships**:
- 1 Workflow → N Executions (one workflow type can be executed many times)

**Validation Rules**:
- `workflow_type` must be globally unique (prevents name collisions)
- `version` must follow semantic versioning (X.Y.Z)
- `entry_point` must resolve to a Python class inheriting from `BaseWorkflow`

---

### 2. Execution

**Purpose**: Represents a single run/instance of a workflow.

| Field | Type | Description |
|-------|------|-------------|
| `execution_id` | `UUID v4` | Unique identifier for this execution (primary key) |
| `workflow_type` | `string` | Reference to workflow being executed |
| `input_params` | `JSON object` | Workflow-specific input parameters (e.g., `{"username": "alice"}`) |
| `start_time` | `ISO8601 timestamp` | When execution began |
| `end_time` | `ISO8601 timestamp or null` | When execution completed (null if still running) |
| `status` | `enum` | Current state: `pending` \| `running` \| `paused` \| `completed` \| `failed` |
| `state` | `JSON object` | Complete execution context (see State Schema below) |
| `last_updated` | `ISO8601 timestamp` | Timestamp of last state modification |

**Relationships**:
- N Executions → 1 Workflow (many instances of same workflow type)
- 1 Execution → N Steps (ordered sequence)
- 1 Execution → N Checkpoints (pause points)
- 1 Execution → N ExecutionLogs (audit trail)
- 1 Execution → N Resources (allocated resources)

**Validation Rules**:
- `execution_id` must be globally unique (UUID v4)
- `status` transitions must follow state machine (see below)
- `input_params` must match workflow schema (enforced at runtime)
- `end_time` must be null if `status` is `running` or `paused`

**State Machine Transitions**:

```
pending → running → paused ──→ running → completed
                ↓                ↓
                └─────────→ failed (unrecoverable)
```

---

### 3. Step

**Purpose**: Atomic action within a workflow execution (navigate, click, fill, etc.).

| Field | Type | Description |
|-------|------|-------------|
| `step_id` | `UUID v4` | Unique identifier for this step |
| `execution_id` | `UUID v4` | Reference to parent execution |
| `step_index` | `integer` | 0-based position in workflow (deterministic ordering) |
| `name` | `string` | Step description (e.g., "fill_login_form", "click_submit_button") |
| `status` | `enum` | Current state: `pending` \| `running` \| `completed` \| `error` \| `skipped` |
| `input_data` | `JSON object` | Input parameters for this step (e.g., `{"selector": "#username", "text": "alice"}`) |
| `output_data` | `JSON object or null` | Result from this step (e.g., page title, extracted data) |
| `error` | `JSON object or null` | Error details if `status == error` |
| `start_time` | `ISO8601 timestamp` | When step execution began |
| `end_time` | `ISO8601 timestamp or null` | When step completed |
| `duration_ms` | `integer` | Total execution time in milliseconds (computed) |
| `retry_count` | `integer` | Number of times this step was retried (default 0) |

**Relationships**:
- N Steps → 1 Execution (ordered sequence per execution)

**Validation Rules**:
- `step_index` must be unique within execution (no duplicates)
- `status` must match execution status (e.g., step can't be `completed` if execution is `paused`)
- `end_time` must be null if `status` is `pending` or `running`
- `output_data` is populated only if `status == completed`
- `error` is populated only if `status == error`

**Step Result Example**:

```json
{
  "step_id": "550e8400-e29b-41d4-a716-446655440000",
  "execution_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "step_index": 2,
  "name": "fill_login_form",
  "status": "completed",
  "input_data": {
    "username_selector": "#username",
    "username_value": "alice",
    "password_selector": "#password",
    "password_value": "secret123"
  },
  "output_data": {
    "form_filled": true,
    "ready_to_submit": true
  },
  "error": null,
  "start_time": "2026-11-01T12:00:00Z",
  "end_time": "2026-11-01T12:00:02Z",
  "duration_ms": 2000,
  "retry_count": 0
}
```

---

### 4. Checkpoint

**Purpose**: Pause point in workflow requesting human/agent decision.

| Field | Type | Description |
|-------|------|-------------|
| `checkpoint_id` | `UUID v4` | Unique identifier |
| `execution_id` | `UUID v4` | Reference to parent execution |
| `checkpoint_index` | `integer` | Position in execution's checkpoint sequence (0-based) |
| `step_number` | `integer` | Which workflow step triggered this checkpoint |
| `question` | `JSON object` | Decision question/prompt for agent (see format below) |
| `response` | `JSON object or null` | Agent's decision/response (null until resolved) |
| `agent_id` | `string or null` | Which agent handled this checkpoint (for audit) |
| `created_at` | `ISO8601 timestamp` | When checkpoint was created |
| `resolved_at` | `ISO8601 timestamp or null` | When response was received (null if pending) |
| `timeout_strategy` | `enum` | How to handle timeout: `keep_alive` \| `replay` |
| `browser_context_data` | `JSON object` | Playwright context state (cookies, storage) if `timeout_strategy == keep_alive` |
| `session_cookies` | `JSON object` | Serialized session cookies for re-auth |
| `encrypted_credentials` | `JSON object or null` | Encrypted login credentials for re-auth on hard timeout |
| `last_completed_step_index` | `integer` | Index of last successfully completed step (for replay) |
| `workflow_state_snapshot` | `JSON object` | Complete execution state at checkpoint (for context) |
| `status` | `enum` | `pending` \| `resolved` \| `timeout` \| `error` |

**Relationships**:
- N Checkpoints → 1 Execution (multiple decision points per execution)

**Validation Rules**:
- `checkpoint_index` must be unique within execution
- `response` is null until checkpoint is resolved
- `resolved_at` must be null if `status != resolved`
- `browser_context_data` is non-null only if `timeout_strategy == keep_alive`
- `encrypted_credentials` is encrypted via AES-256-GCM

**Question Format**:

```json
{
  "type": "confirmation",
  "text": "Ready to submit the login form?",
  "context": {
    "current_page": "https://example.com/login",
    "form_data": {"username": "alice", "password": "***"},
    "screenshot_url": "/data/artifacts/checkpoint_123.png"
  },
  "options": [
    {"value": "proceed", "label": "Yes, submit form"},
    {"value": "cancel", "label": "Cancel and stop"},
    {"value": "revise", "label": "Go back and revise"}
  ],
  "timeout_seconds": 300,
  "allow_custom_response": false
}
```

**Response Format**:

```json
{
  "decision": "proceed",
  "rationale": "Form data looks correct, proceeding with submission",
  "timestamp": "2026-11-01T12:05:30Z",
  "agent": "claude-3-opus"
}
```

---

### 5. Resource

**Purpose**: Tracks allocated resources per execution (browser pages, API connections, file handles).

| Field | Type | Description |
|-------|------|-------------|
| `resource_id` | `UUID v4` | Unique identifier |
| `execution_id` | `UUID v4` | Reference to parent execution |
| `resource_type` | `enum` | Type: `browser_page` \| `browser_context` \| `api_connection` \| `file_lock` |
| `resource_name` | `string` | Name/descriptor (e.g., "page_1", "db_pool", "upload_file.txt") |
| `allocated_at` | `ISO8601 timestamp` | When resource was allocated |
| `released_at` | `ISO8601 timestamp or null` | When resource was freed (null if still active) |
| `quota_limit` | `integer` | Maximum allowed (e.g., max 50 browser pages per execution) |
| `current_usage` | `integer` | Current count/usage |
| `metadata` | `JSON object` | Resource-specific metadata |

**Relationships**:
- N Resources → 1 Execution (per-execution resource isolation)

**Validation Rules**:
- `current_usage` must not exceed `quota_limit`
- `released_at` must be null if resource is still active
- Resource must be released before execution completes

**Resource Quota Defaults**:

```json
{
  "browser_page": 10,
  "browser_context": 1,
  "api_connection": 5,
  "file_lock": 20,
  "memory_mb": 512,
  "agent_timeouts": 5
}
```

---

### 6. ExecutionLog

**Purpose**: Structured audit trail of all execution events.

| Field | Type | Description |
|-------|------|-------------|
| `log_id` | `UUID v4` | Unique identifier |
| `execution_id` | `UUID v4` | Reference to execution |
| `step_id` | `UUID v4 or null` | Reference to step (if event is step-related) |
| `checkpoint_id` | `UUID v4 or null` | Reference to checkpoint (if event is checkpoint-related) |
| `timestamp` | `ISO8601 timestamp` | When event occurred |
| `event_type` | `enum` | `execution_started` \| `step_started` \| `step_completed` \| `step_error` \| `checkpoint_created` \| `checkpoint_resolved` \| `checkpoint_timeout` \| `execution_completed` \| `execution_failed` \| `session_recovered` |
| `level` | `enum` | `info` \| `warning` \| `error` \| `debug` |
| `message` | `string` | Human-readable log message |
| `context` | `JSON object` | Additional structured data (see format below) |

**Relationships**:
- N ExecutionLogs → 1 Execution (complete audit trail)

**Log Format**:

```json
{
  "log_id": "550e8400-e29b-41d4-a716-446655440001",
  "execution_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "step_id": "550e8400-e29b-41d4-a716-446655440000",
  "checkpoint_id": null,
  "timestamp": "2026-11-01T12:00:02.500Z",
  "event_type": "step_completed",
  "level": "info",
  "message": "Step 'fill_login_form' completed successfully",
  "context": {
    "step_name": "fill_login_form",
    "step_index": 2,
    "duration_ms": 2000,
    "input": {"username": "alice", "password": "***"},
    "output": {"form_filled": true},
    "retries": 0
  }
}
```

---

## Execution State Schema (Stored in Execution.state)

**Purpose**: Complete snapshot of execution context for resumption and audit.

```json
{
  "__version__": 1,
  "execution_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "workflow_type": "login_workflow",
  "workflow_version": "1.0.0",
  "input_params": {
    "username": "alice",
    "password_encrypted": "eyJhbGci...",
    "target_url": "https://example.com"
  },
  "status": "paused",
  "start_time": "2026-11-01T12:00:00Z",
  "end_time": null,
  "completed_steps": [0, 1, 2],
  "current_step_index": 3,
  "step_results": [
    {
      "step_index": 0,
      "name": "navigate",
      "status": "completed",
      "output": {"page_title": "Login - Example"}
    },
    {
      "step_index": 1,
      "name": "fill_username",
      "status": "completed",
      "output": {"filled": true}
    },
    {
      "step_index": 2,
      "name": "fill_password",
      "status": "completed",
      "output": {"filled": true}
    }
  ],
  "checkpoint": {
    "checkpoint_id": "7ca8b911-9dad-11d1-80b4-00c04fd430c9",
    "checkpoint_index": 0,
    "step_number": 3,
    "created_at": "2026-11-01T12:00:10Z",
    "resolved_at": null,
    "timeout_strategy": "keep_alive",
    "question": {
      "type": "confirmation",
      "text": "Ready to submit login form?",
      "options": ["proceed", "cancel"]
    },
    "response": null,
    "browser_context_preserved": true
  },
  "browser_context": {
    "cookies": [
      {"name": "session_id", "value": "abc123...", "domain": "example.com"}
    ],
    "local_storage": {
      "user_preferences": "{\"theme\": \"dark\"}"
    },
    "session_storage": {}
  },
  "session_cookies": {
    "session_id": "abc123...",
    "csrf_token": "def456..."
  },
  "encrypted_credentials": {
    "salt": "0123456789abcdef",
    "nonce": "fedcba9876543210",
    "ciphertext": "encrypted_payload...",
    "algorithm": "aes-256-gcm"
  },
  "resources_allocated": {
    "browser_pages": 1,
    "browser_context": 1,
    "api_connections": 0
  },
  "errors": [],
  "agent_decisions": [
    {
      "checkpoint_id": "...",
      "decision": "proceed",
      "agent": "claude-3-opus",
      "timestamp": "2026-11-01T12:05:30Z"
    }
  ],
  "last_url": "https://example.com/login",
  "last_activity_time": "2026-11-01T12:00:10Z"
}
```

---

## Data Relationships (Entity Diagram)

```
┌─────────────┐
│  Workflow   │
│  workflow_  │
│   type  (PK)│
└────────┬────┘
         │
         │ 1:N
         ▼
┌──────────────────┐      ┌──────────┐      ┌────────┐
│   Execution      │◄─────┤   Step   │      │ Step   │
│ execution_id (PK)│ 1:N  │(FK: exec)│ 1:N  └────────┘
└──────┬───────────┘      └──────────┘
       │
       ├─ 1:N ─► Checkpoint (FK: exec_id)
       ├─ 1:N ─► ExecutionLog (FK: exec_id)
       └─ 1:N ─► Resource (FK: exec_id)
       
Constraints:
- execution_id: UNIQUE (global)
- step_index: UNIQUE per execution
- checkpoint_index: UNIQUE per execution
```

---

## Validation Rules (Cross-Entity)

| Rule | Description | Enforcement |
|------|-------------|------------|
| Execution State Consistency | If `status == paused`, then `checkpoint` must be non-null and unresolved | Runtime check at pause/resume |
| Step Ordering | Steps within execution must have sequential `step_index` (0, 1, 2, ...) | DB constraint or runtime validation |
| Checkpoint Timeout | If `resolved_at - created_at > 300s` and response is null, mark as `timeout` | Async timeout handler |
| Resource Quota | Current resource usage must not exceed per-execution quota | Enforcement at resource allocation |
| Credential Encryption | All credentials stored in `encrypted_credentials` must use same algorithm | Validation in SecureCredentialStore |

---

## State Transitions & Lifecycle

### Execution Lifecycle

```
[pending] ──start──► [running] ◄──resume── [paused]
   │                    │                      ▲
   │                    ├──error──► [failed]   │
   │                    │                      │
   │                    └──checkpoint──────────┘
   │
   └──timeout──► [failed]
```

### Step Lifecycle (per execution)

```
[pending] ──start──► [running] ──success──► [completed]
   │                    │
   │                    └──error──► [error] ──retry──┐
   │                                                  │
   │ (if skipped during replay)                      │
   └──────────────────────► [skipped]               │
                                                    └──► [running] ──► [completed]
```

### Checkpoint Lifecycle

```
[pending] ──wait──► [pending] ──resolve──► [resolved]
   │                    │
   │                    └──timeout──► [timeout] ──manual_resolve──► [resolved]
   │
   └──workflow_error──► [error]
```

---

## Future Extensibility

### Schema Versioning

Current version: `1`

When Execution.state or other entities need schema changes:

1. Increment `__version__` in state JSON
2. Add migration logic in framework: `def migrate_v1_to_v2(state)`
3. Auto-migrate on load: if loaded state has old version, run migration before processing

### Optional Fields for Future

- `parent_execution_id` (for nested workflows)
- `cost_estimate`, `cost_actual` (for cloud resource tracking)
- `performance_metrics` (detailed timing per component)
- `compliance_metadata` (for audit/regulatory requirements)

---

**Data model complete and ready for implementation.**
