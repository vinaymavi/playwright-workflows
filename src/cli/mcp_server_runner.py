"""MCP Server Runner - Entrypoint for running MCP server on stdio.

This module provides a CLI entrypoint to run the workflow MCP server,
which communicates with clients via JSON-RPC 2.0 on stdin/stdout.

Usage:
    python3 -m src.cli.mcp_server_runner

The server will:
1. Initialize on stdio transport
2. Listen for JSON-RPC 2.0 requests
3. Dispatch to appropriate tools/resources
4. Send responses and notifications back to client
"""


from src.mcp_server.server import create_server


async def main() -> None:
    """Run the MCP server on stdio."""
    server = create_server()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
