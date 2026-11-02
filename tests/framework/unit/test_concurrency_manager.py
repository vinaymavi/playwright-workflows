"""Unit Tests for ConcurrencyManager

Tests concurrency control, quota enforcement, and resource tracking
without browser or real async operations.
"""

import asyncio
import pytest

from src.framework.concurrency_manager import (
    ConcurrencyManager,
    ExecutionMetrics,
    QuotaType,
    ResourceQuota,
)


class TestResourceQuota:
    """Test ResourceQuota dataclass."""

    def test_default_quota_values(self):
        """Test default quota values."""
        quota = ResourceQuota()

        assert quota.max_browser_pages == 10
        assert quota.max_agent_concurrency == 2
        assert quota.max_memory_mb == 512
        assert quota.max_timeout_seconds == 3600

    def test_custom_quota_values(self):
        """Test custom quota initialization."""
        quota = ResourceQuota(
            max_browser_pages=5,
            max_agent_concurrency=1,
            max_memory_mb=256,
            max_timeout_seconds=1800,
        )

        assert quota.max_browser_pages == 5
        assert quota.max_agent_concurrency == 1
        assert quota.max_memory_mb == 256
        assert quota.max_timeout_seconds == 1800

    def test_quota_to_dict(self):
        """Test quota serialization to dict."""
        quota = ResourceQuota(max_browser_pages=5, max_agent_concurrency=1)
        quota_dict = quota.to_dict()

        assert quota_dict[QuotaType.MAX_BROWSER_PAGES.value] == 5
        assert quota_dict[QuotaType.MAX_AGENT_CONCURRENCY.value] == 1
        assert quota_dict[QuotaType.MAX_MEMORY_MB.value] == 512
        assert quota_dict[QuotaType.MAX_TIMEOUT_SECONDS.value] == 3600

    def test_quota_from_dict(self):
        """Test quota deserialization from dict."""
        quota_dict = {
            QuotaType.MAX_BROWSER_PAGES.value: 8,
            QuotaType.MAX_AGENT_CONCURRENCY.value: 3,
            QuotaType.MAX_MEMORY_MB.value: 1024,
            QuotaType.MAX_TIMEOUT_SECONDS.value: 7200,
        }

        quota = ResourceQuota.from_dict(quota_dict)

        assert quota.max_browser_pages == 8
        assert quota.max_agent_concurrency == 3
        assert quota.max_memory_mb == 1024
        assert quota.max_timeout_seconds == 7200


class TestExecutionMetrics:
    """Test ExecutionMetrics dataclass."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = ExecutionMetrics(execution_id="test-exec-1")

        assert metrics.execution_id == "test-exec-1"
        assert metrics.current_browser_pages == 0
        assert metrics.current_agent_tasks == 0
        assert metrics.current_memory_mb == 0
        assert metrics.start_time == 0.0
        assert metrics.peak_memory_mb == 0

    def test_metrics_elapsed_seconds_with_start_time(self):
        """Test elapsed time calculation."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            current_time = loop.time()
            metrics = ExecutionMetrics(
                execution_id="test-exec-1",
                start_time=current_time - 10.0,  # Started 10 seconds ago
            )

            elapsed = metrics.elapsed_seconds
            assert 9.0 <= elapsed <= 11.0  # Allow small timing variation
        finally:
            loop.close()

    def test_metrics_elapsed_seconds_without_start_time(self):
        """Test elapsed time when not started."""
        metrics = ExecutionMetrics(execution_id="test-exec-1", start_time=0.0)

        assert metrics.elapsed_seconds == 0.0


class TestConcurrencyManagerBasics:
    """Test basic ConcurrencyManager functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test manager initialization."""
        manager = ConcurrencyManager(max_concurrent=5)

        assert manager.max_concurrent == 5
        assert isinstance(manager.semaphore, asyncio.Semaphore)
        assert await manager.get_active_execution_count() == 0
        assert await manager.get_available_slots() == 5

    @pytest.mark.asyncio
    async def test_custom_default_quota(self):
        """Test initialization with custom default quota."""
        custom_quota = ResourceQuota(max_browser_pages=20, max_agent_concurrency=5)
        manager = ConcurrencyManager(max_concurrent=5, default_quota=custom_quota)

        assert manager.default_quota.max_browser_pages == 20
        assert manager.default_quota.max_agent_concurrency == 5


class TestExecutionSlotManagement:
    """Test execution slot acquisition and release."""

    @pytest.mark.asyncio
    async def test_acquire_execution_slot(self):
        """Test acquiring an execution slot."""
        manager = ConcurrencyManager(max_concurrent=3)

        await manager.acquire_execution_slot("exec-1")

        assert await manager.get_active_execution_count() == 1
        assert await manager.get_available_slots() == 2

    @pytest.mark.asyncio
    async def test_acquire_multiple_slots(self):
        """Test acquiring multiple execution slots."""
        manager = ConcurrencyManager(max_concurrent=3)

        await manager.acquire_execution_slot("exec-1")
        await manager.acquire_execution_slot("exec-2")
        await manager.acquire_execution_slot("exec-3")

        assert await manager.get_active_execution_count() == 3
        assert await manager.get_available_slots() == 0

    @pytest.mark.asyncio
    async def test_acquire_slot_blocks_when_full(self):
        """Test that slot acquisition blocks when at max capacity."""
        manager = ConcurrencyManager(max_concurrent=1)

        await manager.acquire_execution_slot("exec-1")

        # Try to acquire second slot (should block indefinitely or timeout)
        task = asyncio.create_task(manager.acquire_execution_slot("exec-2"))

        # Give it a moment to attempt acquisition
        await asyncio.sleep(0.1)

        # Task should still be pending
        assert not task.done()

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_release_execution_slot(self):
        """Test releasing an execution slot."""
        manager = ConcurrencyManager(max_concurrent=3)

        await manager.acquire_execution_slot("exec-1")
        await manager.release_execution_slot("exec-1")

        assert await manager.get_active_execution_count() == 0
        assert await manager.get_available_slots() == 3

    @pytest.mark.asyncio
    async def test_release_unknown_execution(self):
        """Test releasing slot for unknown execution (no-op)."""
        manager = ConcurrencyManager(max_concurrent=3)

        # Should not raise
        await manager.release_execution_slot("unknown-exec")

        assert await manager.get_active_execution_count() == 0

    @pytest.mark.asyncio
    async def test_duplicate_slot_acquisition(self):
        """Test that duplicate slot acquisition raises error."""
        manager = ConcurrencyManager(max_concurrent=3)

        await manager.acquire_execution_slot("exec-1")

        with pytest.raises(RuntimeError, match="already has a slot"):
            await manager.acquire_execution_slot("exec-1")


class TestBrowserPageQuota:
    """Test browser page quota enforcement."""

    @pytest.mark.asyncio
    async def test_register_browser_page(self):
        """Test registering a browser page."""
        manager = ConcurrencyManager(max_concurrent=5)
        await manager.acquire_execution_slot("exec-1")

        await manager.register_browser_page("exec-1", "page-1")

        metrics = await manager.get_execution_metrics("exec-1")
        assert metrics.current_browser_pages == 1

    @pytest.mark.asyncio
    async def test_register_multiple_pages(self):
        """Test registering multiple browser pages."""
        manager = ConcurrencyManager(max_concurrent=5)
        await manager.acquire_execution_slot("exec-1")

        for i in range(5):
            await manager.register_browser_page("exec-1", f"page-{i}")

        metrics = await manager.get_execution_metrics("exec-1")
        assert metrics.current_browser_pages == 5

    @pytest.mark.asyncio
    async def test_browser_page_quota_exceeded(self):
        """Test that exceeding browser page quota raises error."""
        custom_quota = ResourceQuota(max_browser_pages=2)
        manager = ConcurrencyManager(max_concurrent=5, default_quota=custom_quota)
        await manager.acquire_execution_slot("exec-1")

        await manager.register_browser_page("exec-1", "page-1")
        await manager.register_browser_page("exec-1", "page-2")

        with pytest.raises(RuntimeError, match="exceeded max_browser_pages"):
            await manager.register_browser_page("exec-1", "page-3")

    @pytest.mark.asyncio
    async def test_unregister_browser_page(self):
        """Test unregistering a browser page."""
        manager = ConcurrencyManager(max_concurrent=5)
        await manager.acquire_execution_slot("exec-1")

        await manager.register_browser_page("exec-1", "page-1")
        await manager.register_browser_page("exec-1", "page-2")
        await manager.unregister_browser_page("exec-1", "page-1")

        metrics = await manager.get_execution_metrics("exec-1")
        assert metrics.current_browser_pages == 1

    @pytest.mark.asyncio
    async def test_unregister_unknown_execution(self):
        """Test unregistering page for unknown execution (no-op)."""
        manager = ConcurrencyManager(max_concurrent=5)

        # Should not raise
        await manager.unregister_browser_page("unknown-exec", "page-1")


class TestAgentSlotManagement:
    """Test agent task quota enforcement."""

    @pytest.mark.asyncio
    async def test_acquire_agent_slot(self):
        """Test acquiring an agent slot."""
        manager = ConcurrencyManager(max_concurrent=5)
        await manager.acquire_execution_slot("exec-1")

        await manager.acquire_agent_slot("exec-1")

        metrics = await manager.get_execution_metrics("exec-1")
        assert metrics.current_agent_tasks == 1

    @pytest.mark.asyncio
    async def test_acquire_multiple_agent_slots(self):
        """Test acquiring multiple agent slots."""
        manager = ConcurrencyManager(max_concurrent=5)
        await manager.acquire_execution_slot("exec-1")

        await manager.acquire_agent_slot("exec-1")
        await manager.acquire_agent_slot("exec-1")

        metrics = await manager.get_execution_metrics("exec-1")
        assert metrics.current_agent_tasks == 2

    @pytest.mark.asyncio
    async def test_agent_slot_quota_exceeded(self):
        """Test that exceeding agent slot quota raises error."""
        custom_quota = ResourceQuota(max_agent_concurrency=1)
        manager = ConcurrencyManager(max_concurrent=5, default_quota=custom_quota)
        await manager.acquire_execution_slot("exec-1")

        await manager.acquire_agent_slot("exec-1")

        with pytest.raises(RuntimeError, match="exceeded max_agent_concurrency"):
            await manager.acquire_agent_slot("exec-1")

    @pytest.mark.asyncio
    async def test_release_agent_slot(self):
        """Test releasing agent slots."""
        manager = ConcurrencyManager(max_concurrent=5)
        await manager.acquire_execution_slot("exec-1")

        await manager.acquire_agent_slot("exec-1")
        await manager.acquire_agent_slot("exec-1")
        await manager.release_agent_slot("exec-1")

        metrics = await manager.get_execution_metrics("exec-1")
        assert metrics.current_agent_tasks == 1


class TestCustomQuotas:
    """Test custom quota management per execution."""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_set_execution_quota(self):
        """Test setting custom quota for execution."""
        manager = ConcurrencyManager(max_concurrent=5)
        await manager.acquire_execution_slot("exec-1")

        custom_quota = ResourceQuota(
            max_browser_pages=20,
            max_agent_concurrency=5,
        )
        await manager.set_execution_quota("exec-1", custom_quota)

        # Register 15 pages (should not exceed new quota of 20)
        for i in range(15):
            await manager.register_browser_page("exec-1", f"page-{i}")

        metrics = await manager.get_execution_metrics("exec-1")
        assert metrics.current_browser_pages == 15

    @pytest.mark.asyncio
    async def test_quota_enforcement_per_execution(self):
        """Test that quotas are independent per execution."""
        custom_quota1 = ResourceQuota(max_browser_pages=5)
        custom_quota2 = ResourceQuota(max_browser_pages=10)

        manager = ConcurrencyManager(max_concurrent=10, default_quota=custom_quota1)
        await manager.acquire_execution_slot("exec-1")
        await manager.acquire_execution_slot("exec-2")

        # exec-2 has custom higher quota
        await manager.set_execution_quota("exec-2", custom_quota2)

        # Register pages for both executions
        for i in range(5):
            await manager.register_browser_page("exec-1", f"exec1-page-{i}")
            await manager.register_browser_page("exec-2", f"exec2-page-{i}")

        # Try to register 6th page for exec-1 (should fail)
        with pytest.raises(RuntimeError):
            await manager.register_browser_page("exec-1", "exec1-page-5")

        # exec-2 should allow more pages
        for i in range(5, 10):
            await manager.register_browser_page("exec-2", f"exec2-page-{i}")

        metrics1 = await manager.get_execution_metrics("exec-1")
        metrics2 = await manager.get_execution_metrics("exec-2")

        assert metrics1.current_browser_pages == 5
        assert metrics2.current_browser_pages == 10


class TestMetricsAndTimeouts:
    """Test metrics collection and timeout enforcement."""

    @pytest.mark.asyncio
    async def test_get_execution_metrics(self):
        """Test retrieving execution metrics."""
        manager = ConcurrencyManager(max_concurrent=5)
        await manager.acquire_execution_slot("exec-1")

        metrics = await manager.get_execution_metrics("exec-1")

        assert metrics is not None
        assert metrics.execution_id == "exec-1"
        assert metrics.current_browser_pages == 0
        assert metrics.current_agent_tasks == 0

    @pytest.mark.asyncio
    async def test_get_unknown_metrics(self):
        """Test retrieving metrics for unknown execution."""
        manager = ConcurrencyManager(max_concurrent=5)

        metrics = await manager.get_execution_metrics("unknown-exec")

        assert metrics is None

    @pytest.mark.asyncio
    async def test_get_all_metrics(self):
        """Test retrieving all metrics."""
        manager = ConcurrencyManager(max_concurrent=5)

        await manager.acquire_execution_slot("exec-1")
        await manager.acquire_execution_slot("exec-2")

        all_metrics = await manager.get_all_metrics()

        assert len(all_metrics) == 2
        assert "exec-1" in all_metrics
        assert "exec-2" in all_metrics

    @pytest.mark.asyncio
    async def test_timeout_not_exceeded(self):
        """Test timeout check when not exceeded."""
        custom_quota = ResourceQuota(max_timeout_seconds=100)
        manager = ConcurrencyManager(max_concurrent=5, default_quota=custom_quota)

        await manager.acquire_execution_slot("exec-1")

        # Should not exceed immediately
        exceeded = await manager.enforce_timeout("exec-1")

        assert not exceeded

    @pytest.mark.asyncio
    async def test_timeout_exceeded(self):
        """Test timeout check when exceeded."""
        loop = asyncio.get_event_loop()
        custom_quota = ResourceQuota(max_timeout_seconds=1)  # 1 second timeout
        manager = ConcurrencyManager(max_concurrent=5, default_quota=custom_quota)

        # Create metrics with start time in the past
        start_time = loop.time() - 2.0  # Started 2 seconds ago
        await manager.acquire_execution_slot("exec-1")

        # Manually set start time to trigger timeout
        metrics = await manager.get_execution_metrics("exec-1")
        metrics.start_time = start_time

        exceeded = await manager.enforce_timeout("exec-1")

        assert exceeded

    @pytest.mark.asyncio
    async def test_timeout_unknown_execution(self):
        """Test timeout check for unknown execution."""
        manager = ConcurrencyManager(max_concurrent=5)

        exceeded = await manager.enforce_timeout("unknown-exec")

        assert not exceeded


class TestConcurrentExecutions:
    """Test concurrent execution scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_slot_acquisition_respects_limit(self):
        """Test that concurrent acquisitions respect max_concurrent limit."""
        manager = ConcurrencyManager(max_concurrent=3)

        # Acquire 3 slots without waiting
        tasks = [
            asyncio.create_task(manager.acquire_execution_slot(f"exec-{i}"))
            for i in range(3)
        ]

        # Wait for all to acquire
        await asyncio.gather(*tasks)

        assert await manager.get_active_execution_count() == 3
        assert await manager.get_available_slots() == 0

    @pytest.mark.asyncio
    async def test_concurrent_slot_release_frees_slots(self):
        """Test that releasing slots frees them for waiting tasks."""
        manager = ConcurrencyManager(max_concurrent=2)

        # Acquire 2 slots
        await manager.acquire_execution_slot("exec-1")
        await manager.acquire_execution_slot("exec-2")

        # Release one
        await manager.release_execution_slot("exec-1")

        assert await manager.get_available_slots() == 1
