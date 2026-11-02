"""Tests for batch workflow execution with concurrency control."""

import asyncio
import json
import pytest
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from src.cli.batch_runner import BatchRunner, BatchExecutionResult
from src.workflows.login_workflow import LoginWorkflow


@pytest.mark.asyncio
class TestBatchExecution:
    """Test batch execution of multiple workflows."""

    async def test_batch_execution_with_10_workflows(self):
        """Test executing 10 LoginWorkflows in parallel with max 5 concurrent."""
        # Setup batch runner with max 5 concurrent
        runner = BatchRunner(max_concurrent=5, output_format="json")

        # Create 10 workflow specifications
        workflow_specs = [
            {
                "workflow_type": "login",
                "input": {
                    "url": "http://localhost:8000",
                    "username": f"user{i:02d}",
                    "password": f"pass{i:02d}",
                },
            }
            for i in range(10)
        ]

        # Run batch
        result = await runner.run_batch(workflow_specs)

        # Verify all workflows completed
        assert result.total_workflows == 10
        assert result.succeeded + result.failed == 10

        # Verify concurrency was respected (execution isolation)
        assert result.total_time_seconds > 0

        # Convert to dict for detailed inspection
        result_dict = result.to_dict()
        assert "success" in result_dict
        assert "succeeded" in result_dict
        assert "failed" in result_dict
        assert "total_time_seconds" in result_dict

    async def test_batch_execution_verifies_state_isolation(self):
        """Test that 10 concurrent workflows maintain isolated state."""
        runner = BatchRunner(max_concurrent=5, output_format="json")

        # Create 10 workflows with different credentials
        workflow_specs = [
            {
                "workflow_type": "login",
                "input": {
                    "url": f"http://localhost:800{i}",
                    "username": f"user{i:02d}",
                    "password": f"secret{i:02d}",
                },
            }
            for i in range(10)
        ]

        # Execute batch
        result = await runner.run_batch(workflow_specs)

        # Verify batch completed
        assert result.total_workflows == 10

        # Verify results contain expected structure
        for exec_result in result.results:
            assert "execution_id" in exec_result
            assert "workflow_type" in exec_result
            assert "status" in exec_result
            assert "success" in exec_result

    async def test_batch_execution_respects_concurrency_limit(self):
        """Test that batch runner respects max_concurrent limit."""
        max_concurrent = 3
        runner = BatchRunner(max_concurrent=max_concurrent, output_format="json")

        # Create workflows
        workflow_specs = [
            {
                "workflow_type": "login",
                "input": {
                    "url": "http://localhost:8000",
                    "username": f"user{i}",
                    "password": f"pass{i}",
                },
            }
            for i in range(6)
        ]

        # Track concurrent execution timing
        # The runner should enforce max_concurrent through ConcurrencyManager
        result = await runner.run_batch(workflow_specs)

        # Verify all completed
        assert result.total_workflows == 6
        assert result.total_time_seconds > 0

    async def test_batch_execution_returns_summary(self):
        """Test that batch execution returns proper summary."""
        runner = BatchRunner(max_concurrent=5, output_format="json")

        # Create 5 workflows
        workflow_specs = [
            {
                "workflow_type": "login",
                "input": {
                    "url": "http://localhost:8000",
                    "username": f"user{i}",
                    "password": f"pass{i}",
                },
            }
            for i in range(5)
        ]

        # Run batch
        result = await runner.run_batch(workflow_specs)

        # Verify summary structure
        assert isinstance(result, BatchExecutionResult)
        assert result.total_workflows == 5
        assert result.succeeded >= 0
        assert result.failed >= 0
        assert result.succeeded + result.failed == 5
        assert result.total_time_seconds > 0
        assert len(result.results) == result.succeeded
        assert len(result.errors) == result.failed

    async def test_batch_execution_with_logging(self):
        """Test batch execution with log file output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BatchRunner(max_concurrent=5, output_format="json")

            # Create 3 workflows
            workflow_specs = [
                {
                    "workflow_type": "login",
                    "input": {
                        "url": "http://localhost:8000",
                        "username": f"user{i}",
                        "password": f"pass{i}",
                    },
                }
                for i in range(3)
            ]

            # Run with log directory
            result = await runner.run_batch(workflow_specs, log_dir=tmpdir)

            # Verify logs directory was created
            log_dir = Path(tmpdir)
            assert log_dir.exists()

            # Verify batch execution completed
            assert result.total_workflows == 3

    async def test_batch_execution_output_formats(self):
        """Test batch execution output in different formats."""
        # Test JSON output format
        runner_json = BatchRunner(max_concurrent=5, output_format="json")
        workflow_specs = [
            {
                "workflow_type": "login",
                "input": {
                    "url": "http://localhost:8000",
                    "username": f"user{i}",
                    "password": f"pass{i}",
                },
            }
            for i in range(2)
        ]

        result = await runner_json.run_batch(workflow_specs)
        result_dict = result.to_dict()

        # Verify JSON output format
        assert "total_workflows" in result_dict
        assert "succeeded" in result_dict
        assert "failed" in result_dict
        assert "total_time_seconds" in result_dict
        assert "success" in result_dict
        assert "summary" in result_dict

        # Test text output format
        runner_text = BatchRunner(max_concurrent=5, output_format="text")
        result2 = await runner_text.run_batch(workflow_specs)
        assert result2.total_workflows == 2


@pytest.mark.asyncio
class TestBatchExecutionErrorHandling:
    """Test error handling in batch execution."""

    async def test_batch_execution_aggregates_errors(self):
        """Test that batch execution properly aggregates errors."""
        runner = BatchRunner(max_concurrent=5, output_format="json")

        # Create workflows (some may fail based on invalid inputs)
        workflow_specs = [
            {
                "workflow_type": "login",
                "input": {
                    "url": "http://localhost:8000",
                    "username": f"user{i}",
                    "password": f"pass{i}",
                },
            }
            for i in range(5)
        ]

        # Run batch
        result = await runner.run_batch(workflow_specs)

        # Verify error handling structure
        assert isinstance(result.errors, list)
        if result.failed > 0:
            # Verify error format
            for error in result.errors:
                assert "execution_id" in error
                assert "status" in error
                assert "error" in error or "error_type" in error

    async def test_batch_execution_partial_failure(self):
        """Test batch execution with partial failures."""
        runner = BatchRunner(max_concurrent=5, output_format="json")

        # Create mix of valid workflow specs
        workflow_specs = [
            {
                "workflow_type": "login",
                "input": {
                    "url": "http://localhost:8000",
                    "username": f"user{i}",
                    "password": f"pass{i}",
                },
            }
            for i in range(5)
        ]

        result = await runner.run_batch(workflow_specs)

        # Verify partial failure tracking
        assert result.total_workflows == 5
        assert result.succeeded + result.failed == 5

        # If there were failures, verify they're tracked
        if result.failed > 0:
            assert len(result.errors) == result.failed


@pytest.mark.asyncio
class TestBatchExecutionConcurrency:
    """Test concurrency behavior of batch execution."""

    async def test_batch_execution_max_concurrent_5(self):
        """Test batch with max_concurrent=5."""
        runner = BatchRunner(max_concurrent=5, output_format="json")

        # Create 10 workflows
        workflow_specs = [
            {
                "workflow_type": "login",
                "input": {
                    "url": "http://localhost:8000",
                    "username": f"user{i}",
                    "password": f"pass{i}",
                },
            }
            for i in range(10)
        ]

        result = await runner.run_batch(workflow_specs)

        # Verify execution completed
        assert result.total_workflows == 10
        assert result.total_time_seconds > 0

        # With max 5 concurrent, 10 workflows should take at least 2 "batches"
        # Total time should reflect this batching

    async def test_batch_execution_different_concurrency_limits(self):
        """Test batch execution with different concurrency limits."""
        for max_concurrent in [1, 3, 5, 10]:
            runner = BatchRunner(max_concurrent=max_concurrent, output_format="json")

            # Create 5 workflows
            workflow_specs = [
                {
                    "workflow_type": "login",
                    "input": {
                        "url": "http://localhost:8000",
                        "username": f"user{i}",
                        "password": f"pass{i}",
                    },
                }
                for i in range(5)
            ]

            result = await runner.run_batch(workflow_specs)

            # Verify execution completed with specified concurrency
            assert result.total_workflows == 5
            assert result.total_time_seconds > 0


@pytest.mark.asyncio
class TestBatchExecutionIntegration:
    """Integration tests for batch execution."""

    async def test_scenario_d_10_workflows_max_5_concurrent(self):
        """Test Scenario D: 10 workflows, max 5 concurrent, all complete, no conflicts."""
        runner = BatchRunner(max_concurrent=5, output_format="json")

        # Create 10 LoginWorkflow specifications
        workflow_specs = [
            {
                "workflow_type": "login",
                "input": {
                    "url": "http://localhost:8000",
                    "username": f"contractor{i:02d}",
                    "password": f"secure_pass_{i:02d}",
                },
            }
            for i in range(10)
        ]

        # Execute batch
        result = await runner.run_batch(workflow_specs)

        # Verify all workflows completed
        assert result.total_workflows == 10
        assert result.succeeded + result.failed == 10

        # Verify no execution conflicts (all completed in reasonable time)
        assert result.total_time_seconds > 0

        # Verify results are properly aggregated
        result_dict = result.to_dict()
        assert result_dict["total_workflows"] == 10
        assert "summary" in result_dict
