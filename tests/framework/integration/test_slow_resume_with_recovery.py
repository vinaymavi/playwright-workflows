"""Integration tests for slow resume (>5 min) with recovery and re-authentication.

Tests step replay, 401/403 detection, and re-authentication workflows.
"""

import time
from pathlib import Path

import pytest

from src.framework.resumption_manager import ResumptionManager


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


@pytest.mark.asyncio
class TestSlowResumeWithRecovery:
    """Tests for slow resume workflow (>5 min) with recovery."""
    
    async def test_slow_resume_triggered_for_old_execution(self, resumption_manager):
        """Test slow resume is triggered for execution > 5 min old."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-1",
            "status": "failed",
            "started_at": now - 1000,
            "last_activity_at": now - 600,  # 10 minutes ago
            "completed_steps": 3,
            "total_steps": 10,
        }
        
        resumption_manager.save_execution_state("exec-1", execution_state)
        
        # Prepare for slow resume
        success, message = resumption_manager.prepare_for_slow_resume("exec-1")
        assert success
        assert "replay" in message.lower()
        
        # Verify state
        state = resumption_manager.get_resumption_info("exec-1")
        assert state["strategy"] == "slow"
        assert state["session_age_seconds"] > 500
    
    async def test_slow_resume_marks_replay_needed(self, resumption_manager):
        """Test slow resume marks replay as needed."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-2",
            "status": "paused",
            "started_at": now - 900,
            "last_activity_at": now - 700,  # 11+ minutes ago
            "completed_steps": 5,
        }
        
        resumption_manager.save_execution_state("exec-2", execution_state)
        
        success, message = resumption_manager.prepare_for_slow_resume("exec-2")
        assert success
        
        state = resumption_manager.load_execution_state("exec-2")
        assert state["replay_needed"] is True
        assert state["resumption_strategy"] == "slow"
    
    async def test_slow_resume_with_auth_failure_detection(self, resumption_manager):
        """Test slow resume detects 401/403 auth failures."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-3",
            "status": "failed",
            "started_at": now - 1200,
            "last_activity_at": now - 900,
            "completed_steps": 2,
            "total_steps": 8,
            "error": "HTTP 401 Unauthorized",
            "steps": [
                {
                    "id": "step-1",
                    "description": "Navigate to login",
                    "status": "completed",
                    "timestamp": now - 1000
                },
                {
                    "id": "step-2",
                    "description": "Fill login form",
                    "status": "completed",
                    "timestamp": now - 950
                },
                {
                    "id": "step-3",
                    "description": "Submit form",
                    "status": "failed",
                    "error": "HTTP 401",
                    "timestamp": now - 900
                }
            ]
        }
        
        resumption_manager.save_execution_state("exec-3", execution_state)
        
        success, message = resumption_manager.prepare_for_slow_resume("exec-3")
        assert success
        
        # Record auth detection event
        resumption_manager.record_recovery_event(
            "exec-3",
            "session_expired",
            {
                "http_status": 401,
                "step": "step-3",
                "error": "Session expired during form submit"
            }
        )
        
        state = resumption_manager.load_execution_state("exec-3")
        events = state["recovery_events"]
        assert len(events) == 1
        assert events[0]["type"] == "session_expired"
        assert events[0]["details"]["http_status"] == 401
    
    async def test_slow_resume_with_re_auth_workflow(self, resumption_manager):
        """Test slow resume with re-authentication workflow."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-4",
            "status": "failed",
            "started_at": now - 1000,
            "last_activity_at": now - 800,
            "error": "HTTP 403 Forbidden",
            "session": {
                "expired": True,
                "last_valid": now - 900
            }
        }
        
        resumption_manager.save_execution_state("exec-4", execution_state)
        
        # Prepare slow resume
        success, message = resumption_manager.prepare_for_slow_resume("exec-4")
        assert success
        
        # Record session expired
        resumption_manager.record_recovery_event(
            "exec-4",
            "session_expired",
            {
                "http_status": 403,
                "reason": "Session expired after 15+ minutes"
            }
        )
        
        # Record re-auth attempt
        resumption_manager.record_recovery_event(
            "exec-4",
            "re_auth",
            {
                "method": "stored_credentials",
                "username": "user@example.com",
                "status": "initiated"
            }
        )
        
        state = resumption_manager.load_execution_state("exec-4")
        events = state["recovery_events"]
        
        assert len(events) == 2
        assert events[0]["type"] == "session_expired"
        assert events[0]["details"]["http_status"] == 403
        assert events[1]["type"] == "re_auth"
        assert events[1]["details"]["method"] == "stored_credentials"
    
    async def test_slow_resume_replay_workflow(self, resumption_manager):
        """Test slow resume replay workflow."""
        now = time.time()
        
        execution_state = {
            "execution_id": "exec-5",
            "status": "failed",
            "started_at": now - 1200,
            "last_activity_at": now - 1000,
            "completed_steps": 3,
            "total_steps": 8,
            "steps": [
                {
                    "id": "step-1",
                    "description": "Navigate to login page",
                    "status": "completed"
                },
                {
                    "id": "step-2",
                    "description": "Enter username",
                    "status": "completed"
                },
                {
                    "id": "step-3",
                    "description": "Enter password",
                    "status": "completed"
                },
                {
                    "id": "step-4",
                    "description": "Click login button",
                    "status": "failed",
                    "error": "Session expired"
                }
            ]
        }
        
        resumption_manager.save_execution_state("exec-5", execution_state)
        
        # Prepare for slow resume
        success, message = resumption_manager.prepare_for_slow_resume("exec-5")
        assert success
        
        # Record replay events
        resumption_manager.record_recovery_event(
            "exec-5",
            "replay_started",
            {
                "steps_to_replay": 3,
                "from_step": "step-1",
                "to_step": "step-3"
            }
        )
        
        # Simulate replay progress
        time.sleep(0.01)  # Small delay to have different timestamp
        
        resumption_manager.record_recovery_event(
            "exec-5",
            "replay_complete",
            {
                "steps_replayed": 3,
                "success": True,
                "final_url": "https://example.com/dashboard"
            }
        )
        
        state = resumption_manager.load_execution_state("exec-5")
        events = state["recovery_events"]
        
        assert len(events) == 2
        assert events[0]["type"] == "replay_started"
        assert events[0]["details"]["steps_to_replay"] == 3
        assert events[1]["type"] == "replay_complete"
        assert events[1]["details"]["success"] is True
    
    async def test_slow_resume_full_recovery_sequence(self, resumption_manager):
        """Test complete slow resume recovery sequence."""
        now = time.time()
        
        # Initial failed execution
        execution_state = {
            "execution_id": "exec-6",
            "status": "failed",
            "started_at": now - 1500,
            "last_activity_at": now - 1200,
            "completed_steps": 3,
            "total_steps": 10,
            "error": "HTTP 401 Unauthorized",
            "workflow_type": "LoginWorkflow",
            "checkpoints": [
                {"id": "cp-1", "step": 3, "timestamp": now - 1300}
            ]
        }
        
        resumption_manager.save_execution_state("exec-6", execution_state)
        
        # Step 1: Determine slow resume needed
        info = resumption_manager.get_resumption_info("exec-6")
        assert info["strategy"] == "slow"
        assert info["session_age_seconds"] > 1000
        
        # Step 2: Prepare slow resume
        success, msg = resumption_manager.prepare_for_slow_resume("exec-6")
        assert success
        
        # Step 3: Detect session expired
        resumption_manager.record_recovery_event(
            "exec-6",
            "session_expired",
            {"http_status": 401, "reason": "Token expired"}
        )
        
        # Step 4: Start replay
        resumption_manager.record_recovery_event(
            "exec-6",
            "replay_started",
            {"steps_to_replay": 3}
        )
        
        # Step 5: Complete replay
        resumption_manager.record_recovery_event(
            "exec-6",
            "replay_complete",
            {"success": True}
        )
        
        # Step 6: Perform re-auth
        resumption_manager.record_recovery_event(
            "exec-6",
            "re_auth",
            {
                "method": "stored_credentials",
                "success": True,
                "new_token": "token-xyz"
            }
        )
        
        # Step 7: Session recovered
        resumption_manager.record_recovery_event(
            "exec-6",
            "session_recovered",
            {"strategy": "slow", "final_status": "ready"}
        )
        
        # Step 8: Mark resumption complete
        resumption_manager.mark_resumption_complete("exec-6")
        
        # Verify complete sequence
        final_state = resumption_manager.load_execution_state("exec-6")
        
        assert final_state["status"] == "running"
        assert final_state["resumption_strategy"] == "slow"
        assert len(final_state["recovery_events"]) == 5
        
        events = final_state["recovery_events"]
        event_types = [e["type"] for e in events]
        assert event_types == [
            "session_expired",
            "replay_started",
            "replay_complete",
            "re_auth",
            "session_recovered"
        ]
    
    async def test_slow_resume_with_multiple_auth_retries(self, resumption_manager):
        """Test slow resume handling multiple auth retry attempts."""
        now = time.time()
        
        execution_state = {
            "execution_id": "exec-7",
            "status": "failed",
            "started_at": now - 2000,
            "last_activity_at": now - 1500,
            "completed_steps": 2,
        }
        
        resumption_manager.save_execution_state("exec-7", execution_state)
        
        # Prepare slow resume
        resumption_manager.prepare_for_slow_resume("exec-7")
        
        # Record multiple auth attempts
        for attempt in range(1, 4):
            resumption_manager.record_recovery_event(
                "exec-7",
                "re_auth",
                {
                    "attempt": attempt,
                    "method": "stored_credentials",
                    "success": attempt == 3,  # Third attempt succeeds
                    "error": None if attempt == 3 else "Invalid credentials"
                }
            )
        
        state = resumption_manager.load_execution_state("exec-7")
        re_auth_events = [e for e in state["recovery_events"] if e["type"] == "re_auth"]
        
        assert len(re_auth_events) == 3
        assert re_auth_events[0]["details"]["success"] is False
        assert re_auth_events[1]["details"]["success"] is False
        assert re_auth_events[2]["details"]["success"] is True
    
    async def test_slow_resume_error_recovery_logging(self, resumption_manager):
        """Test comprehensive error recovery logging for slow resume."""
        now = time.time()
        
        execution_state = {
            "execution_id": "exec-8",
            "status": "failed",
            "started_at": now - 1800,
            "last_activity_at": now - 1500,
            "error": "Network timeout",
        }
        
        resumption_manager.save_execution_state("exec-8", execution_state)
        
        # Simulate complete recovery with detailed logging
        recovery_sequence = [
            ("session_expired", {"http_status": 401, "message": "Token expired"}),
            ("replay_started", {"total_steps": 5, "estimated_time": "30s"}),
            ("replay_complete", {"total_steps": 5, "actual_time": "28s"}),
            ("re_auth", {"method": "password", "status": "success"}),
            ("session_recovered", {"cookies_count": 3, "storage_keys": 5}),
        ]
        
        for event_type, details in recovery_sequence:
            resumption_manager.record_recovery_event("exec-8", event_type, details)
        
        state = resumption_manager.load_execution_state("exec-8")
        events = state["recovery_events"]
        
        # Verify all events recorded with details
        assert len(events) == 5
        
        # Check specific details
        assert events[0]["details"]["http_status"] == 401
        assert events[1]["details"]["total_steps"] == 5
        assert events[2]["details"]["actual_time"] == "28s"
        assert events[3]["details"]["method"] == "password"
        assert events[4]["details"]["cookies_count"] == 3
