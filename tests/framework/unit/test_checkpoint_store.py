"""Tests for checkpoint_store.py - JSON-based checkpoint persistence."""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.framework.checkpoint_store import CheckpointStore, get_checkpoint_store


class TestCheckpointStoreSaveLoad:
    """Test basic save and load operations."""

    def test_save_creates_checkpoint_file(self):
        """Test that save creates a valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            checkpoint_data = {
                "checkpoint_id": "cp_123",
                "execution_id": "exec_123",
                "step_number": 2,
                "question": {"text": "Continue?"},
                "status": "pending",
            }
            
            cp_id = store.save(checkpoint_data)
            
            assert cp_id == "cp_123"
            checkpoint_path = Path(tmpdir) / "cp_123.json"
            assert checkpoint_path.exists()
            
            # Verify file content
            with open(checkpoint_path) as f:
                loaded = json.load(f)
            assert loaded["checkpoint_id"] == "cp_123"
            assert loaded["execution_id"] == "exec_123"
            assert "created_at" in loaded

    def test_save_generates_checkpoint_id_if_missing(self):
        """Test that save generates a UUID if checkpoint_id is not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            checkpoint_data = {
                "execution_id": "exec_123",
                "status": "pending",
            }
            
            cp_id = store.save(checkpoint_data)
            
            assert cp_id  # Should be non-empty
            assert len(cp_id) == 36  # UUID v4 format
            checkpoint_path = Path(tmpdir) / f"{cp_id}.json"
            assert checkpoint_path.exists()

    def test_save_requires_execution_id(self):
        """Test that save raises error if execution_id is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            checkpoint_data = {
                "checkpoint_id": "cp_123",
                "status": "pending",
                # Missing execution_id
            }
            
            with pytest.raises(ValueError, match="execution_id"):
                store.save(checkpoint_data)

    def test_load_returns_checkpoint_data(self):
        """Test that load retrieves saved checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            original = {
                "checkpoint_id": "cp_456",
                "execution_id": "exec_456",
                "step_number": 3,
                "status": "pending",
            }
            
            store.save(original)
            loaded = store.load("cp_456")
            
            assert loaded is not None
            assert loaded["checkpoint_id"] == "cp_456"
            assert loaded["execution_id"] == "exec_456"
            assert loaded["step_number"] == 3

    def test_load_returns_none_for_missing_checkpoint(self):
        """Test that load returns None if checkpoint doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            result = store.load("nonexistent_id")
            
            assert result is None


class TestCheckpointStoreResolution:
    """Test checkpoint resolution (marking as resolved/timed out)."""

    def test_mark_resolved_updates_checkpoint(self):
        """Test that mark_resolved updates checkpoint status and adds response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            checkpoint_data = {
                "checkpoint_id": "cp_resolve_1",
                "execution_id": "exec_resolve",
                "status": "pending",
                "question": {"text": "Continue?"},
            }
            
            store.save(checkpoint_data)
            
            decision = {
                "choice": "proceed",
                "timestamp": "2026-11-01T12:00:00Z",
            }
            
            result = store.mark_resolved("cp_resolve_1", decision)
            
            assert result is True
            
            resolved = store.load("cp_resolve_1")
            assert resolved["status"] == "resolved"
            assert resolved["response"] == decision
            assert "resolved_at" in resolved

    def test_mark_resolved_fails_for_missing_checkpoint(self):
        """Test that mark_resolved returns False if checkpoint doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            result = store.mark_resolved("nonexistent", {"choice": "proceed"})
            
            assert result is False

    def test_mark_timeout_updates_checkpoint(self):
        """Test that mark_timeout updates checkpoint status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            checkpoint_data = {
                "checkpoint_id": "cp_timeout_1",
                "execution_id": "exec_timeout",
                "status": "pending",
            }
            
            store.save(checkpoint_data)
            
            result = store.mark_timeout("cp_timeout_1", "keep_alive")
            
            assert result is True
            
            timed_out = store.load("cp_timeout_1")
            assert timed_out["status"] == "timeout"
            assert timed_out["timeout_strategy"] == "keep_alive"
            assert "timeout_at" in timed_out

    def test_mark_timeout_with_replay_strategy(self):
        """Test mark_timeout with replay strategy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            checkpoint_data = {
                "checkpoint_id": "cp_replay",
                "execution_id": "exec_replay",
                "status": "pending",
            }
            
            store.save(checkpoint_data)
            store.mark_timeout("cp_replay", "replay")
            
            timed_out = store.load("cp_replay")
            assert timed_out["timeout_strategy"] == "replay"


class TestCheckpointStoreQuerying:
    """Test querying and filtering checkpoints."""

    def test_get_pending_returns_only_pending_checkpoints(self):
        """Test that get_pending returns only unresolved checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            # Create multiple checkpoints with different statuses
            store.save({"checkpoint_id": "cp_1", "execution_id": "exec_1", "status": "pending"})
            store.save({"checkpoint_id": "cp_2", "execution_id": "exec_1", "status": "pending"})
            store.save({"checkpoint_id": "cp_3", "execution_id": "exec_1", "status": "resolved"})
            
            pending = store.get_pending("exec_1")
            
            assert len(pending) == 2
            assert all(cp["status"] == "pending" for cp in pending)

    def test_get_pending_returns_empty_for_unknown_execution(self):
        """Test that get_pending returns empty list for unknown execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            pending = store.get_pending("unknown_exec_id")
            
            assert pending == []

    def test_query_execution_checkpoints_filters_by_status(self):
        """Test that query_execution_checkpoints filters by status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            store.save({"checkpoint_id": "cp_1", "execution_id": "exec_q1", "status": "pending"})
            store.save({"checkpoint_id": "cp_2", "execution_id": "exec_q1", "status": "resolved"})
            store.save({"checkpoint_id": "cp_3", "execution_id": "exec_q1", "status": "timeout"})
            
            # Query all
            all_cps = store.query_execution_checkpoints("exec_q1")
            assert len(all_cps) == 3
            
            # Query specific status
            pending = store.query_execution_checkpoints("exec_q1", status="pending")
            assert len(pending) == 1
            assert pending[0]["checkpoint_id"] == "cp_1"
            
            resolved = store.query_execution_checkpoints("exec_q1", status="resolved")
            assert len(resolved) == 1
            assert resolved[0]["checkpoint_id"] == "cp_2"

    def test_list_all_checkpoints(self):
        """Test that list_all_checkpoints returns all checkpoint IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            store.save({"checkpoint_id": "cp_a", "execution_id": "exec_a"})
            store.save({"checkpoint_id": "cp_b", "execution_id": "exec_a"})
            store.save({"checkpoint_id": "cp_c", "execution_id": "exec_b"})
            
            checkpoints = store.list_all_checkpoints()
            
            assert len(checkpoints) == 3
            assert "cp_a" in checkpoints
            assert "cp_b" in checkpoints
            assert "cp_c" in checkpoints


class TestCheckpointStoreDeletion:
    """Test checkpoint deletion."""

    def test_delete_checkpoint_removes_file(self):
        """Test that delete_checkpoint removes the checkpoint file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            store.save({"checkpoint_id": "cp_del", "execution_id": "exec_del"})
            checkpoint_path = Path(tmpdir) / "cp_del.json"
            assert checkpoint_path.exists()
            
            result = store.delete_checkpoint("cp_del")
            
            assert result is True
            assert not checkpoint_path.exists()

    def test_delete_checkpoint_returns_false_if_not_found(self):
        """Test that delete_checkpoint returns False for nonexistent checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            result = store.delete_checkpoint("nonexistent")
            
            assert result is False


class TestCheckpointStoreExecutionIndex:
    """Test execution index management."""

    def test_save_updates_execution_index(self):
        """Test that save creates/updates execution index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            store.save({"checkpoint_id": "cp_idx_1", "execution_id": "exec_idx"})
            store.save({"checkpoint_id": "cp_idx_2", "execution_id": "exec_idx"})
            
            index_path = Path(tmpdir) / "execution_exec_idx_index.json"
            assert index_path.exists()
            
            with open(index_path) as f:
                index_data = json.load(f)
            
            assert index_data["execution_id"] == "exec_idx"
            assert "cp_idx_1" in index_data["checkpoints"]
            assert "cp_idx_2" in index_data["checkpoints"]

    def test_execution_index_prevents_duplicate_checkpoint_ids(self):
        """Test that execution index doesn't store duplicate checkpoint IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            data = {"checkpoint_id": "cp_dup", "execution_id": "exec_dup"}
            store.save(data)
            store.save(data)  # Save same checkpoint again
            
            index_path = Path(tmpdir) / "execution_exec_dup_index.json"
            with open(index_path) as f:
                index_data = json.load(f)
            
            # Count occurrences of checkpoint ID
            count = index_data["checkpoints"].count("cp_dup")
            assert count == 1


class TestCheckpointStoreGlobalInstance:
    """Test global store instance management."""

    def test_get_checkpoint_store_returns_singleton(self):
        """Test that get_checkpoint_store returns the same instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = get_checkpoint_store(tmpdir)
            store2 = get_checkpoint_store(tmpdir)
            
            assert store1 is store2

    def test_store_directory_created_on_init(self):
        """Test that store directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / "nested" / "checkpoints"
            
            store = CheckpointStore(str(nested_dir))
            
            assert nested_dir.exists()
            assert nested_dir.is_dir()


class TestCheckpointStoreEdgeCases:
    """Test edge cases and error handling."""

    def test_save_with_timestamp(self):
        """Test that save uses provided timestamp or creates one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            checkpoint_data = {
                "checkpoint_id": "cp_ts",
                "execution_id": "exec_ts",
            }
            
            store.save(checkpoint_data)
            loaded = store.load("cp_ts")
            
            assert "created_at" in loaded
            assert loaded["created_at"].endswith("Z")

    def test_mark_resolved_with_custom_timestamp(self):
        """Test mark_resolved with custom timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            store.save({"checkpoint_id": "cp_cust_ts", "execution_id": "exec_cust_ts"})
            
            custom_ts = "2026-11-01T15:30:00Z"
            store.mark_resolved("cp_cust_ts", {"choice": "proceed"}, timestamp=custom_ts)
            
            resolved = store.load("cp_cust_ts")
            assert resolved["resolved_at"] == custom_ts

    def test_concurrent_checkpoint_saves_to_different_executions(self):
        """Test that checkpoints from different executions don't interfere."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CheckpointStore(tmpdir)
            
            store.save({"checkpoint_id": "cp_exec1_1", "execution_id": "exec1", "status": "pending"})
            store.save({"checkpoint_id": "cp_exec1_2", "execution_id": "exec1", "status": "pending"})
            store.save({"checkpoint_id": "cp_exec2_1", "execution_id": "exec2", "status": "pending"})
            
            exec1_pending = store.get_pending("exec1")
            exec2_pending = store.get_pending("exec2")
            
            assert len(exec1_pending) == 2
            assert len(exec2_pending) == 1
            assert exec1_pending[0]["checkpoint_id"] == "cp_exec1_1"
            assert exec2_pending[0]["checkpoint_id"] == "cp_exec2_1"
