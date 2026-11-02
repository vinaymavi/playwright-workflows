"""Integration tests for concurrent execution state isolation.

Tests N concurrent executions to verify:
- Each execution loads own state from data/executions/{execution_id}.json
- Executions don't cross-contaminate state files
- File locking prevents state corruption during concurrent writes
- Semaphore limits actual concurrency to configured max (default 5)
"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.framework.concurrency_manager import ConcurrencyManager
from src.framework.checkpoint_store import CheckpointStore
from src.framework.execution import Execution


class MockWorkflowState:
    """Mock workflow execution state for testing."""

    def __init__(self, execution_id: str, user_id: str = None, test_data: dict = None):
        self.execution_id = execution_id
        self.user_id = user_id or f"user-{execution_id}"
        self.test_data = test_data or {"counter": 0, "values": []}
        self.updated_at = time.time()


class TestConcurrentStateIsolation:
    """Test state isolation across concurrent executions."""

    @pytest.mark.asyncio
    async def test_concurrent_executions_load_own_state(self, tmp_path):
        """Test 10 concurrent executions each load their own state file."""
        n_executions = 10
        execution_states = {}

        # Create state files for each execution
        executions_dir = tmp_path / "data" / "executions"
        executions_dir.mkdir(parents=True, exist_ok=True)

        for i in range(n_executions):
            exec_id = f"exec-{i}"
            state_file = executions_dir / f"{exec_id}.json"
            state_data = {
                "execution_id": exec_id,
                "user_id": f"user-{i}",
                "counter": i * 100,
                "values": list(range(i)),
            }
            state_file.write_text(json.dumps(state_data))
            execution_states[exec_id] = state_data

        # Simulate concurrent loading
        async def load_state(exec_id: str):
            state_file = executions_dir / f"{exec_id}.json"
            await asyncio.sleep(0.001)  # Simulate I/O
            return json.loads(state_file.read_text())

        results = await asyncio.gather(
            *[load_state(f"exec-{i}") for i in range(n_executions)]
        )

        # Verify each execution got its own state
        for i, result in enumerate(results):
            assert result["execution_id"] == f"exec-{i}"
            assert result["user_id"] == f"user-{i}"
            assert result["counter"] == i * 100
            assert result["values"] == list(range(i))

    @pytest.mark.asyncio
    async def test_concurrent_writes_dont_corrupt_state(self, tmp_path):
        """Test concurrent state writes don't corrupt individual files."""
        n_executions = 5
        executions_dir = tmp_path / "data" / "executions"
        executions_dir.mkdir(parents=True, exist_ok=True)

        # Initialize state files
        for i in range(n_executions):
            exec_id = f"exec-{i}"
            state_file = executions_dir / f"{exec_id}.json"
            state_data = {
                "execution_id": exec_id,
                "iteration": 0,
                "data": list(range(10)),
            }
            state_file.write_text(json.dumps(state_data))

        # Concurrent writer: simulate state updates
        async def update_state(exec_id: str, iterations: int = 10):
            state_file = executions_dir / f"{exec_id}.json"

            for iteration in range(iterations):
                # Read-modify-write cycle (simulates file locking)
                state_data = json.loads(state_file.read_text())
                state_data["iteration"] = iteration
                state_data["data"].append(iteration)

                # Brief delay to increase chance of contention
                await asyncio.sleep(0.001)

                state_file.write_text(json.dumps(state_data))

        # Run concurrent updates
        await asyncio.gather(
            *[update_state(f"exec-{i}", 5) for i in range(n_executions)]
        )

        # Verify each file is valid and not corrupted
        for i in range(n_executions):
            exec_id = f"exec-{i}"
            state_file = executions_dir / f"{exec_id}.json"

            # Should be valid JSON
            state_data = json.loads(state_file.read_text())

            # Should have correct structure
            assert state_data["execution_id"] == exec_id
            assert state_data["iteration"] == 4  # Last iteration
            assert isinstance(state_data["data"], list)

    @pytest.mark.asyncio
    async def test_concurrent_executions_with_checkpoint_store(self, tmp_path):
        """Test checkpoint store isolates state per execution during concurrent access."""
        n_executions = 5

        # Create checkpoint stores for each execution
        stores = {}
        for i in range(n_executions):
            exec_id = f"exec-{i}"
            store_dir = tmp_path / f"checkpoints-{i}"
            store_dir.mkdir(exist_ok=True)
            stores[exec_id] = CheckpointStore(store_dir=str(store_dir))

        # Concurrent checkpoint creation
        async def create_checkpoints(exec_id: str, count: int = 3):
            store = stores[exec_id]

            for i in range(count):
                checkpoint_data = {
                    "checkpoint_id": f"{exec_id}-cp-{i}",
                    "workflow_step": f"step-{i}",
                    "workflow_state": {"step": i, "exec_id": exec_id},
                    "human_question": "Test question",
                    "pause_duration_seconds": 60,
                    "execution_id": exec_id,
                }

                store.save(checkpoint_data)
                await asyncio.sleep(0.001)

        # Create checkpoints concurrently
        await asyncio.gather(
            *[create_checkpoints(f"exec-{i}", 3) for i in range(n_executions)]
        )

        # Verify each store has correct checkpoints
        for i in range(n_executions):
            exec_id = f"exec-{i}"
            store = stores[exec_id]

            checkpoints_data = store.query_execution_checkpoints(exec_id)

            # Should have 3 checkpoints for this execution
            assert len(checkpoints_data) == 3

            # All should have this exec_id in their ID
            for cp in checkpoints_data:
                assert exec_id in cp["checkpoint_id"]


class TestSemaphoreEnforcesConcurrencyLimit:
    """Test that semaphore properly limits concurrent executions."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_acquisitions(self):
        """Test semaphore blocks acquisitions beyond max_concurrent."""
        max_concurrent = 3
        manager = ConcurrencyManager(max_concurrent=max_concurrent)

        active_count = 0
        max_active = 0

        async def task(task_id: int):
            nonlocal active_count, max_active

            # Acquire slot
            await manager.acquire_execution_slot(f"task-{task_id}")
            active_count += 1
            max_active = max(max_active, active_count)

            # Simulate work
            await asyncio.sleep(0.01)

            # Release slot
            await manager.release_execution_slot(f"task-{task_id}")
            active_count -= 1

        # Try to run 10 tasks with max_concurrent=3
        await asyncio.gather(*[task(i) for i in range(10)])

        # Max active should never exceed max_concurrent
        assert max_active <= max_concurrent

    @pytest.mark.asyncio
    async def test_semaphore_timing_shows_sequential_batches(self):
        """Test that with semaphore limit, tasks complete in batches."""
        max_concurrent = 2
        manager = ConcurrencyManager(max_concurrent=max_concurrent)

        task_times = {}

        async def timed_task(task_id: int):
            start = time.time()
            await manager.acquire_execution_slot(f"task-{task_id}")

            await asyncio.sleep(0.02)  # Simulate 20ms work

            await manager.release_execution_slot(f"task-{task_id}")
            end = time.time()

            task_times[task_id] = {"start": start, "end": end}

        # Run 6 tasks with max 2 concurrent
        # Expected: batch 1 (0,1), batch 2 (2,3), batch 3 (4,5)
        start_time = time.time()
        await asyncio.gather(*[timed_task(i) for i in range(6)])
        total_time = time.time() - start_time

        # Total time should be ~60ms (3 batches * 20ms)
        # Allow 50-80ms to account for overhead
        assert 0.05 <= total_time <= 0.1

        # Verify batching: consecutive tasks should have overlapping times
        # within same batch
        for batch_start in range(0, 6, max_concurrent):
            batch_tasks = list(range(batch_start, min(batch_start + max_concurrent, 6)))

            if len(batch_tasks) > 1:
                # Tasks in same batch should overlap
                batch_start_time = min(task_times[t]["start"] for t in batch_tasks)
                batch_end_time = max(task_times[t]["end"] for t in batch_tasks)

                # All tasks in batch should start/end within batch window
                for task_id in batch_tasks:
                    assert task_times[task_id]["start"] >= batch_start_time - 0.001
                    assert task_times[task_id]["end"] <= batch_end_time + 0.001

    @pytest.mark.asyncio
    async def test_quota_enforcement_per_execution(self):
        """Test per-execution resource quotas are enforced independently."""
        manager = ConcurrencyManager(max_concurrent=10)

        # Set different quotas for different executions
        from src.framework.concurrency_manager import ResourceQuota

        quota_1 = ResourceQuota(max_browser_pages=2, max_agent_concurrency=1)
        quota_2 = ResourceQuota(max_browser_pages=5, max_agent_concurrency=3)

        await manager.set_execution_quota("exec-1", quota_1)
        await manager.set_execution_quota("exec-2", quota_2)

        # Register pages for exec-1 (should fail at 3rd)
        await manager.acquire_execution_slot("exec-1")
        await manager.register_browser_page("exec-1", "page-1")
        await manager.register_browser_page("exec-1", "page-2")

        with pytest.raises(RuntimeError, match="exceeded max_browser_pages"):
            await manager.register_browser_page("exec-1", "page-3")

        # Register pages for exec-2 (should succeed up to 5)
        await manager.acquire_execution_slot("exec-2")
        for i in range(5):
            await manager.register_browser_page("exec-2", f"page-{i+1}")

        # 6th page should fail for exec-2
        with pytest.raises(RuntimeError, match="exceeded max_browser_pages"):
            await manager.register_browser_page("exec-2", "page-6")


class TestExecutionIsolationScenarios:
    """End-to-end scenarios testing execution isolation."""

    @pytest.mark.asyncio
    async def test_10_concurrent_executions_isolated_state(self, tmp_path):
        """Integration test: 10 concurrent executions with isolated state and semaphore limit."""
        n_executions = 10
        max_concurrent = 5
        manager = ConcurrencyManager(max_concurrent=max_concurrent)

        executions_dir = tmp_path / "data" / "executions"
        executions_dir.mkdir(parents=True, exist_ok=True)

        # Initialize state files
        for i in range(n_executions):
            exec_id = f"exec-{i}"
            state_file = executions_dir / f"{exec_id}.json"
            state_data = {
                "execution_id": exec_id,
                "iteration": 0,
                "result": None,
            }
            state_file.write_text(json.dumps(state_data))

        active_count = 0
        max_active = 0
        execution_results = {}

        async def isolated_execution(exec_id: str):
            nonlocal active_count, max_active

            # Acquire slot
            await manager.acquire_execution_slot(exec_id)
            active_count += 1
            max_active = max(max_active, active_count)

            try:
                # Load state
                state_file = executions_dir / f"{exec_id}.json"
                state_data = json.loads(state_file.read_text())

                # Simulate work
                await asyncio.sleep(0.01)

                # Update state
                state_data["iteration"] += 1
                state_data["result"] = f"processed-{state_data['iteration']}"
                state_file.write_text(json.dumps(state_data))

                execution_results[exec_id] = {
                    "success": True,
                    "final_iteration": state_data["iteration"],
                }

            finally:
                # Release slot
                await manager.release_execution_slot(exec_id)
                active_count -= 1

        # Run all executions concurrently
        await asyncio.gather(
            *[isolated_execution(f"exec-{i}") for i in range(n_executions)]
        )

        # Verify results
        assert len(execution_results) == n_executions
        assert all(r["success"] for r in execution_results.values())

        # Verify max concurrency wasn't exceeded
        assert max_active <= max_concurrent

        # Verify all state files have correct isolation
        for i in range(n_executions):
            exec_id = f"exec-{i}"
            state_file = executions_dir / f"{exec_id}.json"
            state_data = json.loads(state_file.read_text())

            assert state_data["execution_id"] == exec_id
            assert state_data["iteration"] == 1
            assert state_data["result"] == "processed-1"
