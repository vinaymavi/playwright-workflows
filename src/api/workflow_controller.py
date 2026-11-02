"""Python API client for workflow orchestration.

This module provides a convenient Python API to control workflow execution
without MCP overhead. Suitable for local Python programs that need to:
- Start workflows
- Monitor execution status
- Resolve checkpoints  
- Retrieve execution logs

Example:
    controller = WorkflowController()
    execution_id = controller.start("LoginWorkflow", {"url": "https://example.com"})
    while True:
        status = controller.get_status(execution_id)
        if status["status"] == "pending_checkpoint":
            controller.resolve_checkpoint(
                execution_id,
                status["pending_checkpoint"]["checkpoint_id"],
                "approved"
            )
        elif status["status"] in ("completed", "failed"):
            break
"""

import asyncio
from typing import Any, Dict, List, Optional

from src.mcp_server.tools import (
    start_workflow_impl,
    resolve_checkpoint_impl,
    get_execution_status_impl,
    get_execution_logs_impl,
)


class WorkflowController:
    """Python API client for workflow orchestration.
    
    Provides synchronous and asynchronous methods to control workflow
    execution via direct function calls (no MCP overhead).
    """

    def __init__(self):
        """Initialize workflow controller."""
        pass

    async def start_async(
        self,
        workflow_type: str,
        input_params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ) -> str:
        """Start a workflow asynchronously.
        
        Args:
            workflow_type: Type of workflow to execute
            input_params: Input parameters for the workflow
            max_retries: Maximum retry attempts on failure
            timeout_seconds: Execution timeout in seconds
            
        Returns:
            Execution ID for the started workflow
            
        Raises:
            ValueError: If workflow_type not registered
        """
        result = await start_workflow_impl(
            workflow_type=workflow_type,
            input_params=input_params or {},
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )
        
        if "error" in result:
            raise ValueError(result["error"])
        
        return result["execution_id"]

    def start(
        self,
        workflow_type: str,
        input_params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ) -> str:
        """Start a workflow (synchronous wrapper).
        
        Args:
            workflow_type: Type of workflow to execute
            input_params: Input parameters for the workflow
            max_retries: Maximum retry attempts on failure
            timeout_seconds: Execution timeout in seconds
            
        Returns:
            Execution ID for the started workflow
        """
        try:
            loop = asyncio.get_running_loop()
            raise RuntimeError(
                "Cannot use sync API from within an async context. "
                "Use start_async() instead."
            )
        except RuntimeError:
            pass
        
        return asyncio.run(
            self.start_async(workflow_type, input_params, max_retries, timeout_seconds)
        )

    async def get_status_async(self, execution_id: str) -> Dict[str, Any]:
        """Get workflow execution status asynchronously.
        
        Args:
            execution_id: Workflow execution ID
            
        Returns:
            Status dictionary with keys:
            - execution_id
            - workflow_type
            - status (pending, running, completed, failed, pending_checkpoint)
            - started_at
            - ended_at
            - completed_steps
            - total_steps
            - current_step_name
            - pending_checkpoint (if status is pending_checkpoint)
            - error (if status is failed)
        """
        return await get_execution_status_impl(execution_id)

    def get_status(self, execution_id: str) -> Dict[str, Any]:
        """Get workflow execution status (synchronous wrapper).
        
        Args:
            execution_id: Workflow execution ID
            
        Returns:
            Status dictionary
        """
        try:
            loop = asyncio.get_running_loop()
            raise RuntimeError(
                "Cannot use sync API from within an async context. "
                "Use get_status_async() instead."
            )
        except RuntimeError:
            pass
        
        return asyncio.run(self.get_status_async(execution_id))

    async def resolve_checkpoint_async(
        self,
        execution_id: str,
        checkpoint_id: str,
        decision: Dict[str, Any],
        agent_id: str = "python-api",
    ) -> Dict[str, Any]:
        """Resolve a workflow checkpoint asynchronously.
        
        Args:
            execution_id: Workflow execution ID
            checkpoint_id: Checkpoint ID to resolve
            decision: Decision/response to checkpoint as a dict (structure depends on checkpoint)
            agent_id: ID of agent providing resolution (default: "python-api")
            
        Returns:
            Resolution result with keys:
            - execution_id
            - checkpoint_id
            - status (resolved)
            - resolved_at
        """
        return await resolve_checkpoint_impl(
            execution_id=execution_id,
            checkpoint_id=checkpoint_id,
            decision=decision,
            agent_id=agent_id,
        )

    def resolve_checkpoint(
        self,
        execution_id: str,
        checkpoint_id: str,
        decision: Dict[str, Any],
        agent_id: str = "python-api",
    ) -> Dict[str, Any]:
        """Resolve a workflow checkpoint (synchronous wrapper).
        
        Args:
            execution_id: Workflow execution ID
            checkpoint_id: Checkpoint ID to resolve
            decision: Decision/response to checkpoint as a dict
            agent_id: ID of agent providing resolution
            
        Returns:
            Resolution result
        """
        try:
            loop = asyncio.get_running_loop()
            raise RuntimeError(
                "Cannot use sync API from within an async context. "
                "Use resolve_checkpoint_async() instead."
            )
        except RuntimeError:
            pass
        
        return asyncio.run(
            self.resolve_checkpoint_async(execution_id, checkpoint_id, decision, agent_id)
        )

    async def get_logs_async(
        self,
        execution_id: str,
        event_type: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get execution logs asynchronously.
        
        Args:
            execution_id: Workflow execution ID
            event_type: Filter by event type (step, checkpoint)
            level: Filter by log level (debug, info, warning, error)
            limit: Maximum logs to return (default 100, max 1000)
            offset: Pagination offset (default 0)
            
        Returns:
            List of log entries with keys:
            - timestamp
            - level
            - event
            - message
            - context
        """
        result = await get_execution_logs_impl(
            execution_id=execution_id,
            event_type=event_type,
            level=level,
            limit=limit,
            offset=offset,
        )
        
        if "error" in result:
            raise ValueError(result["error"])
        
        return result.get("logs", [])

    def get_logs(
        self,
        execution_id: str,
        event_type: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get execution logs (synchronous wrapper).
        
        Args:
            execution_id: Workflow execution ID
            event_type: Filter by event type
            level: Filter by log level
            limit: Maximum logs to return
            offset: Pagination offset
            
        Returns:
            List of log entries
        """
        try:
            loop = asyncio.get_running_loop()
            raise RuntimeError(
                "Cannot use sync API from within an async context. "
                "Use get_logs_async() instead."
            )
        except RuntimeError:
            pass
        
        return asyncio.run(
            self.get_logs_async(execution_id, event_type, level, limit, offset)
        )
