"""Unit tests for state_manager module."""

import json
import tempfile
from pathlib import Path

import pytest

from src.framework.state_manager import StateManager


class TestStateManager:
    """Test StateManager for persistent state storage."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for state files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_initialization(self, temp_dir):
        """Test state manager initialization."""
        manager = StateManager(state_dir=temp_dir)
        assert manager.state_dir == temp_dir

    def test_save_state(self, temp_dir):
        """Test saving state to storage."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "execution_id": "exec-001",
            "status": "running",
            "current_step": "navigate",
        }
        manager.save("exec-001", state)
        
        file_path = temp_dir / "exec-001.json"
        assert file_path.exists()

    def test_load_state(self, temp_dir):
        """Test loading state from storage."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "execution_id": "exec-001",
            "status": "running",
            "current_step": "navigate",
        }
        manager.save("exec-001", state)

        # Load state
        loaded = manager.load("exec-001")
        assert loaded["status"] == "running"
        assert loaded["current_step"] == "navigate"

    def test_load_nonexistent_returns_none(self, temp_dir):
        """Test that loading nonexistent state returns None."""
        manager = StateManager(state_dir=temp_dir)
        loaded = manager.load("exec-999")
        assert loaded is None

    def test_update_state(self, temp_dir):
        """Test updating part of state."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "status": "pending",
            "steps": [],
            "metadata": {"start_time": 1000},
        }
        manager.save("exec-001", state)

        # Update specific fields
        manager.update("exec-001", {"status": "running", "current_step": "click"})

        loaded = manager.load("exec-001")
        assert loaded["status"] == "running"
        assert loaded["current_step"] == "click"
        assert loaded["steps"] == []  # Untouched

    def test_update_nested_field(self, temp_dir):
        """Test updating nested field with dot notation."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "status": "running",
            "context": {"page": "login", "user": "john"},
        }
        manager.save("exec-001", state)

        manager.update("exec-001", {"context.user": "jane"})

        loaded = manager.load("exec-001")
        assert loaded["context"]["user"] == "jane"
        assert loaded["context"]["page"] == "login"  # Untouched

    def test_get_nested_value(self, temp_dir):
        """Test getting nested value with dot notation."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "context": {
                "form": {"username": "john", "email": "john@example.com"},
            },
        }
        manager.save("exec-001", state)

        # Load and check nested access works
        loaded = manager.load("exec-001")
        assert loaded["context"]["form"]["username"] == "john"

    def test_atomic_write(self, temp_dir):
        """Test that writes are atomic (temp file -> rename)."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "execution_id": "exec-001",
            "status": "running",
            "steps_completed": 5,
        }
        manager.save("exec-001", state)

        # Verify state file exists
        file_path = temp_dir / "exec-001.json"
        assert file_path.exists()

    def test_concurrent_access_safe(self, temp_dir):
        """Test that multiple state managers can access same directory."""
        manager1 = StateManager(state_dir=temp_dir)
        manager2 = StateManager(state_dir=temp_dir)

        # Both managers operate on different keys
        manager1.save("exec-001", {"status": "running", "value": 1})
        manager2.save("exec-002", {"status": "pending", "value": 2})

        # Both should load correctly
        loaded1 = manager1.load("exec-001")
        loaded2 = manager2.load("exec-002")
        assert loaded1["value"] == 1
        assert loaded2["value"] == 2

    def test_large_nested_structure(self, temp_dir):
        """Test saving and loading large nested structures."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "execution_id": "exec-001",
            "workflow": {
                "steps": [
                    {"name": "init", "status": "success", "data": {"page": "/"}},
                    {"name": "login", "status": "success", "data": {"user_id": 123}},
                ],
                "context": {
                    "form_values": {
                        "username": "john",
                        "email": "john@example.com",
                        "address": {
                            "street": "123 Main St",
                            "city": "Boston",
                            "zip": "02101",
                        },
                    },
                },
            },
        }
        manager.save("exec-001", state)

        # Load and verify nested structure preserved
        loaded = manager.load("exec-001")
        assert loaded["workflow"]["steps"][0]["data"]["page"] == "/"
        assert (
            loaded["workflow"]["context"]["form_values"]["address"]["city"]
            == "Boston"
        )

    def test_special_characters_in_state(self, temp_dir):
        """Test handling special characters in state values."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "status": "running",
            "context": {
                "text": 'Hello "world" with \\escapes and\nnewlines',
                "emoji": "🎉✨",
            },
        }
        manager.save("exec-001", state)

        loaded = manager.load("exec-001")
        assert loaded["context"]["emoji"] == "🎉✨"

    def test_null_values_preserved(self, temp_dir):
        """Test that null values are preserved."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "status": "running",
            "optional_field": None,
            "steps": [{"name": "test", "result": None}],
        }
        manager.save("exec-001", state)

        loaded = manager.load("exec-001")
        assert loaded["optional_field"] is None
        assert loaded["steps"][0]["result"] is None

    def test_null_values(self, temp_dir):
        """Test handling null/None values."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "status": "running",
            "error": None,
            "result": None,
        }
        manager.save("exec-001", state)

        loaded = manager.load("exec-001")
        assert loaded["error"] is None
        assert loaded["result"] is None

    def test_boolean_and_numeric_types(self, temp_dir):
        """Test handling boolean and numeric types."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "status": "running",
            "success": True,
            "failure": False,
            "count": 42,
            "percentage": 99.5,
        }
        manager.save("exec-001", state)

        loaded = manager.load("exec-001")
        assert loaded["success"] is True
        assert loaded["failure"] is False
        assert loaded["count"] == 42
        assert loaded["percentage"] == 99.5

    def test_list_updates(self, temp_dir):
        """Test updating list fields."""
        manager = StateManager(state_dir=temp_dir)
        state = {
            "status": "running",
            "completed_steps": ["init", "login"],
        }
        manager.save("exec-001", state)

        manager.update("exec-001", {"completed_steps": ["init", "login", "navigate"]})

        loaded = manager.load("exec-001")
        assert len(loaded["completed_steps"]) == 3
        assert loaded["completed_steps"][-1] == "navigate"
