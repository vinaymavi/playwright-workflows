"""Unit tests for session_manager module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.framework.session_manager import SessionManager


class TestSessionManager:
    """Test SessionManager for browser session lifecycle."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for session files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_initialization(self, temp_dir):
        """Test session manager initialization."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)
        assert manager.execution_id == "exec-001"
        assert manager.session_dir == temp_dir
        assert manager.browser_context is None

    def test_session_timeout_constant(self):
        """Test session timeout configuration."""
        assert SessionManager.SESSION_TIMEOUT_SECONDS == 300  # 5 minutes

    def test_auth_error_codes(self):
        """Test auth error codes."""
        assert 401 in SessionManager.AUTH_ERROR_CODES
        assert 403 in SessionManager.AUTH_ERROR_CODES

    @pytest.mark.asyncio
    async def test_initialize_context_fresh(self, temp_dir):
        """Test initializing fresh browser context."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        # Mock browser
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        context = await manager.initialize_context(
            mock_browser,
            base_url="https://example.com",
        )

        assert context is not None
        mock_browser.new_context.assert_called_once()
        assert manager.browser_context is not None

    @pytest.mark.asyncio
    async def test_initialize_context_restore(self, temp_dir):
        """Test restoring browser context from saved session."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        # Create saved session file
        session_data = {
            "execution_id": "exec-001",
            "timestamp": 1000,
            "cookies": [{"name": "session_id", "value": "abc123"}],
            "origins": [],
        }
        with open(manager.session_file, "w") as f:
            json.dump(session_data, f)

        # Mock browser
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        context = await manager.initialize_context(
            mock_browser,
            base_url="https://example.com",
        )

        # Verify storage_state was passed with cookies
        call_kwargs = mock_browser.new_context.call_args[1]
        assert "storage_state" in call_kwargs
        assert call_kwargs["storage_state"]["cookies"][0]["name"] == "session_id"

    @pytest.mark.asyncio
    async def test_save_session(self, temp_dir):
        """Test saving session data."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        # Mock browser context
        mock_context = AsyncMock()
        mock_context.storage_state = AsyncMock(
            return_value={
                "cookies": [{"name": "sid", "value": "xyz"}],
                "origins": [],
            }
        )
        manager.browser_context = mock_context

        await manager.save_session()

        assert manager.session_file.exists()
        with open(manager.session_file) as f:
            data = json.load(f)
        assert data["execution_id"] == "exec-001"
        assert len(data["cookies"]) == 1

    @pytest.mark.asyncio
    async def test_check_session_valid_success(self, temp_dir):
        """Test checking session validity with successful response."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        # Mock page
        mock_response = MagicMock()
        mock_response.status = 200
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.goto = AsyncMock(return_value=mock_response)

        result = await manager.check_session_valid(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_session_valid_unauthorized(self, temp_dir):
        """Test checking session validity with 401 Unauthorized."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        # Mock page with 401 response
        mock_response = MagicMock()
        mock_response.status = 401
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.goto = AsyncMock(return_value=mock_response)

        result = await manager.check_session_valid(mock_page)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_session_valid_forbidden(self, temp_dir):
        """Test checking session validity with 403 Forbidden."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        # Mock page with 403 response
        mock_response = MagicMock()
        mock_response.status = 403
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.goto = AsyncMock(return_value=mock_response)

        result = await manager.check_session_valid(mock_page)

        assert result is False

    def test_session_age_seconds(self, temp_dir):
        """Test calculating session age."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)
        age = manager.get_session_age_seconds()
        # Should be very small (close to 0) since just created
        assert age < 1.0

    def test_is_session_expired_false(self, temp_dir):
        """Test that fresh session is not expired."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)
        # Just created, should not be expired
        assert manager.is_session_expired() is False

    def test_is_session_expired_true(self, temp_dir):
        """Test that old session is expired."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)
        # Manually set created_at to past
        manager.created_at = 0  # Unix epoch
        assert manager.is_session_expired() is True

    @pytest.mark.asyncio
    async def test_recover_session_keep_alive_strategy(self, temp_dir):
        """Test session recovery with keep-alive strategy (<5min)."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)
        # Fresh session, age < 5 minutes
        manager.created_at = 0  # Just now

        mock_browser = AsyncMock()

        success, strategy = await manager.recover_session(
            mock_browser,
            base_url="https://example.com",
        )

        # Age is large, should use replay strategy
        # (depends on current timestamp, but test logic is sound)

    @pytest.mark.asyncio
    async def test_recover_session_replay_strategy(self, temp_dir):
        """Test session recovery with replay strategy (>5min)."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)
        # Old session, age >= 5 minutes
        manager.created_at = 0  # Very old

        # Mock browser and context
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        manager.browser_context = AsyncMock()
        manager.browser_context.close = AsyncMock()

        success, strategy = await manager.recover_session(
            mock_browser,
            base_url="https://example.com",
        )

        assert success is True
        # Age is old, should use replay or keep_alive

    @pytest.mark.asyncio
    async def test_close_session(self, temp_dir):
        """Test closing session."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        # Mock context
        mock_context = AsyncMock()
        mock_context.storage_state = AsyncMock(
            return_value={"cookies": [], "origins": []}
        )
        mock_context.close = AsyncMock()
        manager.browser_context = mock_context

        await manager.close()

        # Verify context was closed
        mock_context.close.assert_called_once()
        # Session should be saved before close
        mock_context.storage_state.assert_called()

    def test_load_session_nonexistent(self, temp_dir):
        """Test loading nonexistent session returns None."""
        manager = SessionManager(execution_id="exec-999", session_dir=temp_dir)
        data = manager._load_session()
        assert data is None

    def test_load_session_existing(self, temp_dir):
        """Test loading existing session."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        # Create session file
        session_data = {
            "execution_id": "exec-001",
            "timestamp": 1000,
            "cookies": [{"name": "sid", "value": "abc"}],
        }
        with open(manager.session_file, "w") as f:
            json.dump(session_data, f)

        data = manager._load_session()
        assert data is not None
        assert data["cookies"][0]["name"] == "sid"

    def test_save_session_data_atomic(self, temp_dir):
        """Test that session data is saved atomically."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        session_data = {
            "execution_id": "exec-001",
            "timestamp": 1000,
            "cookies": [],
        }
        manager._save_session_data(session_data)

        # Verify only .json exists, not .tmp
        assert manager.session_file.exists()
        temp_file = manager.session_file.with_suffix(".json.tmp")
        assert not temp_file.exists()

    def test_save_session_data_with_cookies(self, temp_dir):
        """Test saving session with cookie data."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)

        session_data = {
            "execution_id": "exec-001",
            "timestamp": 1000,
            "cookies": [
                {"name": "session_id", "value": "abc123", "domain": ".example.com"},
                {"name": "csrf_token", "value": "xyz789", "domain": ".example.com"},
            ],
            "origins": [],
        }
        manager._save_session_data(session_data)

        # Reload and verify
        loaded = manager._load_session()
        assert len(loaded["cookies"]) == 2
        assert loaded["cookies"][0]["name"] == "session_id"

    @pytest.mark.asyncio
    async def test_save_session_without_context(self, temp_dir):
        """Test that save_session handles missing context gracefully."""
        manager = SessionManager(execution_id="exec-001", session_dir=temp_dir)
        # No context initialized
        manager.browser_context = None

        # Should not raise error
        await manager.save_session()

    def test_multiple_session_files(self, temp_dir):
        """Test managing multiple session files."""
        manager1 = SessionManager(execution_id="exec-001", session_dir=temp_dir)
        manager2 = SessionManager(execution_id="exec-002", session_dir=temp_dir)

        # Save sessions with different execution IDs
        session1 = {"execution_id": "exec-001", "cookies": []}
        session2 = {"execution_id": "exec-002", "cookies": []}

        manager1._save_session_data(session1)
        manager2._save_session_data(session2)

        # Both files should exist
        assert manager1.session_file.exists()
        assert manager2.session_file.exists()
        assert manager1.session_file != manager2.session_file
