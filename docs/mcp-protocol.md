# MCP Protocol & Server Integration Guide

This document explains how to use the Playwright Workflow Automation framework through the Model Context Protocol (MCP) server interface.

## Table of Contents

- [Overview](#overview)
- [MCP Server Setup](#mcp-server-setup)
- [Tool Contracts](#tool-contracts)
  - [start_workflow](#start_workflow)
  - [resolve_checkpoint](#resolve_checkpoint)
  - [get_execution_status](#get_execution_status)
  - [get_execution_logs](#get_execution_logs)
- [Notification Protocol](#notification-protocol)
- [Resources](#resources)
- [Error Handling](#error-handling)
- [Example Workflows](#example-workflows)

## Overview

The Playwright Workflow Automation framework provides an MCP (Model Context Protocol) server that allows external clients (Claude, other AI agents, automation tools) to:

1. **Start workflows** - Trigger workflow execution with parameters
2. **Monitor execution** - Poll status and retrieve logs
3. **Resolve checkpoints** - Provide decisions at human/AI-in-loop checkpoints
4. **Access resources** - Query workflow metadata and execution state

The MCP server uses standard JSON-RPC 2.0 over stdio transport, making it compatible with any MCP client.

## MCP Server Setup

### Running the Server

Start the MCP server with:

```bash
python3 -m src.cli.mcp_server_runner
```

The server will listen on stdin/stdout and respond to MCP protocol messages.

### Configuration

The server automatically discovers and registers all workflows in `src/workflows/`. Custom workflows can be registered:

```python
from src.mcp_server.tools import register_workflow
from src.workflows.my_workflow import MyWorkflow

register_workflow("my_workflow", MyWorkflow)
```

## Tool Contracts

### start_workflow

Start a new workflow execution with input parameters.

**Input Schema:**
```json
{
  "workflow_type": {
    "type": "string",
    "description": "Type of workflow to execute (e.g., 'login_workflow', 'form_filling')"
  },
  "input_params": {
    "type": "object",
    "description": "Input parameters specific to the workflow",
    "additionalProperties": true
  },
  "max_retries": {
    "type": "integer",
    "description": "Maximum retry attempts on failure (default: 3)",
    "default": 3
  },
  "timeout_seconds": {
    "type": "integer",
    "description": "Execution timeout in seconds (default: 300)",
    "default": 300
  }
}
```

**Output Schema:**
```json
{
  "execution_id": {
    "type": "string",
    "description": "UUID of the created execution"
  },
  "workflow_type": {
    "type": "string"
  },
  "status": {
    "type": "string",
    "enum": ["pending", "running"]
  },
  "started_at": {
    "type": "string",
    "format": "date-time"
  }
}
```

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "start_workflow",
    "arguments": {
      "workflow_type": "login_workflow",
      "input_params": {
        "url": "https://example.com",
        "username": "test@example.com",
        "password": "secure_password"
      }
    }
  }
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "workflow_type": "login_workflow",
    "status": "running",
    "started_at": "2024-01-15T10:30:00Z"
  }
}
```

### resolve_checkpoint

Provide an agent/human decision to resume a workflow from a checkpoint.

**Input Schema:**
```json
{
  "execution_id": {
    "type": "string",
    "description": "UUID of the execution to resume"
  },
  "checkpoint_id": {
    "type": "string",
    "description": "UUID of the checkpoint to resolve"
  },
  "decision": {
    "type": "object",
    "description": "Agent's decision response (structure depends on checkpoint question)",
    "additionalProperties": true
  },
  "agent_id": {
    "type": "string",
    "description": "Identifier of agent making the decision (for audit)",
    "default": "unknown"
  }
}
```

**Output Schema:**
```json
{
  "execution_id": {
    "type": "string"
  },
  "checkpoint_id": {
    "type": "string"
  },
  "status": {
    "type": "string",
    "enum": ["pending", "running", "paused", "completed", "failed"]
  },
  "resolved_at": {
    "type": "string",
    "format": "date-time"
  }
}
```

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "resolve_checkpoint",
    "arguments": {
      "execution_id": "550e8400-e29b-41d4-a716-446655440000",
      "checkpoint_id": "660f9511-f40c-52e5-b827-557766551111",
      "decision": {
        "action": "approve",
        "reason": "Form data looks correct"
      },
      "agent_id": "claude-3-opus"
    }
  }
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "checkpoint_id": "660f9511-f40c-52e5-b827-557766551111",
    "status": "running",
    "resolved_at": "2024-01-15T10:32:00Z"
  }
}
```

### get_execution_status

Get current status and progress of a workflow execution.

**Input Schema:**
```json
{
  "execution_id": {
    "type": "string",
    "description": "UUID of the execution to query"
  }
}
```

**Output Schema:**
```json
{
  "execution_id": {
    "type": "string"
  },
  "workflow_type": {
    "type": "string"
  },
  "status": {
    "type": "string",
    "enum": ["pending", "running", "paused", "completed", "failed"]
  },
  "started_at": {
    "type": "string",
    "format": "date-time"
  },
  "ended_at": {
    "type": ["string", "null"],
    "format": "date-time"
  },
  "completed_steps": {
    "type": "integer"
  },
  "total_steps": {
    "type": "integer"
  },
  "current_step_name": {
    "type": "string"
  },
  "pending_checkpoint": {
    "type": ["object", "null"],
    "properties": {
      "checkpoint_id": {"type": "string"},
      "question": {"type": "string"},
      "options": {"type": "array"}
    }
  },
  "error": {
    "type": ["string", "null"]
  }
}
```

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "get_execution_status",
    "arguments": {
      "execution_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "workflow_type": "login_workflow",
    "status": "paused",
    "started_at": "2024-01-15T10:30:00Z",
    "ended_at": null,
    "completed_steps": 3,
    "total_steps": 5,
    "current_step_name": "verify_captcha",
    "pending_checkpoint": {
      "checkpoint_id": "660f9511-f40c-52e5-b827-557766551111",
      "question": "Please verify the CAPTCHA",
      "options": ["verified", "failed", "retry"]
    },
    "error": null
  }
}
```

### get_execution_logs

Retrieve structured logs from a workflow execution with optional filtering.

**Input Schema:**
```json
{
  "execution_id": {
    "type": "string",
    "description": "UUID of the execution"
  },
  "event_type": {
    "type": ["string", "null"],
    "description": "Filter by event type (e.g., 'step_started', 'checkpoint_requested')"
  },
  "level": {
    "type": ["string", "null"],
    "description": "Filter by log level (DEBUG, INFO, WARNING, ERROR)",
    "enum": ["DEBUG", "INFO", "WARNING", "ERROR", null]
  },
  "limit": {
    "type": "integer",
    "description": "Maximum logs to return (default: 100)",
    "default": 100
  },
  "offset": {
    "type": "integer",
    "description": "Pagination offset (default: 0)",
    "default": 0
  }
}
```

**Output Schema:**
```json
{
  "execution_id": {
    "type": "string"
  },
  "total_logs": {
    "type": "integer"
  },
  "returned_logs": {
    "type": "integer"
  },
  "logs": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "timestamp": {"type": "string", "format": "date-time"},
        "event_type": {"type": "string"},
        "level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]},
        "message": {"type": "string"},
        "step_name": {"type": ["string", "null"]},
        "data": {"type": ["object", "null"]}
      }
    }
  }
}
```

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "get_execution_logs",
    "arguments": {
      "execution_id": "550e8400-e29b-41d4-a716-446655440000",
      "event_type": "checkpoint_requested",
      "limit": 50,
      "offset": 0
    }
  }
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "total_logs": 15,
    "returned_logs": 1,
    "logs": [
      {
        "timestamp": "2024-01-15T10:31:30Z",
        "event_type": "checkpoint_requested",
        "level": "INFO",
        "message": "Workflow paused at checkpoint: verify_captcha",
        "step_name": "verify_captcha",
        "data": {
          "checkpoint_id": "660f9511-f40c-52e5-b827-557766551111",
          "question": "Please verify the CAPTCHA"
        }
      }
    ]
  }
}
```

## Notification Protocol

The MCP server sends notifications to inform clients of important events.

### Notification Types

#### checkpoint_requested

Sent when a workflow reaches a checkpoint requiring human/agent decision.

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/checkpoint_requested",
  "params": {
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "checkpoint_id": "660f9511-f40c-52e5-b827-557766551111",
    "step_name": "verify_captcha",
    "question": "Please verify the CAPTCHA",
    "options": ["verified", "failed", "retry"],
    "timestamp": "2024-01-15T10:31:30Z"
  }
}
```

#### execution_completed

Sent when a workflow completes successfully.

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/execution_completed",
  "params": {
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "workflow_type": "login_workflow",
    "result": {
      "success": true,
      "message": "Login successful",
      "user_id": "12345"
    },
    "completed_at": "2024-01-15T10:35:00Z"
  }
}
```

#### execution_failed

Sent when a workflow fails.

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/execution_failed",
  "params": {
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "workflow_type": "login_workflow",
    "error": "Invalid credentials",
    "step_name": "verify_credentials",
    "failed_at": "2024-01-15T10:31:00Z"
  }
}
```

## Resources

The MCP server provides resources for querying workflow metadata.

### workflow://{workflow_type}

Get metadata about a registered workflow type.

**URI:** `workflow://login_workflow`

**Response:**
```json
{
  "workflow_type": "login_workflow",
  "description": "Logs into a web application",
  "required_inputs": ["url", "username", "password"],
  "optional_inputs": ["2fa_method", "remember_me"],
  "steps": [
    "navigate_to_url",
    "fill_login_form",
    "submit_form",
    "verify_2fa",
    "check_dashboard"
  ],
  "checkpoints": [
    {
      "step": "verify_2fa",
      "question": "Enter the 2FA code",
      "options": ["manual_code", "auto_detect", "skip"]
    }
  ]
}
```

### execution/{execution_id}

Get complete state of a workflow execution.

**URI:** `execution/550e8400-e29b-41d4-a716-446655440000`

**Response:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow_type": "login_workflow",
  "status": "paused",
  "started_at": "2024-01-15T10:30:00Z",
  "ended_at": null,
  "completed_steps": 3,
  "total_steps": 5,
  "current_step_name": "verify_2fa",
  "execution_context": {
    "url": "https://example.com",
    "username": "test@example.com",
    "form_data": {...}
  },
  "pending_checkpoint": {
    "checkpoint_id": "660f9511-f40c-52e5-b827-557766551111",
    "question": "Enter the 2FA code",
    "step": "verify_2fa"
  },
  "error": null,
  "log_stats": {
    "total_logs": 25,
    "by_level": {
      "DEBUG": 5,
      "INFO": 18,
      "WARNING": 2,
      "ERROR": 0
    }
  }
}
```

## Error Handling

### Error Response Format

All MCP errors follow the JSON-RPC 2.0 standard:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "error_type": "validation_error",
      "details": "workflow_type is required"
    }
  }
}
```

### Common Error Codes

| Code | Message | Meaning |
|------|---------|---------|
| -32600 | Invalid Request | Malformed JSON-RPC request |
| -32602 | Invalid params | Parameters don't match schema |
| -32603 | Internal error | Server error executing tool |
| 400 | Bad Request | Invalid workflow type or missing required params |
| 404 | Not Found | Execution not found |
| 409 | Conflict | Execution already completed or failed |
| 500 | Internal Server Error | Unexpected server error |

### Error Handling Best Practices

1. **Always check for errors** - MCP responses may contain error objects
2. **Retry on transient errors** - Use exponential backoff for server errors
3. **Validate early** - Check tool schema before sending requests
4. **Log error details** - Preserve error data and context for debugging
5. **Handle timeouts** - Set appropriate timeouts for long-running workflows

Example error handling:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": 404,
    "message": "Execution not found",
    "data": {
      "execution_id": "invalid-uuid",
      "error_type": "execution_not_found"
    }
  }
}
```

## Example Workflows

### Complete Login Workflow

1. Start workflow:
```json
{
  "workflow_type": "login_workflow",
  "input_params": {
    "url": "https://example.com",
    "username": "user@example.com",
    "password": "secret123"
  }
}
```

2. Monitor status:
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

3. Receive checkpoint notification when 2FA is needed

4. Resolve checkpoint:
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "checkpoint_id": "660f9511-f40c-52e5-b827-557766551111",
  "decision": {
    "method": "email",
    "code": "123456"
  }
}
```

5. Monitor until completion

### Form Filling with Verification

1. Start form filling workflow
2. Poll status to get current step
3. When checkpoint occurs, retrieve logs to understand form state
4. Provide verification decision
5. Monitor for completion or error

---

**For more information:**
- See [Python API Documentation](./python-api.md) for programmatic access
- See [Checkpoint Protocol Guide](./checkpoint-protocol.md) for checkpoint design
- See [Custom Actions Guide](./custom-actions-guide.md) for extending workflows
