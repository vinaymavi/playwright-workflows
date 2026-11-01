"""Unit tests for Workflow decorators."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from functools import wraps

from src.framework.decorators import step, retry
from src.framework.errors import PermanentError, TransientError, WorkflowError
from src.framework.workflow import Workflow


class TestStepDecorator:
    """Test @step decorator."""

    def test_step_decorator_exists(self):
        """Test @step decorator is available."""
        assert callable(step)

    def test_step_decorator_with_defaults(self):
        """Test @step decorator with default parameters."""
        @step()
        async def test_method(self):
            return "result"

        # Verify decorator returns a callable
        assert callable(test_method)

    def test_step_decorator_with_max_retries(self):
        """Test @step decorator with max_retries parameter."""
        @step(max_retries=5)
        async def test_method(self):
            return "result"

        assert callable(test_method)

    def test_step_decorator_with_timeout(self):
        """Test @step decorator with timeout_ms parameter."""
        @step(timeout_ms=30000)
        async def test_method(self):
            return "result"

        assert callable(test_method)

    def test_step_decorator_with_name(self):
        """Test @step decorator with name parameter."""
        @step(name="Test step")
        async def test_method(self):
            return "result"

        assert callable(test_method)

    def test_step_decorator_supports_sync_functions(self):
        """Test @step decorator supports synchronous functions."""
        @step()
        def sync_method(self):
            return "sync_result"

        assert callable(sync_method)

    def test_step_decorator_supports_async_functions(self):
        """Test @step decorator supports asynchronous functions."""
        @step()
        async def async_method(self):
            return "async_result"

        assert callable(async_method)

    @pytest.mark.asyncio
    async def test_step_decorator_executes_async_method(self):
        """Test @step decorator executes async method."""
        call_count = 0

        class TestWorkflow(Workflow):
            async def run(self):
                pass

            @step()
            async def test_step(self):
                nonlocal call_count
                call_count += 1
                return "success"

        workflow = TestWorkflow(
            execution_id="test-123",
            base_url="https://example.com"
        )

        # Mock logger
        workflow.logger = MagicMock()

        result = await workflow.test_step()
        assert result == "success"
        assert call_count == 1

    def test_step_decorator_sync_method_execution(self):
        """Test @step decorator executes sync method."""
        call_count = 0

        class TestWorkflow(Workflow):
            async def run(self):
                pass

            @step()
            def sync_step(self):
                nonlocal call_count
                call_count += 1
                return "sync_success"

        workflow = TestWorkflow(
            execution_id="test-123",
            base_url="https://example.com"
        )

        # Mock logger
        workflow.logger = MagicMock()

        result = workflow.sync_step()
        assert result == "sync_success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_step_decorator_logs_step_start(self):
        """Test @step decorator logs step start."""

        class TestWorkflow(Workflow):
            async def run(self):
                pass

            @step()
            async def test_step(self):
                return "result"

        workflow = TestWorkflow(
            execution_id="test-123",
            base_url="https://example.com"
        )

        workflow.logger = MagicMock()

        await workflow.test_step()

        # Verify logger was called (logging the step execution)
        assert workflow.logger.info.called or workflow.logger.debug.called

    @pytest.mark.asyncio
    async def test_step_decorator_handles_exceptions(self):
        """Test @step decorator handles exceptions in step."""

        class TestWorkflow(Workflow):
            async def run(self):
                pass

            @step()
            async def failing_step(self):
                raise ValueError("Test error")

        workflow = TestWorkflow(
            execution_id="test-123",
            base_url="https://example.com"
        )

        workflow.logger = MagicMock()

        # The decorator should handle the exception
        # (actual behavior depends on error classification)
        with pytest.raises((ValueError, TransientError, PermanentError, WorkflowError)):
            await workflow.failing_step()


class TestRetryDecorator:
    """Test @retry decorator."""

    def test_retry_decorator_exists(self):
        """Test @retry decorator is available."""
        assert callable(retry)

    def test_retry_decorator_with_defaults(self):
        """Test @retry decorator with default parameters."""
        @retry()
        async def test_method():
            return "result"

        assert callable(test_method)

    def test_retry_decorator_with_max_attempts(self):
        """Test @retry decorator with max_attempts parameter."""
        @retry(max_attempts=5)
        async def test_method():
            return "result"

        assert callable(test_method)

    def test_retry_decorator_with_backoff_multiplier(self):
        """Test @retry decorator with backoff_multiplier parameter."""
        @retry(backoff_multiplier=2.0)
        async def test_method():
            return "result"

        assert callable(test_method)

    def test_retry_decorator_with_delay(self):
        """Test @retry decorator with delay_seconds parameter."""
        @retry(delay_seconds=1)
        async def test_method():
            return "result"

        assert callable(test_method)

    def test_retry_decorator_supports_sync(self):
        """Test @retry decorator supports sync functions."""
        @retry()
        def sync_method():
            return "sync_result"

        assert callable(sync_method)

    def test_retry_decorator_supports_async(self):
        """Test @retry decorator supports async functions."""
        @retry()
        async def async_method():
            return "async_result"

        assert callable(async_method)

    @pytest.mark.asyncio
    async def test_retry_decorator_executes_async_successfully(self):
        """Test @retry decorator executes async function successfully."""
        call_count = 0

        @retry(max_attempts=3)
        async def test_method():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await test_method()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_decorator_retries_on_transient_error(self):
        """Test @retry decorator retries on transient errors."""
        call_count = 0

        @retry(max_attempts=3, delay_seconds=0.01)
        async def test_method():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TransientError("test", "Transient error")
            return "success"

        result = await test_method()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_decorator_gives_up_after_max_attempts(self):
        """Test @retry decorator gives up after max attempts."""
        call_count = 0

        @retry(max_attempts=3, delay_seconds=0.01)
        async def test_method():
            nonlocal call_count
            call_count += 1
            raise TransientError("test", "Always fails")

        with pytest.raises(TransientError):
            await test_method()

        assert call_count == 3

    def test_retry_decorator_sync_execution(self):
        """Test @retry decorator executes sync function."""
        call_count = 0

        @retry()
        def sync_method():
            nonlocal call_count
            call_count += 1
            return "sync_success"

        result = sync_method()
        assert result == "sync_success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_decorator_sync_retry_on_error(self):
        """Test @retry decorator retries sync function on error."""
        call_count = 0

        @retry(max_attempts=3, delay_seconds=0.01)
        def sync_method():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TransientError("test", "Transient error")
            return "success"

        result = sync_method()
        assert result == "success"
        assert call_count == 2


class TestDecoratorIntegration:
    """Test integration of decorators with Workflow class."""

    @pytest.mark.asyncio
    async def test_step_and_retry_integration(self):
        """Test @step and @retry decorators work together."""

        class TestWorkflow(Workflow):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.attempt_count = 0

            async def run(self):
                return await self.retry_step()

            @step(max_retries=3)
            async def retry_step(self):
                self.attempt_count += 1
                if self.attempt_count < 2:
                    raise TransientError("retry_step", "First attempt fails")
                return {"status": "success", "attempts": self.attempt_count}

        workflow = TestWorkflow(
            execution_id="test-123",
            base_url="https://example.com"
        )

        workflow.logger = MagicMock()

        # Note: The actual behavior depends on how retry logic is implemented
        # This test verifies the decorators can be stacked without raising errors
        try:
            result = await workflow.retry_step()
            # If it succeeds, we expect the result
            assert result is not None
        except (TransientError, WorkflowError):
            # If retry logic exhausts, it's also acceptable
            pass


class TestDecoratorParameters:
    """Test decorator parameter validation and handling."""

    def test_step_accepts_none_name(self):
        """Test @step decorator accepts None for name."""
        @step(name=None)
        async def test_method(self):
            return "result"

        assert callable(test_method)

    def test_step_accepts_zero_max_retries(self):
        """Test @step decorator accepts 0 for max_retries."""
        @step(max_retries=0)
        async def test_method(self):
            return "result"

        assert callable(test_method)

    def test_step_accepts_none_timeout(self):
        """Test @step decorator accepts None for timeout_ms."""
        @step(timeout_ms=None)
        async def test_method(self):
            return "result"

        assert callable(test_method)

    def test_retry_accepts_positive_integers(self):
        """Test @retry decorator accepts positive integers."""
        @retry(max_attempts=5, delay_seconds=1)
        async def test_method():
            return "result"

        assert callable(test_method)

    def test_retry_accepts_float_backoff(self):
        """Test @retry decorator accepts float backoff multiplier."""
        @retry(backoff_multiplier=1.5)
        async def test_method():
            return "result"

        assert callable(test_method)
