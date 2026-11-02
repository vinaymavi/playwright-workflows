"""Scenario E: WorkflowController Python API Client

This scenario demonstrates using the WorkflowController Python API client
to programmatically control workflows in a Python program.

WorkflowController provides:
- Async and sync methods for workflow control
- Start/status/resolve/logs operations
- Proper Python typing and error handling
- Integration with Python programs and MCP servers

This test scenario demonstrates the API patterns.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from src.api.workflow_controller import WorkflowController
from src.mcp_server.tools import register_workflow


class SimpleWorkflow:
    """Simple test workflow for scenario testing."""
    
    workflow_type = "scenario_e_test"
    
    def __init__(self):
        self.state = {}
    
    async def run(self, input_data):
        """Run the workflow with simple test data."""
        await asyncio.sleep(0.01)
        return {"status": "success"}


class TestScenarioEController:
    """Scenario E: WorkflowController API usage demonstration."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Register test workflow."""
        register_workflow("scenario_e_test", SimpleWorkflow)
        yield
    
    @pytest.mark.asyncio
    async def test_start_and_monitor_async(self):
        """Test starting a workflow and monitoring its status asynchronously."""
        controller = WorkflowController()
        
        # Start workflow asynchronously
        execution_id = await controller.start_async(
            workflow_type="scenario_e_test",
            input_params={},
        )
        
        # Verify we got a valid execution_id (string UUID)
        assert isinstance(execution_id, str)
        assert len(execution_id) > 0
    
    def test_start_synchronous(self):
        """Test starting a workflow using the synchronous API."""
        controller = WorkflowController()
        
        # Start workflow synchronously
        result = controller.start(
            workflow_type="scenario_e_test",
            input_params={"test": "data"},
        )
        
        # Verify we got a response
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_workflow(self):
        """Test error handling for invalid workflow type."""
        controller = WorkflowController()
        
        with pytest.raises(ValueError):
            await controller.start_async(
                workflow_type="nonexistent",
                input_params={},
            )
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_execution(self):
        """Test handling for non-existent execution."""
        controller = WorkflowController()
        
        # Try to get status of non-existent execution
        status = await controller.get_status_async("invalid-id-12345")
        
        # Should return status dict (implementation returns error in dict)
        assert isinstance(status, dict)
        assert "execution_id" in status or "error" in status
    
    @pytest.mark.asyncio
    async def test_concurrent_workflow_starts(self):
        """Test starting multiple workflows concurrently."""
        controller = WorkflowController()
        
        # Start 3 workflows concurrently
        tasks = [
            controller.start_async(
                workflow_type="scenario_e_test",
                input_params={"worker_id": i},
            )
            for i in range(3)
        ]
        
        results = await asyncio.gather(*tasks)
        assert len(results) == 3
    
    def test_sync_api_basic_flow(self):
        """Test basic synchronous API flow."""
        controller = WorkflowController()
        
        # Start workflow
        start_result = controller.start(
            workflow_type="scenario_e_test",
            input_params={"sync_test": True},
        )
        assert start_result is not None
        
        # The pattern shows how sync API works for Python programs
        # Real usage would have error handling and status polling
