"""MCP Server Module for Workflow Orchestration

Exposes workflow control via Model Context Protocol (MCP) server.
Provides tools for starting workflows, resolving checkpoints, and monitoring execution.
"""

from .notifications import NotificationService
from .server import mcp, create_server
from .tools import register_workflow

__all__ = [
    "mcp",
    "create_server",
    "NotificationService",
    "register_workflow",
]
