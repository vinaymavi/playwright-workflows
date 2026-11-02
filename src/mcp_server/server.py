"""MCP Server for Workflow Orchestration

Exposes Playwright workflow orchestration tools and resources via
Model Context Protocol (MCP) server over stdio transport.

Tools:
- start_workflow: Create new workflow execution
- resolve_checkpoint: Provide agent decision to resume paused workflow
- get_execution_status: Poll execution status and progress
- get_execution_logs: Retrieve structured execution logs

Resources:
- workflow://{workflow_type}: Metadata for workflow type
- execution/{execution_id}: Complete execution state

Notifications:
- checkpoint_requested: Sent when workflow hits checkpoint
- execution_completed: Sent when workflow finishes successfully
- execution_failed: Sent when workflow fails
"""

import asyncio
import json
from typing import Any, Annotated

from mcp.server import MCPServer
from pydantic import BaseModel, Field


# Request/Response models for type safety
class StartWorkflowRequest(BaseModel):
    """Start workflow request."""
    workflow_type: str = Field(
        description="Type/name of workflow to execute (e.g., 'login_workflow', 'form_filling')"
    )
    input_params: dict = Field(
        default_factory=dict,
        description="Workflow-specific input parameters"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Max retries for transient errors"
    )
    timeout_seconds: int = Field(
        default=3600,
        ge=10,
        description="Hard timeout for entire workflow execution"
    )


class ResolveCheckpointRequest(BaseModel):
    """Resolve checkpoint request."""
    execution_id: str = Field(description="UUID v4 of the execution to resume")
    checkpoint_id: str = Field(description="UUID v4 of the checkpoint to resolve")
    decision: dict = Field(
        description="Agent's decision response (structure depends on checkpoint question)"
    )
    agent_id: str = Field(
        default="unknown",
        description="Identifier of agent making the decision"
    )


class GetExecutionStatusRequest(BaseModel):
    """Get execution status request."""
    execution_id: str = Field(description="UUID v4 of the execution to query")


class GetExecutionLogsRequest(BaseModel):
    """Get execution logs request."""
    execution_id: str = Field(description="UUID v4 of the execution")
    event_type: str | None = Field(
        default=None,
        description="Filter by event type"
    )
    level: str | None = Field(
        default=None,
        description="Filter by log level (debug, info, warning, error)"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of logs to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Pagination offset"
    )


# Create the MCP server instance
mcp = MCPServer("WorkflowOrchestrator")


@mcp.tool()
async def start_workflow(
    workflow_type: Annotated[str, Field(description="Type/name of workflow to execute")],
    input_params: Annotated[dict, Field(default_factory=dict, description="Input parameters")],
    max_retries: Annotated[int, Field(default=3, ge=0, le=10, description="Max retries")],
    timeout_seconds: Annotated[int, Field(default=3600, ge=10, description="Timeout in seconds")],
) -> str:
    """Start a new Playwright workflow execution."""
    from .tools import start_workflow_impl
    
    result = await start_workflow_impl(
        workflow_type=workflow_type,
        input_params=input_params,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
    )
    return json.dumps(result)


@mcp.tool()
async def resolve_checkpoint(
    execution_id: Annotated[str, Field(description="UUID v4 of execution to resume")],
    checkpoint_id: Annotated[str, Field(description="UUID v4 of checkpoint to resolve")],
    decision: Annotated[dict, Field(description="Agent's decision response")],
    agent_id: Annotated[str, Field(default="unknown", description="Agent identifier")],
) -> str:
    """Provide agent/human decision to resume a paused workflow from checkpoint."""
    from .tools import resolve_checkpoint_impl
    
    result = await resolve_checkpoint_impl(
        execution_id=execution_id,
        checkpoint_id=checkpoint_id,
        decision=decision,
        agent_id=agent_id,
    )
    return json.dumps(result)


@mcp.tool()
async def get_execution_status(
    execution_id: Annotated[str, Field(description="UUID v4 of execution to query")],
) -> str:
    """Get current status and progress of a workflow execution."""
    from .tools import get_execution_status_impl
    
    result = await get_execution_status_impl(execution_id=execution_id)
    return json.dumps(result)


@mcp.tool()
async def get_execution_logs(
    execution_id: Annotated[str, Field(description="UUID v4 of execution")],
    event_type: Annotated[str | None, Field(default=None, description="Filter by event type")] = None,
    level: Annotated[str | None, Field(default=None, description="Filter by log level")] = None,
    limit: Annotated[int, Field(default=100, ge=1, le=1000, description="Max logs")] = 100,
    offset: Annotated[int, Field(default=0, ge=0, description="Pagination offset")] = 0,
) -> str:
    """Retrieve structured execution logs with optional filtering."""
    from .tools import get_execution_logs_impl
    
    result = await get_execution_logs_impl(
        execution_id=execution_id,
        event_type=event_type,
        level=level,
        limit=limit,
        offset=offset,
    )
    return json.dumps(result)


async def main() -> None:
    """Entry point for running MCP server."""
    async with mcp.stdio():
        await mcp.run()


def create_server() -> MCPServer:
    """Factory function to return MCP server instance."""
    return mcp


if __name__ == "__main__":
    asyncio.run(main())
