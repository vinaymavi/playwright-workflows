"""Fixtures for MCP server testing.

Provides subprocess-based MCP server for integration testing,
and JSON-RPC 2.0 client for communication.
"""

import asyncio
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Generator

import pytest

logger = logging.getLogger(__name__)


class MCPServerProcess:
    """Manages MCP server subprocess."""

    def __init__(self, server_module: str = "src.cli.mcp_server_runner", timeout: int = 10):
        """Initialize MCP server process manager.

        Args:
            server_module: Python module to run as MCP server
            timeout: Timeout in seconds for process startup/shutdown
        """
        self.server_module = server_module
        self.timeout = timeout
        self.process: subprocess.Popen | None = None
        self.temp_dir: Path | None = None
        self.logger = logging.getLogger(__name__)

    async def start(self, temp_data_dir: Path | None = None) -> None:
        """Start MCP server subprocess.

        Args:
            temp_data_dir: Directory for execution state files
        """
        # Create temp directory for execution storage
        if temp_data_dir is None:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="mcp_test_"))
        else:
            self.temp_dir = temp_data_dir

        # Set environment for subprocess
        env = {
            **dict(os.environ),  # type: ignore
            "WORKFLOW_DATA_DIR": str(self.temp_dir),
            "PYTHONUNBUFFERED": "1",
        }

        # Start MCP server
        self.logger.info(f"Starting MCP server from {self.server_module}")
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-m", self.server_module],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )

            # Wait for server to be ready (with timeout)
            await asyncio.sleep(0.5)

            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                raise RuntimeError(
                    f"MCP server failed to start.\nStdout: {stdout}\nStderr: {stderr}"
                )

            self.logger.info("MCP server started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start MCP server: {e}")
            raise

    async def stop(self) -> None:
        """Stop MCP server subprocess."""
        if self.process is None:
            return

        self.logger.info("Stopping MCP server")
        try:
            # Send terminate signal
            self.process.terminate()

            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                # Force kill if timeout
                self.process.kill()
                self.process.wait()

            self.logger.info("MCP server stopped")
        except Exception as e:
            self.logger.error(f"Error stopping MCP server: {e}")

        # Clean up temp directory
        if self.temp_dir:
            import shutil

            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except:
                pass

    async def send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC 2.0 request to MCP server.

        Args:
            method: MCP tool name (e.g., "start_workflow")
            params: Tool parameters

        Returns:
            Response dict

        Raises:
            RuntimeError: If server is not running or request fails
        """
        if self.process is None:
            raise RuntimeError("MCP server not running")

        # Build JSON-RPC 2.0 request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        request_json = json.dumps(request)

        try:
            # Send request
            self.process.stdin.write(request_json + "\n")
            self.process.stdin.flush()

            # Read response with timeout
            response_task = asyncio.create_task(self._read_response())
            response = await asyncio.wait_for(response_task, timeout=self.timeout)

            return response
        except asyncio.TimeoutError:
            raise RuntimeError(f"MCP server request timeout for {method}")
        except Exception as e:
            raise RuntimeError(f"MCP server communication error: {e}")

    async def _read_response(self) -> dict[str, Any]:
        """Read JSON-RPC 2.0 response from server."""
        # Read line from stdout
        loop = asyncio.get_event_loop()
        line = await loop.run_in_executor(None, self.process.stdout.readline)

        if not line:
            raise RuntimeError("MCP server closed connection")

        try:
            response = json.loads(line)
            return response
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from MCP server: {line}") from e


@pytest.fixture
async def mcp_server(tmp_path) -> AsyncGenerator[MCPServerProcess, None]:
    """Provide running MCP server for integration tests.

    Starts server before test, stops after test.
    """
    server = MCPServerProcess()
    temp_data_dir = tmp_path / "mcp_data"
    temp_data_dir.mkdir()

    try:
        await server.start(temp_data_dir)
        yield server
    finally:
        await server.stop()


@pytest.fixture
def mcp_temp_dir(tmp_path) -> Path:
    """Provide temp directory for MCP execution storage."""
    mcp_dir = tmp_path / "mcp_executions"
    mcp_dir.mkdir()
    return mcp_dir


# Import os at module level for environment setup
import os
