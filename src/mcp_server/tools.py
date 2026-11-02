"""MCP Tools Implementation for Workflow Orchestration

Implements start_workflow, resolve_checkpoint, get_execution_status,
and get_execution_logs tools per contracts/mcp_tools.json.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..framework.checkpoint import CheckpointDecision
from .notifications import NotificationService


logger = logging.getLogger(__name__)


# Placeholder for workflow registry - will be populated when workflows are registered
_workflow_registry: dict[str, Any] = {}

# Placeholder for active executions - in-memory store of execution IDs
_active_executions: dict[str, Any] = {}

# Data directory for execution state storage (configurable via environment variable)
_DATA_DIR_ENV = os.getenv("WORKFLOW_DATA_DIR")
DATA_DIR = Path(_DATA_DIR_ENV) if _DATA_DIR_ENV else Path(__file__).parent.parent.parent / "data" / "executions"


def register_workflow(workflow_type: str, workflow_class: Any) -> None:
    """Register a workflow class by type name."""
    _workflow_registry[workflow_type] = workflow_class


def get_data_dir() -> Path:
    """Get data directory for execution storage, creating if needed."""
    # Re-check environment variable to allow test overrides
    env_dir = os.getenv("WORKFLOW_DATA_DIR")
    if env_dir:
        data_dir = Path(env_dir)
    else:
        data_dir = DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


async def start_workflow_impl(
    workflow_type: str,
    input_params: Optional[dict[str, Any]] = None,
    max_retries: int = 3,
    timeout_seconds: int = 3600) -> dict[str, Any]:
    """Start a new workflow execution.

    Args:
        workflow_type: Type/name of workflow (e.g., 'login_workflow')
        input_params: Workflow-specific input parameters
        max_retries: Max retries for transient errors (0-10, default 3)
        timeout_seconds: Hard timeout for workflow execution (min 10, default 3600)

    Returns:
        {
            "execution_id": "uuid",
            "workflow_type": "string",
            "status": "pending" | "running" | "paused" | "completed" | "failed",
            "created_at": "ISO8601 timestamp"
        }
    """
    try:
        # Validate workflow type is registered
        if workflow_type not in _workflow_registry:
            return {
                "error": f"Unknown workflow type: {workflow_type}",
                "available_workflows": list(_workflow_registry.keys()),
            }

        # Create execution ID and metadata
        execution_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Create execution state file
        execution_state = {
            "execution_id": execution_id,
            "workflow_type": workflow_type,
            "status": "pending",
            "input_params": input_params or {},
            "max_retries": max_retries,
            "timeout_seconds": timeout_seconds,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "steps": [],
            "checkpoints": [],
            "error": None,
        }

        # Save execution state to file
        data_dir = get_data_dir()
        execution_file = data_dir / f"{execution_id}.json"
        with open(execution_file, "w") as f:
            json.dump(execution_state, f, indent=2)

        # Track in memory
        _active_executions[execution_id] = execution_state

        # Get workflow class and start async execution
        workflow_class = _workflow_registry[workflow_type]

        # Start workflow in background task (don't await)
        asyncio.create_task(_execute_workflow(execution_id, workflow_class, input_params or {}))

        logger.info(
            "Started workflow execution",
            extra={
                "execution_id": execution_id,
                "workflow_type": workflow_type,
                "event": "workflow_started",
            })

        return {
            "execution_id": execution_id,
            "workflow_type": workflow_type,
            "status": "pending",
            "created_at": now,
        }

    except Exception as e:
        logger.error(f"Error starting workflow: {e}", exc_info=True)
        return {"error": str(e), "error_type": type(e).__name__}


async def resolve_checkpoint_impl(
    execution_id: str,
    checkpoint_id: str,
    decision: dict[str, Any],
    agent_id: str = "unknown") -> dict[str, Any]:
    """Resolve a checkpoint by providing agent decision.

    Args:
        execution_id: UUID of execution to resume
        checkpoint_id: UUID of checkpoint to resolve
        decision: Agent's decision response
        agent_id: Identifier of agent making decision (for audit)

    Returns:
        {
            "execution_id": "uuid",
            "checkpoint_id": "uuid",
            "status": "pending" | "running" | "paused" | "completed" | "failed",
            "resolved_at": "ISO8601 timestamp"
        }
    """
    try:
        # Load execution state
        data_dir = get_data_dir()
        execution_file = data_dir / f"{execution_id}.json"

        if not execution_file.exists():
            return {"error": f"Execution not found: {execution_id}"}

        with open(execution_file, "r") as f:
            execution_state = json.load(f)

        # Find checkpoint
        checkpoint = None
        for cp in execution_state.get("checkpoints", []):
            if cp["checkpoint_id"] == checkpoint_id:
                checkpoint = cp
                break

        if not checkpoint:
            return {"error": f"Checkpoint not found: {checkpoint_id}"}

        # Update checkpoint with decision
        checkpoint["response"] = decision
        checkpoint["agent_id"] = agent_id
        checkpoint["resolved_at"] = datetime.utcnow().isoformat()

        # Update execution state
        execution_state["status"] = "running"
        with open(execution_file, "w") as f:
            json.dump(execution_state, f, indent=2)

        # Track in memory
        _active_executions[execution_id] = execution_state

        # NOTIFY THE WAITING WORKFLOW EXECUTION
        # The workflow is paused in checkpoint() waiting for this decision
        # We need to find the Execution object and trigger its event
        try:
            # Try to import and notify the execution
            from ..framework.execution import Execution
            
            # Look for execution in active executions registry
            # Note: This relies on the Execution object being registered when workflow starts
            # For now, we try to get it from _active_executions if it was stored as an object
            
            # If _active_executions contains Execution objects (not just state dicts)
            if execution_id in _active_executions:
                exec_obj = _active_executions[execution_id]
                # Check if it's an Execution object (has set_checkpoint_decision method)
                if hasattr(exec_obj, 'set_checkpoint_decision'):
                    checkpoint_decision = CheckpointDecision(**decision)
                    exec_obj.set_checkpoint_decision(checkpoint_decision)
                    logger.info(
                        "Notified workflow execution to resume",
                        extra={
                            "execution_id": execution_id,
                            "checkpoint_id": checkpoint_id,
                        })
        except Exception as e:
            logger.warning(
                f"Could not notify execution to resume: {e}. "
                "Workflow will resume on next poll.",
                extra={"execution_id": execution_id})

        # Signal the workflow to resume (via event or queue)
        # This is handled by the workflow execution loop waiting on checkpoint resolution
        logger.info(
            "Resolved checkpoint",
            extra={
                "execution_id": execution_id,
                "checkpoint_id": checkpoint_id,
                "agent_id": agent_id,
                "event": "checkpoint_resolved",
            })

        return {
            "execution_id": execution_id,
            "checkpoint_id": checkpoint_id,
            "status": "running",
            "resolved_at": checkpoint["resolved_at"],
        }

    except Exception as e:
        logger.error(f"Error resolving checkpoint: {e}", exc_info=True)
        return {"error": str(e), "error_type": type(e).__name__}


async def get_execution_status_impl(execution_id: str) -> dict[str, Any]:
    """Get current status and progress of workflow execution.

    Args:
        execution_id: UUID of execution to query

    Returns:
        {
            "execution_id": "uuid",
            "workflow_type": "string",
            "status": "pending" | "running" | "paused" | "completed" | "failed",
            "started_at": "ISO8601 timestamp or null",
            "completed_at": "ISO8601 timestamp or null",
            "completed_steps": int,
            "total_steps": int,
            "current_step_name": "string or null",
            "pending_checkpoint": {"checkpoint_id": "...", "question": {...}} or null,
            "error": "error message or null"
        }
    """
    try:
        # Load execution state
        data_dir = get_data_dir()
        execution_file = data_dir / f"{execution_id}.json"

        if not execution_file.exists():
            return {"error": f"Execution not found: {execution_id}"}

        with open(execution_file, "r") as f:
            execution_state = json.load(f)

        # Find pending checkpoint if any
        pending_checkpoint = None
        for cp in execution_state.get("checkpoints", []):
            if cp.get("response") is None:  # No response yet = pending
                pending_checkpoint = {
                    "checkpoint_id": cp["checkpoint_id"],
                    "question": cp.get("question", {}),
                }
                break

        completed_steps = len([s for s in execution_state.get("steps", []) if s["status"] == "success"])
        total_steps = len(execution_state.get("steps", []))

        return {
            "execution_id": execution_id,
            "workflow_type": execution_state.get("workflow_type"),
            "status": execution_state.get("status"),
            "started_at": execution_state.get("started_at"),
            "completed_at": execution_state.get("completed_at"),
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "current_step_name": execution_state.get("current_step"),
            "pending_checkpoint": pending_checkpoint,
            "error": execution_state.get("error"),
        }

    except Exception as e:
        logger.error(f"Error getting execution status: {e}", exc_info=True)
        return {"error": str(e), "error_type": type(e).__name__}


async def get_execution_logs_impl(
    execution_id: str,
    event_type: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 100,
    offset: int = 0) -> dict[str, Any]:
    """Retrieve structured execution logs with optional filtering.

    Args:
        execution_id: UUID of execution
        event_type: Filter by event type (step_started, step_completed, etc.)
        level: Filter by log level (debug, info, warning, error)
        limit: Max logs to return (1-1000, default 100)
        offset: Pagination offset (default 0)

    Returns:
        {
            "execution_id": "uuid",
            "total_logs": int,
            "returned_logs": int,
            "logs": [
                {
                    "timestamp": "ISO8601",
                    "level": "info|warning|error|debug",
                    "event": "step_started|step_completed|checkpoint_reached|error",
                    "message": "string",
                    "context": {...}
                }
            ]
        }
    """
    try:
        # Load execution state
        data_dir = get_data_dir()
        execution_file = data_dir / f"{execution_id}.json"

        if not execution_file.exists():
            return {"error": f"Execution not found: {execution_id}"}

        with open(execution_file, "r") as f:
            execution_state = json.load(f)

        # Build log list from execution state
        logs = []

        # Add step logs
        for step in execution_state.get("steps", []):
            step_name = step.get("name", step.get("step_id", "unknown"))
            timestamp = step.get("timestamp") or step.get("started_at") or step.get("created_at")
            log_entry = {
                "timestamp": timestamp,
                "level": "info",
                "event": f"step_{step.get('status')}",
                "message": f"Step {step_name} {step.get('status')}",
                "context": {
                    "step_name": step_name,
                    "status": step.get("status"),
                    "duration_seconds": step.get("duration_seconds"),
                    "retry_count": step.get("retry_count", 0),
                },
            }
            if step.get("error"):
                log_entry["level"] = "error"
                log_entry["context"]["error"] = step["error"]

            logs.append(log_entry)

        # Add checkpoint logs
        for checkpoint in execution_state.get("checkpoints", []):
            checkpoint_id = checkpoint.get("checkpoint_id", "unknown")
            logs.append(
                {
                    "timestamp": checkpoint.get("created_at"),
                    "level": "info",
                    "event": "checkpoint_reached",
                    "message": f"Checkpoint {checkpoint_id} reached",
                    "context": {
                        "checkpoint_id": checkpoint_id,
                        "question": checkpoint.get("question", {}),
                    },
                }
            )
            if checkpoint.get("responded_at"):
                logs.append(
                    {
                        "timestamp": checkpoint.get("responded_at"),
                        "level": "info",
                        "event": "checkpoint_resolved",
                        "message": f"Checkpoint {checkpoint_id} resolved",
                        "context": {
                            "checkpoint_id": checkpoint_id,
                            "agent_id": checkpoint.get("agent_id", "unknown"),
                        },
                    }
                )

        # Add error log if execution failed
        if execution_state.get("error"):
            logs.append(
                {
                    "timestamp": execution_state.get("completed_at"),
                    "level": "error",
                    "event": "execution_failed",
                    "message": f"Execution failed: {execution_state.get('error')}",
                    "context": {"error": execution_state.get("error")},
                }
            )

        # Filter by event_type
        if event_type:
            logs = [log for log in logs if log["event"].startswith(event_type)]

        # Filter by level
        if level:
            logs = [log for log in logs if log["level"] == level]

        # Sort by timestamp
        logs.sort(key=lambda x: x.get("timestamp") or "", reverse=False)

        # Apply pagination
        total_logs = len(logs)
        paginated_logs = logs[offset : offset + limit]

        return {
            "execution_id": execution_id,
            "total_logs": total_logs,
            "returned_logs": len(paginated_logs),
            "logs": paginated_logs,
        }

    except Exception as e:
        logger.error(f"Error getting execution logs: {e}", exc_info=True)
        return {"error": str(e), "error_type": type(e).__name__}


async def _execute_workflow(
    execution_id: str, workflow_class: Any, input_params: dict[str, Any]
) -> None:
    """Execute workflow in background, updating execution state.

    Runs the workflow asynchronously, updating the execution state file
    with progress, checkpoints, and final result.

    Args:
        execution_id: Unique execution identifier
        workflow_class: Workflow class to instantiate and run
        input_params: Input parameters for the workflow
    """
    try:
        from ..framework.execution import Execution
        
        data_dir = get_data_dir()
        execution_file = data_dir / f"{execution_id}.json"

        # Load and update execution state to "running"
        with open(execution_file, "r") as f:
            execution_state = json.load(f)

        execution_state["status"] = "running"
        execution_state["started_at"] = datetime.utcnow().isoformat()

        with open(execution_file, "w") as f:
            json.dump(execution_state, f, indent=2)

        # Create Execution object for checkpoint management
        execution = Execution(
            execution_id=execution_id,
            base_url=execution_state.get("base_url", ""),
            data_dir=data_dir
        )
        execution._state.state = "running"
        execution._state.input_params = input_params
        
        # Store Execution object in memory so resolve_checkpoint can find it
        _active_executions[execution_id] = execution

        # Create workflow instance
        workflow = workflow_class()
        workflow.set_execution(execution)

        # Run workflow - this should handle checkpoints internally
        result = await workflow.run(**input_params)

        # Update execution state with success
        with open(execution_file, "r") as f:
            execution_state = json.load(f)

        execution_state["status"] = "completed"
        execution_state["output"] = result
        execution_state["completed_at"] = datetime.utcnow().isoformat()

        with open(execution_file, "w") as f:
            json.dump(execution_state, f, indent=2)

        # Update in-memory copy
        _active_executions[execution_id] = execution_state

        logger.info(
            "Workflow execution completed",
            extra={
                "execution_id": execution_id,
                "event": "execution_completed",
            })

        # Send completion notification
        notification_service = NotificationService()
        await notification_service.send_notification(
            "execution_completed",
            {"execution_id": execution_id, "result": result})

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)

        # Update execution state with error
        data_dir = get_data_dir()
        execution_file = data_dir / f"{execution_id}.json"

        with open(execution_file, "r") as f:
            execution_state = json.load(f)

        execution_state["status"] = "failed"
        execution_state["error"] = str(e)
        execution_state["completed_at"] = datetime.utcnow().isoformat()

        with open(execution_file, "w") as f:
            json.dump(execution_state, f, indent=2)

        _active_executions[execution_id] = execution_state

        # Send failure notification
        notification_service = NotificationService()
        await notification_service.send_notification(
            "execution_failed",
            {"execution_id": execution_id, "error": str(e)})


async def list_executions_impl(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0) -> dict[str, Any]:
    """List workflow executions with optional status filtering.

    Args:
        status: Filter by status (pending, running, paused, completed, failed)
        limit: Maximum number of executions to return (1-1000, default 50)
        offset: Pagination offset (default 0)

    Returns:
        {
            "total": int,
            "returned": int,
            "offset": int,
            "executions": [
                {
                    "execution_id": "uuid",
                    "workflow_type": "string",
                    "status": "string",
                    "created_at": "ISO8601",
                    "started_at": "ISO8601 or null",
                    "current_step": "string or null",
                    "pending_checkpoint": {
                        "checkpoint_id": "string",
                        "question": {...}
                    } or null
                },
                ...
            ]
        }
    """
    try:
        data_dir = get_data_dir()

        # Collect all execution files
        execution_files = sorted(data_dir.glob("*.json"))
        total = len(execution_files)

        # Filter by status if provided
        executions = []
        for file_path in execution_files:
            try:
                with open(file_path, "r") as f:
                    exec_state = json.load(f)

                # Apply status filter
                if status and exec_state.get("status") != status:
                    continue

                # Find pending checkpoint if any
                pending_checkpoint = None
                for cp in exec_state.get("checkpoints", []):
                    if cp.get("response") is None:
                        pending_checkpoint = {
                            "checkpoint_id": cp["checkpoint_id"],
                            "question": cp.get("question", {}),
                        }
                        break

                executions.append({
                    "execution_id": exec_state.get("execution_id"),
                    "workflow_type": exec_state.get("workflow_type"),
                    "status": exec_state.get("status"),
                    "created_at": exec_state.get("created_at"),
                    "started_at": exec_state.get("started_at"),
                    "current_step": exec_state.get("current_step"),
                    "pending_checkpoint": pending_checkpoint,
                })
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read execution file {file_path}: {e}")
                continue

        # Apply pagination
        returned_executions = executions[offset : offset + limit]
        returned_count = len(returned_executions)

        return {
            "total": total,
            "returned": returned_count,
            "offset": offset,
            "executions": returned_executions,
        }

    except Exception as e:
        logger.error(f"Error listing executions: {e}", exc_info=True)
        return {"error": str(e), "error_type": type(e).__name__}
