"""Tests for concurrent execution isolation and resource management.

Verifies that multiple concurrent executions don't interfere with each other
in terms of temp directories, state files, and checkpoint handling.
"""

import asyncio
from pathlib import Path

import pytest

from src.framework.execution import CheckpointState, Execution, ExecutionState


class TestConcurrentExecutionIsolation:
    """Test execution isolation under concurrent load."""

    @pytest.mark.asyncio
    async def test_ten_concurrent_executions_isolated(self, tmp_path):
        """Test 10 concurrent executions with isolated resources."""
        num_executions = 10
        temp_base_dir = tmp_path / "temp"
        data_dir = tmp_path / "executions"

        # Create 10 concurrent executions
        executions = [
            Execution(
                execution_id=f"concurrent-{i:03d}",
                base_url=f"https://example{i}.com",
                data_dir=data_dir,
                temp_base_dir=temp_base_dir,
            )
            for i in range(num_executions)
        ]

        # All should have unique temp directories
        temp_dirs = [e.temp_dir for e in executions]
        assert len(set(temp_dirs)) == num_executions, "Temp dirs must be unique"

        # All should have unique state files
        state_files = [e.state_file for e in executions]
        assert len(set(state_files)) == num_executions, "State files must be unique"

    @pytest.mark.asyncio
    async def test_concurrent_checkpoint_handling(self, tmp_path):
        """Test concurrent checkpoints don't interfere."""
        num_executions = 5
        temp_base_dir = tmp_path / "temp"
        data_dir = tmp_path / "executions"

        # Create 5 concurrent executions
        executions = [
            Execution(
                execution_id=f"checkpoint-{i:03d}",
                data_dir=data_dir,
                temp_base_dir=temp_base_dir,
            )
            for i in range(num_executions)
        ]

        # Start all
        for i, execution in enumerate(executions):
            execution.start({"test_id": i})

        # Create checkpoints on all
        checkpoints = []
        for i, execution in enumerate(executions):
            checkpoint = CheckpointState(
                checkpoint_id=f"ckpt-{i}",
                question={"type": "yes_no", "text": f"Continue {i}?"},
            )
            execution.pause(checkpoint)
            checkpoints.append(checkpoint)

        # Verify all are paused
        for execution in executions:
            assert execution.get_state() == ExecutionState.PAUSED

        # Resume all with different responses
        for i, execution in enumerate(executions):
            execution.resume(response={"answer": "yes" if i % 2 == 0 else "no"})

        # Verify all are running
        for execution in executions:
            assert execution.get_state() == ExecutionState.RUNNING

    @pytest.mark.asyncio
    async def test_concurrent_temp_file_writes(self, tmp_path):
        """Test concurrent writes to temp directories don't interfere."""
        num_executions = 10
        temp_base_dir = tmp_path / "temp"

        executions = [
            Execution(
                execution_id=f"temp-write-{i:03d}",
                temp_base_dir=temp_base_dir,
            )
            for i in range(num_executions)
        ]

        # Concurrent writes
        async def write_files(execution, idx):
            for j in range(5):
                file_path = execution.temp_dir / f"file-{j}.txt"
                file_path.write_text(f"content-{idx}-{j}")
                await asyncio.sleep(0.01)

        await asyncio.gather(*[write_files(e, i) for i, e in enumerate(executions)])

        # Verify each execution has correct files
        for i, execution in enumerate(executions):
            files = list(execution.temp_dir.glob("file-*.txt"))
            assert len(files) == 5, f"Execution {i} should have 5 files"

            for j in range(5):
                content = (execution.temp_dir / f"file-{j}.txt").read_text()
                assert content == f"content-{i}-{j}", f"Content mismatch for exec {i}, file {j}"

    @pytest.mark.asyncio
    async def test_concurrent_state_file_writes(self, tmp_path):
        """Test concurrent state file updates don't corrupt."""
        num_executions = 5
        data_dir = tmp_path / "executions"
        temp_base_dir = tmp_path / "temp"

        executions = [
            Execution(
                execution_id=f"state-write-{i:03d}",
                data_dir=data_dir,
                temp_base_dir=temp_base_dir,
            )
            for i in range(num_executions)
        ]

        # Concurrent state changes
        async def update_state(execution, idx):
            execution.start({"index": idx})
            await asyncio.sleep(0.01)

            checkpoint = CheckpointState(
                checkpoint_id=f"ckpt-{idx}",
                question={"id": idx},
            )
            execution.pause(checkpoint)
            await asyncio.sleep(0.01)

            execution.resume()

        await asyncio.gather(*[update_state(e, i) for i, e in enumerate(executions)])

        # Verify all states are valid
        for i, execution in enumerate(executions):
            state = execution._state
            assert state.execution_id == f"state-write-{i:03d}"
            assert state.input_params["index"] == i
            assert len(state.checkpoints) == 1
            assert state.state == ExecutionState.RUNNING

    @pytest.mark.asyncio
    async def test_concurrent_cleanup(self, tmp_path):
        """Test concurrent cleanup doesn't cause conflicts."""
        num_executions = 10
        temp_base_dir = tmp_path / "temp"
        data_dir = tmp_path / "executions"

        executions = [
            Execution(
                execution_id=f"cleanup-{i:03d}",
                data_dir=data_dir,
                temp_base_dir=temp_base_dir,
            )
            for i in range(num_executions)
        ]

        # Start and complete all
        for execution in executions:
            execution.start({})
            execution.complete()

        # Concurrent cleanup
        async def cleanup(execution):
            await asyncio.sleep(0.001)
            execution.cleanup()

        await asyncio.gather(*[cleanup(e) for e in executions])

        # Verify all cleaned
        for execution in executions:
            assert execution.temp_dir.exists() is False
            assert execution.state_file.exists() is False

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, tmp_path):
        """Test mixed concurrent operations (some starting, some paused, some cleaning)."""
        num_executions = 15
        temp_base_dir = tmp_path / "temp"
        data_dir = tmp_path / "executions"

        executions = [
            Execution(
                execution_id=f"mixed-{i:03d}",
                data_dir=data_dir,
                temp_base_dir=temp_base_dir,
            )
            for i in range(num_executions)
        ]

        async def mixed_workflow(execution, idx):
            if idx < 5:
                # Group 1: Just start
                execution.start({"group": 1})
            elif idx < 10:
                # Group 2: Start and pause
                execution.start({"group": 2})
                checkpoint = CheckpointState(
                    checkpoint_id=f"ckpt-{idx}",
                    question={"group": 2},
                )
                execution.pause(checkpoint)
            else:
                # Group 3: Full lifecycle
                execution.start({"group": 3})
                checkpoint = CheckpointState(
                    checkpoint_id=f"ckpt-{idx}",
                    question={"group": 3},
                )
                execution.pause(checkpoint)
                await asyncio.sleep(0.005)
                execution.resume()
                execution.complete()

            await asyncio.sleep(0.01)

        await asyncio.gather(*[mixed_workflow(e, i) for i, e in enumerate(executions)])

        # Verify states
        for i, execution in enumerate(executions):
            if i < 5:
                assert execution.get_state() == ExecutionState.RUNNING
            elif i < 10:
                assert execution.get_state() == ExecutionState.PAUSED
            else:
                assert execution.get_state() == ExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_concurrent_resource_cleanup_integrity(self, tmp_path):
        """Test that cleanup during concurrent operations maintains integrity."""
        num_executions = 20
        temp_base_dir = tmp_path / "temp"
        data_dir = tmp_path / "executions"

        executions = [
            Execution(
                execution_id=f"integrity-{i:03d}",
                data_dir=data_dir,
                temp_base_dir=temp_base_dir,
            )
            for i in range(num_executions)
        ]

        async def resource_intensive_workflow(execution, idx):
            execution.start({})

            # Create many temp files
            for j in range(10):
                (execution.temp_dir / f"artifact-{j}.bin").write_bytes(b"x" * 1000)

            checkpoint = CheckpointState(
                checkpoint_id=f"ckpt-{idx}",
                question={"data": "intensive"},
            )
            execution.pause(checkpoint)
            await asyncio.sleep(0.005)

            execution.resume()
            execution.complete()
            execution.cleanup()

        await asyncio.gather(
            *[resource_intensive_workflow(e, i) for i, e in enumerate(executions)]
        )

        # Verify all cleaned and no orphaned directories
        temp_dirs_remaining = list(temp_base_dir.glob("*"))
        assert len(temp_dirs_remaining) == 0, f"Found orphaned temp dirs: {temp_dirs_remaining}"

        # Verify state files for terminal states are cleaned
        state_files = list(data_dir.glob("*.json"))
        assert len(state_files) == 0, f"Found orphaned state files: {state_files}"

    @pytest.mark.asyncio
    async def test_rapid_sequential_same_id(self, tmp_path):
        """Test rapid sequential reuse of same execution ID."""
        execution_id = "reuse-test"
        temp_base_dir = tmp_path / "temp"
        data_dir = tmp_path / "executions"

        for i in range(5):
            execution = Execution(
                execution_id=execution_id,
                data_dir=data_dir,
                temp_base_dir=temp_base_dir,
            )

            # Note: Each new Execution with same ID gets fresh temp_dir
            # (old one would need cleanup first)
            execution.start({})
            execution.complete()
            execution.cleanup()

        # Verify no artifacts left
        assert (temp_base_dir / execution_id).exists() is False
        assert (data_dir / f"{execution_id}.json").exists() is False


class TestConcurrentStressTests:
    """Stress tests for concurrent execution handling."""

    @pytest.mark.asyncio
    async def test_high_concurrency_100_executions(self, tmp_path):
        """Stress test with 100 concurrent executions."""
        num_executions = 100
        temp_base_dir = tmp_path / "temp"

        executions = [
            Execution(
                execution_id=f"stress-{i:04d}",
                temp_base_dir=temp_base_dir,
            )
            for i in range(num_executions)
        ]

        async def quick_workflow(execution, idx):
            execution.start({"idx": idx})
            # Create one temp file
            (execution.temp_dir / "data.txt").write_text(f"data-{idx}")
            execution.complete()
            execution.cleanup()

        await asyncio.gather(*[quick_workflow(e, i) for i, e in enumerate(executions)])

        # Verify all cleaned
        temp_dirs = list(temp_base_dir.glob("*"))
        assert len(temp_dirs) == 0

    @pytest.mark.asyncio
    async def test_concurrent_with_checkpoint_timeouts(self, tmp_path):
        """Test concurrent executions with checkpoint timeout handling."""
        num_executions = 5
        temp_base_dir = tmp_path / "temp"
        data_dir = tmp_path / "executions"

        executions = [
            Execution(
                execution_id=f"timeout-{i:03d}",
                data_dir=data_dir,
                temp_base_dir=temp_base_dir,
            )
            for i in range(num_executions)
        ]

        async def timeout_workflow(execution, idx):
            execution.start({})
            checkpoint = CheckpointState(
                checkpoint_id=f"ckpt-{idx}",
                question={"type": "yes_no"},
                timeout_seconds=10 + idx,  # Different timeouts
            )
            execution.pause(checkpoint)
            await asyncio.sleep(0.05)
            execution.resume()

        await asyncio.gather(*[timeout_workflow(e, i) for i, e in enumerate(executions)])

        # Verify all completed correctly
        for execution in executions:
            assert execution.get_state() == ExecutionState.RUNNING
            assert len(execution._state.checkpoints) == 1
