"""Unit tests for ResumptionManager

Tests quick vs slow resume logic without browser interaction.
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.framework.resumption_manager import ResumptionManager, ResumptionStrategy


@pytest.fixture
def temp_execution_dir(tmp_path):
    """Fixture providing a temporary execution directory."""
    exec_dir = tmp_path / "executions"
    exec_dir.mkdir()
    return exec_dir


@pytest.fixture
def resumption_manager(temp_execution_dir):
    """Fixture providing a ResumptionManager with temp directory."""
    return ResumptionManager(execution_dir=temp_execution_dir)


class TestResumptionStrategy:
    """Tests for ResumptionStrategy.determine_strategy()"""
    
    def test_quick_resume_for_recent_execution(self):
        """Test quick resume strategy for execution < 5 min old."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-1",
            "started_at": now,
            "last_activity_at": now - 60,  # 1 minute ago
        }
        
        strategy = ResumptionStrategy.determine_strategy(execution_state)
        assert strategy == "quick"
    
    def test_quick_resume_at_threshold(self):
        """Test slow resume at exactly 5 min threshold (boundary)."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-1",
            "started_at": now,
            "last_activity_at": now - 300,  # Exactly 5 minutes ago
        }
        
        strategy = ResumptionStrategy.determine_strategy(execution_state)
        # At threshold, should switch to slow resume
        assert strategy == "slow"
    
    def test_slow_resume_for_old_execution(self):
        """Test slow resume strategy for execution > 5 min old."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-1",
            "started_at": now,
            "last_activity_at": now - 600,  # 10 minutes ago
        }
        
        strategy = ResumptionStrategy.determine_strategy(execution_state)
        assert strategy == "slow"
    
    def test_strategy_with_iso_timestamp(self):
        """Test strategy determination with ISO format timestamps."""
        from datetime import datetime
        
        now = datetime.utcnow()
        recent_time = now.replace(microsecond=0).isoformat() + "Z"
        
        execution_state = {
            "execution_id": "exec-1",
            "last_activity_at": recent_time,
        }
        
        strategy = ResumptionStrategy.determine_strategy(execution_state)
        assert strategy == "quick"


class TestResumptionManager:
    """Tests for ResumptionManager"""
    
    def test_initialization(self, temp_execution_dir):
        """Test manager initialization creates directory."""
        manager = ResumptionManager(execution_dir=temp_execution_dir)
        assert manager.execution_dir == temp_execution_dir
        assert temp_execution_dir.exists()
    
    def test_save_and_load_execution_state(self, resumption_manager):
        """Test saving and loading execution state."""
        state = {
            "execution_id": "exec-1",
            "status": "paused",
            "completed_steps": 3,
            "total_steps": 10,
        }
        
        # Save
        success = resumption_manager.save_execution_state("exec-1", state)
        assert success
        
        # Load
        loaded = resumption_manager.load_execution_state("exec-1")
        assert loaded == state
    
    def test_load_nonexistent_execution(self, resumption_manager):
        """Test loading nonexistent execution returns None."""
        result = resumption_manager.load_execution_state("nonexistent")
        assert result is None
    
    def test_get_resumption_info_quick(self, resumption_manager):
        """Test get_resumption_info for quick resume case."""
        now = time.time()
        state = {
            "execution_id": "exec-1",
            "status": "paused",
            "completed_steps": 5,
            "total_steps": 10,
            "started_at": now - 100,
            "last_activity_at": now - 60,  # 1 minute ago
            "checkpoints": [
                {"id": "cp-1", "step": 5, "timestamp": now - 60}
            ],
            "workflow_type": "LoginWorkflow",
        }
        
        resumption_manager.save_execution_state("exec-1", state)
        
        info = resumption_manager.get_resumption_info("exec-1")
        assert info is not None
        assert info["execution_id"] == "exec-1"
        assert info["status"] == "paused"
        assert info["strategy"] == "quick"
        assert info["session_age_seconds"] < 120  # Less than 2 minutes
        assert info["completed_steps"] == 5
        assert info["total_steps"] == 10
        assert info["last_checkpoint"]["id"] == "cp-1"
    
    def test_get_resumption_info_slow(self, resumption_manager):
        """Test get_resumption_info for slow resume case."""
        now = time.time()
        state = {
            "execution_id": "exec-2",
            "status": "failed",
            "completed_steps": 3,
            "total_steps": 10,
            "started_at": now - 1000,
            "last_activity_at": now - 600,  # 10 minutes ago
            "checkpoints": [
                {"id": "cp-1", "step": 3, "timestamp": now - 600}
            ],
            "workflow_type": "LoginWorkflow",
        }
        
        resumption_manager.save_execution_state("exec-2", state)
        
        info = resumption_manager.get_resumption_info("exec-2")
        assert info is not None
        assert info["strategy"] == "slow"
        assert info["session_age_seconds"] > 500
    
    def test_prepare_for_quick_resume_success(self, resumption_manager):
        """Test prepare_for_quick_resume success."""
        state = {
            "execution_id": "exec-1",
            "status": "paused",
            "completed_steps": 5,
        }
        
        resumption_manager.save_execution_state("exec-1", state)
        
        success, message = resumption_manager.prepare_for_quick_resume("exec-1")
        assert success
        assert "quick resume" in message.lower()
        
        # Verify state updated
        updated = resumption_manager.load_execution_state("exec-1")
        assert updated["status"] == "resuming"
        assert updated["resumption_strategy"] == "quick"
        assert "resumed_at" in updated
    
    def test_prepare_for_quick_resume_not_found(self, resumption_manager):
        """Test prepare_for_quick_resume with nonexistent execution."""
        success, message = resumption_manager.prepare_for_quick_resume("nonexistent")
        assert not success
        assert "not found" in message.lower()
    
    def test_prepare_for_quick_resume_invalid_status(self, resumption_manager):
        """Test prepare_for_quick_resume with invalid status."""
        state = {
            "execution_id": "exec-1",
            "status": "completed",  # Can't resume completed execution
        }
        
        resumption_manager.save_execution_state("exec-1", state)
        
        success, message = resumption_manager.prepare_for_quick_resume("exec-1")
        assert not success
        assert "cannot resume" in message.lower()
    
    def test_prepare_for_slow_resume_success(self, resumption_manager):
        """Test prepare_for_slow_resume success."""
        state = {
            "execution_id": "exec-2",
            "status": "pending_checkpoint",
            "completed_steps": 3,
        }
        
        resumption_manager.save_execution_state("exec-2", state)
        
        success, message = resumption_manager.prepare_for_slow_resume("exec-2")
        assert success
        assert "slow resume" in message.lower()
        assert "replay" in message.lower()
        
        # Verify state updated
        updated = resumption_manager.load_execution_state("exec-2")
        assert updated["status"] == "resuming"
        assert updated["resumption_strategy"] == "slow"
        assert updated["replay_needed"] is True
    
    def test_prepare_for_slow_resume_failed_status(self, resumption_manager):
        """Test prepare_for_slow_resume with failed status."""
        state = {
            "execution_id": "exec-3",
            "status": "failed",
            "error": "Network timeout",
        }
        
        resumption_manager.save_execution_state("exec-3", state)
        
        success, message = resumption_manager.prepare_for_slow_resume("exec-3")
        assert success
    
    def test_mark_resumption_complete(self, resumption_manager):
        """Test mark_resumption_complete."""
        state = {
            "execution_id": "exec-1",
            "status": "resuming",
        }
        
        resumption_manager.save_execution_state("exec-1", state)
        
        success = resumption_manager.mark_resumption_complete("exec-1")
        assert success
        
        # Verify state updated
        updated = resumption_manager.load_execution_state("exec-1")
        assert updated["status"] == "running"
        assert "resumption_complete_at" in updated
    
    def test_record_recovery_event_session_expired(self, resumption_manager):
        """Test recording session_expired event."""
        state = {
            "execution_id": "exec-1",
            "status": "paused",
        }
        
        resumption_manager.save_execution_state("exec-1", state)
        
        success = resumption_manager.record_recovery_event(
            "exec-1",
            "session_expired",
            {"http_status": 401, "url": "http://example.com"}
        )
        assert success
        
        updated = resumption_manager.load_execution_state("exec-1")
        assert "recovery_events" in updated
        assert len(updated["recovery_events"]) == 1
        assert updated["recovery_events"][0]["type"] == "session_expired"
        assert updated["recovery_events"][0]["details"]["http_status"] == 401
    
    def test_record_recovery_event_re_auth(self, resumption_manager):
        """Test recording re_auth event."""
        state = {
            "execution_id": "exec-2",
            "status": "resuming",
            "recovery_events": [
                {"type": "session_expired", "timestamp": time.time()}
            ],
        }
        
        resumption_manager.save_execution_state("exec-2", state)
        
        success = resumption_manager.record_recovery_event(
            "exec-2",
            "re_auth",
            {"strategy": "credential_replay", "username": "user@example.com"}
        )
        assert success
        
        updated = resumption_manager.load_execution_state("exec-2")
        assert len(updated["recovery_events"]) == 2
        assert updated["recovery_events"][1]["type"] == "re_auth"
    
    def test_record_recovery_event_replay_workflow(self, resumption_manager):
        """Test recording replay events."""
        state = {
            "execution_id": "exec-3",
            "status": "resuming",
        }
        
        resumption_manager.save_execution_state("exec-3", state)
        
        # Record replay_started
        resumption_manager.record_recovery_event(
            "exec-3",
            "replay_started",
            {"steps_to_replay": 5}
        )
        
        # Record replay_complete
        resumption_manager.record_recovery_event(
            "exec-3",
            "replay_complete",
            {"steps_replayed": 5}
        )
        
        updated = resumption_manager.load_execution_state("exec-3")
        events = updated["recovery_events"]
        assert len(events) == 2
        assert events[0]["type"] == "replay_started"
        assert events[1]["type"] == "replay_complete"
    
    def test_multiple_recovery_events(self, resumption_manager):
        """Test handling multiple recovery events in sequence."""
        state = {
            "execution_id": "exec-4",
            "status": "paused",
        }
        
        resumption_manager.save_execution_state("exec-4", state)
        
        # Simulate recovery sequence
        event_sequence = [
            ("session_expired", {"http_status": 401}),
            ("re_auth", {"method": "stored_credentials"}),
            ("replay_started", {"steps": 3}),
            ("replay_complete", {"success": True}),
            ("session_recovered", {"new_cookies": 2}),
        ]
        
        for event_type, details in event_sequence:
            resumption_manager.record_recovery_event("exec-4", event_type, details)
        
        updated = resumption_manager.load_execution_state("exec-4")
        events = updated["recovery_events"]
        
        assert len(events) == 5
        assert events[0]["type"] == "session_expired"
        assert events[1]["type"] == "re_auth"
        assert events[2]["type"] == "replay_started"
        assert events[3]["type"] == "replay_complete"
        assert events[4]["type"] == "session_recovered"
