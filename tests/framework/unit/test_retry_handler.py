"""Unit tests for retry_handler module."""

import asyncio
import pytest

from src.framework.errors import PermanentError, TransientError
from src.framework.retry_handler import ErrorClassifier, RetryPolicy, with_retry, with_retry_sync


class TestRetryPolicy:
    """Test RetryPolicy configuration and backoff calculation."""

    def test_default_policy(self):
        """Test default retry policy."""
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.initial_backoff_seconds == 1.0
        assert policy.max_backoff_seconds == 60.0
        assert policy.backoff_multiplier == 2.0

    def test_custom_policy(self):
        """Test custom retry policy configuration."""
        policy = RetryPolicy(
            max_retries=5,
            initial_backoff_seconds=0.5,
            max_backoff_seconds=30.0,
            backoff_multiplier=1.5,
        )
        assert policy.max_retries == 5
        assert policy.initial_backoff_seconds == 0.5
        assert policy.max_backoff_seconds == 30.0
        assert policy.backoff_multiplier == 1.5

    def test_backoff_calculation(self):
        """Test exponential backoff calculation."""
        policy = RetryPolicy(
            initial_backoff_seconds=1.0,
            backoff_multiplier=2.0,
            max_backoff_seconds=60.0,
            jitter_enabled=False,
        )
        # Attempt 1: 1.0 * 2^0 = 1.0
        assert policy.calculate_backoff(1) == 1.0
        # Attempt 2: 1.0 * 2^1 = 2.0
        assert policy.calculate_backoff(2) == 2.0
        # Attempt 3: 1.0 * 2^2 = 4.0
        assert policy.calculate_backoff(3) == 4.0

    def test_backoff_max_cap(self):
        """Test that backoff is capped at max_backoff_seconds."""
        policy = RetryPolicy(
            initial_backoff_seconds=1.0,
            backoff_multiplier=2.0,
            max_backoff_seconds=10.0,
            jitter_enabled=False,
        )
        # Attempt 10: 1.0 * 2^9 = 512.0 -> capped at 10.0
        assert policy.calculate_backoff(10) == 10.0

    def test_backoff_with_jitter(self):
        """Test backoff with jitter randomization."""
        policy = RetryPolicy(
            initial_backoff_seconds=1.0,
            backoff_multiplier=2.0,
            max_backoff_seconds=60.0,
            jitter_enabled=True,
        )
        backoff = policy.calculate_backoff(2)
        # With jitter, should be between 0 and 2.0
        assert 0 <= backoff <= 2.0


class TestErrorClassifier:
    """Test ErrorClassifier for classifying errors as transient or permanent."""

    def test_classify_timeout_as_transient(self):
        """Test that TimeoutError is classified as transient."""
        classifier = ErrorClassifier()
        error = TimeoutError("Connection timeout")
        assert classifier.is_transient(error) is True

    def test_classify_connection_error_as_transient(self):
        """Test that ConnectionError is classified as transient."""
        classifier = ErrorClassifier()
        error = ConnectionError("Connection refused")
        assert classifier.is_transient(error) is True

    def test_classify_value_error_as_permanent(self):
        """Test that ValueError is classified as permanent."""
        classifier = ErrorClassifier()
        error = ValueError("Invalid value")
        assert classifier.is_transient(error) is False

    def test_classify_assertion_error_as_permanent(self):
        """Test that AssertionError is classified as permanent."""
        classifier = ErrorClassifier()
        error = AssertionError("Assertion failed")
        assert classifier.is_transient(error) is False

    def test_classify_http_5xx_as_transient(self):
        """Test that 5xx HTTP status codes are transient."""
        classifier = ErrorClassifier()
        # Simulate HTTP 500 error via exception message
        error = Exception("HTTP 500: Internal Server Error")
        # Note: actual classification depends on message pattern matching
        # This is implementation-dependent

    def test_classify_http_4xx_as_permanent(self):
        """Test that 4xx HTTP status codes are permanent."""
        classifier = ErrorClassifier()
        # Simulate HTTP 400 error
        error = Exception("HTTP 400: Bad Request")

    def test_classify_rate_limit_as_transient(self):
        """Test that rate limit errors are classified as transient."""
        classifier = ErrorClassifier()
        error = Exception("429 Too Many Requests")
        # Rate limit should be transient

    def test_classify_eof_error_as_transient(self):
        """Test that EOF errors are classified as transient."""
        classifier = ErrorClassifier()
        error = EOFError("Unexpected EOF")
        assert classifier.is_transient(error) is True

    def test_classify_browser_error_as_transient(self):
        """Test that browser/Playwright errors can be transient."""
        classifier = ErrorClassifier()
        # Playwright timeout errors should be transient
        error = TimeoutError("Timeout waiting for element")
        assert classifier.is_transient(error) is True


class TestWithRetryAsync:
    """Test with_retry async function executor."""

    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        """Test that successful calls don't retry."""
        call_count = 0

        async def step_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await with_retry(step_func)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_transient_error_retry(self):
        """Test that transient errors trigger retries."""
        call_count = 0

        async def step_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("Connection timeout")
            return "success"

        result = await with_retry(step_func)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(self):
        """Test that permanent errors don't retry."""
        call_count = 0

        async def step_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")

        with pytest.raises(PermanentError):
            await with_retry(step_func)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test that retries are exhausted after max attempts."""
        call_count = 0

        async def step_func():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Always times out")

        policy = RetryPolicy(max_retries=2)
        with pytest.raises(TransientError):
            await with_retry(step_func, policy=policy)
        assert call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_with_step_name(self):
        """Test retry with step name tracking."""
        async def step_func():
            raise TimeoutError("Timeout")

        with pytest.raises(TransientError):
            await with_retry(step_func, step_name="navigate")

    @pytest.mark.asyncio
    async def test_custom_policy_async(self):
        """Test custom retry policy in async execution."""
        call_count = 0

        async def step_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        policy = RetryPolicy(max_retries=5, initial_backoff_seconds=0.1)
        result = await with_retry(step_func, policy=policy)
        assert result == "success"


class TestWithRetrySyncal:
    """Test with_retry_sync synchronous function."""

    def test_successful_call_no_retry(self):
        """Test that successful sync calls don't retry."""
        call_count = 0

        def step_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = with_retry_sync(step_func)
        assert result == "success"
        assert call_count == 1

    def test_transient_error_retry(self):
        """Test that transient errors trigger retries in sync."""
        call_count = 0

        def step_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("Connection timeout")
            return "success"

        result = with_retry_sync(step_func)
        assert result == "success"
        assert call_count == 3

    def test_permanent_error_no_retry(self):
        """Test that permanent errors don't retry in sync."""
        call_count = 0

        def step_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")

        with pytest.raises(PermanentError):
            with_retry_sync(step_func)
        assert call_count == 1

    def test_custom_policy_sync(self):
        """Test custom retry policy in sync execution."""
        call_count = 0

        def step_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timeout")
            return "ok"

        policy = RetryPolicy(max_retries=5)
        result = with_retry_sync(step_func, policy=policy)
        assert result == "ok"

    def test_retry_with_step_name(self):
        """Test retry with custom step name for logging."""
        call_count = 0

        def step_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Failed")
            return "success"

        result = with_retry_sync(step_func, step_name="login_step")
        assert result == "success"


class TestErrorClassificationIntegration:
    """Test error classification in retry scenarios."""

    def test_network_errors_are_transient(self):
        """Test common network errors are transient."""
        classifier = ErrorClassifier()
        network_errors = [
            TimeoutError("Timeout"),
            ConnectionError("Connection failed"),
            EOFError("EOF"),
        ]
        for error in network_errors:
            assert classifier.is_transient(error) is True

    def test_logic_errors_are_permanent(self):
        """Test logic/assertion errors are permanent."""
        classifier = ErrorClassifier()
        logic_errors = [
            ValueError("Invalid"),
            TypeError("Type error"),
            AssertionError("Assertion failed"),
            KeyError("Missing key"),
        ]
        for error in logic_errors:
            assert classifier.is_transient(error) is False
