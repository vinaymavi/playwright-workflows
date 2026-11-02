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
from typing import Any, Callable, Dict, Optional

from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
)


class WorkflowMCPServer:
    """MCP Server for workflow orchestration.
    
    Handles JSON-RPC 2.0 requests over stdio transport, exposing
    workflow control tools and execution resources.
    """

    def __init__(self):
        """Initialize MCP server with tools and resources."""
        self.server = Server("WorkflowOrchestrator")
        self._setup_tools()
        self._setup_resources()

    def _setup_tools(self) -> None:
        """Register MCP tools for workflow control."""
        # Import here to avoid circular dependencies
        from .tools import (
            start_workflow_impl,
            resolve_checkpoint_impl,
            get_execution_status_impl,
            get_execution_logs_impl,
        )

        # Register start_workflow tool
        self.server.add_tool(
            Tool(
                name="start_workflow",
                description="Start a new Playwright workflow execution",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_type": {
                            "type": "string",
                            "description": "Type/name of workflow to execute "
                            "(e.g., 'login_workflow', 'form_filling')",
                        },
                        "input_params": {
                            "type": "object",
                            "description": "Workflow-specific input parameters (JSON object)",
                            "additionalProperties": True,
                        },
                        "max_retries": {
                            "type": "integer",
                            "description": "Max retries for transient errors (default 3)",
                            "default": 3,
                            "minimum": 0,
                            "maximum": 10,
                        },
                        "timeout_seconds": {
                            "type": "integer",
                            "description": "Hard timeout for entire workflow execution (default 3600)",
                            "default": 3600,
                            "minimum": 10,
                        },
                    },
                    "required": ["workflow_type"],
                    "additionalProperties": False,
                },
            ),
            start_workflow_impl,
        )

        # Register resolve_checkpoint tool
        self.server.add_tool(
            Tool(
                name="resolve_checkpoint",
                description="Provide agent/human decision to resume a paused workflow from checkpoint",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "execution_id": {
                            "type": "string",
                            "description": "UUID v4 of the execution to resume",
                        },
                        "checkpoint_id": {
                            "type": "string",
                            "description": "UUID v4 of the checkpoint to resolve",
                        },
                        "decision": {
                            "type": "object",
                            "description": "Agent's decision response "
                            "(structure depends on checkpoint question)",
                            "additionalProperties": True,
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Identifier of agent making the decision (for audit)",
                            "default": "unknown",
                        },
                    },
                    "required": ["execution_id", "checkpoint_id", "decision"],
                    "additionalProperties": False,
                },
            ),
            resolve_checkpoint_impl,
        )

        # Register get_execution_status tool
        self.server.add_tool(
            Tool(
                name="get_execution_status",
                description="Get current status and progress of a workflow execution",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "execution_id": {
                            "type": "string",
                            "description": "UUID v4 of the execution to query",
                        },
                    },
                    "required": ["execution_id"],
                    "additionalProperties": False,
                },
            ),
            get_execution_status_impl,
        )

        # Register get_execution_logs tool
        self.server.add_tool(
            Tool(
                name="get_execution_logs",
                description="Retrieve structured execution logs with optional filtering",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "execution_id": {
                            "type": "string",
                            "description": "UUID v4 of the execution",
                        },
                        "event_type": {
                            "type": "string",
                            "description": "Filter by event type "
                            "(step_started, step_completed, checkpoint_reached, etc.)",
                        },
                        "level": {
                            "type": "string",
                            "description": "Filter by log level (debug, info, warning, error)",
                            "enum": ["debug", "info", "warning", "error"],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of logs to return (default 100)",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 1000,
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Pagination offset (default 0)",
                            "default": 0,
                            "minimum": 0,
                        },
                    },
                    "required": ["execution_id"],
                    "additionalProperties": False,
                },
            ),
            get_execution_logs_impl,
        )

    def _setup_resources(self) -> None:
        """Register MCP resources for workflow metadata and state."""
        # Resources will be registered once resource handler framework is in place
        # For now, tools provide the necessary access patterns
        pass

    async def run(self) -> None:
        """Run the MCP server on stdio transport.
        
        Handles JSON-RPC 2.0 requests from MCP client indefinitely.
        """
        async with self.server:
            # Server runs on stdio transport, handling requests until closed
            await self.server.run()


def create_server() -> WorkflowMCPServer:
    """Factory function to create MCP server instance."""
    return WorkflowMCPServer()


async def main() -> None:
    """Entry point for running MCP server."""
    server = create_server()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
