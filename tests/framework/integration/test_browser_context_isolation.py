"""Integration tests for browser context pooling and isolation.

Tests N concurrent workflows with isolated contexts to verify:
- Context pool manages max concurrent contexts
- Each execution gets isolated context
- Contexts don't cross-contaminate state
- Pool cleanup works on exit
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.framework.session_manager import BrowserContextPool, SessionManager


class MockBrowserContext:
    """Mock browser context for testing without real browser."""

    def __init__(self, context_id: str, base_url: str = None):
        self.id = context_id
        self.base_url = base_url
        self.pages = []
        self.storage_state_data = {
            "cookies": [{"name": "test", "value": "value"}],
            "origins": [],
        }
        self.is_closed = False

    async def close(self):
        """Simulate closing context."""
        self.is_closed = True

    async def storage_state(self):
        """Return mock storage state."""
        return self.storage_state_data

    async def new_page(self):
        """Create mock page."""
        page = AsyncMock()
        self.pages.append(page)
        return page


class MockBrowser:
    """Mock browser for testing without real browser."""

    def __init__(self, max_contexts: int = 10):
        self.max_contexts = max_contexts
        self.created_contexts = 0
        self.contexts = {}

    async def new_context(self, base_url: str = None, **kwargs):
        """Create mock context."""
        if self.created_contexts >= self.max_contexts:
            raise RuntimeError("Max contexts exceeded")

        context = MockBrowserContext(f"ctx-{self.created_contexts}", base_url)
        self.contexts[context.id] = context
        self.created_contexts += 1
        return context


class TestBrowserContextPoolBasics:
    """Test basic pool initialization and metrics."""

    def test_pool_initialization(self):
        """Test pool initializes with correct settings."""
        pool = BrowserContextPool(max_concurrent=5)
        assert pool.max_concurrent == 5
        assert pool._browser is None
        assert len(pool._execution_to_context) == 0
        assert len(pool._available_contexts) == 0

    @pytest.mark.asyncio
    async def test_pool_initialize_with_browser(self):
        """Test initializing pool with browser instance."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()

        await pool.initialize(mock_browser)

        assert pool._browser is mock_browser

    @pytest.mark.asyncio
    async def test_get_pool_metrics_empty(self):
        """Test metrics for empty pool."""
        pool = BrowserContextPool(max_concurrent=5)
        metrics = await pool.get_pool_metrics()

        assert metrics["active_contexts"] == 0
        assert metrics["available_contexts"] == 0
        assert metrics["max_concurrent"] == 5
        assert metrics["total_contexts"] == 0


class TestContextAcquisitionAndRelease:
    """Test acquiring and releasing contexts from pool."""

    @pytest.mark.asyncio
    async def test_acquire_context_creates_new(self):
        """Test acquiring context creates new when under limit."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        context = await pool.acquire_context(
            "exec-1", base_url="https://example.com"
        )

        assert context is not None
        assert pool.get_context_for_execution("exec-1") is context
        metrics = await pool.get_pool_metrics()
        assert metrics["active_contexts"] == 1

    @pytest.mark.asyncio
    async def test_acquire_context_multiple_executions(self):
        """Test acquiring multiple contexts for different executions."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        contexts = []
        for i in range(3):
            context = await pool.acquire_context(f"exec-{i}")
            contexts.append(context)

        assert len(contexts) == 3
        assert all(c is not None for c in contexts)

        metrics = await pool.get_pool_metrics()
        assert metrics["active_contexts"] == 3

    @pytest.mark.asyncio
    async def test_acquire_duplicate_execution_raises_error(self):
        """Test acquiring context for same execution twice raises error."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        await pool.acquire_context("exec-1")

        with pytest.raises(RuntimeError, match="already has assigned context"):
            await pool.acquire_context("exec-1")

    @pytest.mark.asyncio
    async def test_acquire_at_max_capacity_raises_error(self):
        """Test acquiring context when at max capacity raises error."""
        pool = BrowserContextPool(max_concurrent=2)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        await pool.acquire_context("exec-1")
        await pool.acquire_context("exec-2")

        with pytest.raises(RuntimeError, match="at max capacity"):
            await pool.acquire_context("exec-3")

    @pytest.mark.asyncio
    async def test_release_context_returns_to_pool(self):
        """Test releasing context makes it available for reuse."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        context1 = await pool.acquire_context("exec-1")
        await pool.release_context("exec-1")

        metrics = await pool.get_pool_metrics()
        assert metrics["active_contexts"] == 0
        assert metrics["available_contexts"] == 1

        # Should be able to acquire now (reuses context1)
        context2 = await pool.acquire_context("exec-2")
        assert context2 is context1  # Reused same context

    @pytest.mark.asyncio
    async def test_release_unknown_execution_logs_warning(self):
        """Test releasing unknown execution doesn't error."""
        pool = BrowserContextPool(max_concurrent=5)
        await pool.initialize(MockBrowser())

        # Should not raise
        await pool.release_context("unknown-exec")

    @pytest.mark.asyncio
    async def test_get_context_for_execution_lookup(self):
        """Test getting context for execution (non-blocking lookup)."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        context = await pool.acquire_context("exec-1")

        # Lookup should work
        assert pool.get_context_for_execution("exec-1") is context

        # Unknown should return None
        assert pool.get_context_for_execution("unknown") is None


class TestConcurrentContextAccess:
    """Test concurrent access patterns to pool."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_acquisitions(self):
        """Test multiple concurrent execution acquisitions."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        # Acquire 5 contexts concurrently
        tasks = [pool.acquire_context(f"exec-{i}") for i in range(5)]
        contexts = await asyncio.gather(*tasks)

        assert len(contexts) == 5
        assert all(c is not None for c in contexts)
        metrics = await pool.get_pool_metrics()
        assert metrics["active_contexts"] == 5

    @pytest.mark.asyncio
    async def test_concurrent_acquire_and_release_cycle(self):
        """Test interleaved acquire/release operations."""
        pool = BrowserContextPool(max_concurrent=3)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        # Acquire 3 contexts
        ctx1 = await pool.acquire_context("exec-1")
        ctx2 = await pool.acquire_context("exec-2")
        ctx3 = await pool.acquire_context("exec-3")

        # At capacity, should fail
        with pytest.raises(RuntimeError):
            await pool.acquire_context("exec-4")

        # Release one
        await pool.release_context("exec-1")

        # Now should be able to acquire
        ctx4 = await pool.acquire_context("exec-4")
        assert ctx4 is not None

    @pytest.mark.asyncio
    async def test_rapid_sequential_release_acquire(self):
        """Test rapid release/acquire cycles reuses contexts efficiently."""
        pool = BrowserContextPool(max_concurrent=2)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        contexts_used = []

        for i in range(4):
            exec_id = f"exec-{i}"
            context = await pool.acquire_context(exec_id)
            contexts_used.append(context)
            await pool.release_context(exec_id)

        # With reuse-first strategy, only 1 context is created and reused for all 4
        unique_contexts = len(set(id(c) for c in contexts_used))
        assert unique_contexts == 1  # All reuse same context


class TestContextPoolCleanup:
    """Test cleanup and leak detection."""

    @pytest.mark.asyncio
    async def test_cleanup_closes_all_contexts(self):
        """Test cleanup closes all active and available contexts."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        # Create and release some contexts
        ctx1 = await pool.acquire_context("exec-1")
        ctx2 = await pool.acquire_context("exec-2")
        await pool.release_context("exec-1")

        # ctx1 in available, ctx2 in active
        assert len(pool._available_contexts) == 1

        await pool.cleanup()

        # All should be closed and cleared
        assert len(pool._execution_to_context) == 0
        assert len(pool._available_contexts) == 0
        assert ctx1.is_closed
        assert ctx2.is_closed

    @pytest.mark.asyncio
    async def test_cleanup_handles_close_errors(self):
        """Test cleanup handles errors closing contexts gracefully."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        context = await pool.acquire_context("exec-1")

        # Make close raise error
        async def failing_close():
            raise RuntimeError("Close failed")

        context.close = failing_close

        # Should not raise, just log error
        await pool.cleanup()

    @pytest.mark.asyncio
    async def test_metrics_show_active_and_available(self):
        """Test metrics correctly count active vs available contexts."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        # Acquire 3, release 1
        await pool.acquire_context("exec-1")
        await pool.acquire_context("exec-2")
        ctx3 = await pool.acquire_context("exec-3")
        await pool.release_context("exec-1")

        metrics = await pool.get_pool_metrics()

        assert metrics["active_contexts"] == 2  # exec-2, exec-3
        assert metrics["available_contexts"] == 1  # released ctx1


class TestBrowserContextPoolIntegration:
    """Integration tests with SessionManager."""

    @pytest.mark.asyncio
    async def test_pool_with_session_manager_save(self, tmp_path):
        """Test pool integration with SessionManager for saving state."""
        pool = BrowserContextPool(max_concurrent=5)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        # Create session manager
        session_mgr = SessionManager(execution_id="exec-1", session_dir=tmp_path)

        # Acquire context and save session through pool
        context = await pool.acquire_context("exec-1")
        session_mgr.browser_context = context

        await pool.release_context(
            "exec-1",
            save_session=True,
            session_manager=session_mgr,
        )

        # Session should be saved (session_mgr._save_session_data called)
        assert session_mgr.session_file.exists()

    @pytest.mark.asyncio
    async def test_n_concurrent_isolated_workflows(self):
        """Test N concurrent workflows each with isolated context."""
        n_workflows = 5
        pool = BrowserContextPool(max_concurrent=n_workflows)
        mock_browser = MockBrowser()
        await pool.initialize(mock_browser)

        # Simulate N concurrent workflows
        async def workflow(exec_id: str):
            context = await pool.acquire_context(exec_id)
            # Simulate work
            await asyncio.sleep(0.01)
            await pool.release_context(exec_id)
            return context

        contexts = await asyncio.gather(
            *[workflow(f"exec-{i}") for i in range(n_workflows)]
        )

        # All should have completed
        assert len(contexts) == n_workflows
        assert all(c is not None for c in contexts)

        # Pool should be empty
        metrics = await pool.get_pool_metrics()
        assert metrics["active_contexts"] == 0
        assert metrics["available_contexts"] == n_workflows
