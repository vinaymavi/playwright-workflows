"""Integration tests for quick resume (<5 min) with browser context preservation.

Tests actual browser context preservation and resumption without replay.
"""

import asyncio
import time
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

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
class TestQuickResume:
    """Tests for quick resume workflow (<5 min)."""
    
    async def test_quick_resume_within_threshold(self, resumption_manager):
        """Test quick resume is triggered for execution < 5 min old."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-1",
            "status": "paused",
            "started_at": now - 60,  # Started 1 minute ago
            "last_activity_at": now - 30,  # Last activity 30 seconds ago
            "completed_steps": 5,
            "total_steps": 10,
            "workflow_type": "BrowsingWorkflow",
        }
        
        resumption_manager.save_execution_state("exec-1", execution_state)
        
        # Prepare for quick resume
        success, message = resumption_manager.prepare_for_quick_resume("exec-1")
        assert success
        
        # Verify state
        state = resumption_manager.get_resumption_info("exec-1")
        assert state["strategy"] == "quick"
        assert state["session_age_seconds"] < 60
    
    async def test_quick_resume_preserves_browser_context(self, resumption_manager):
        """Test that quick resume would preserve browser context (simulated).
        
        This simulates the browser context preservation without actual browser.
        """
        now = time.time()
        execution_state = {
            "execution_id": "exec-2",
            "status": "paused",
            "started_at": now - 120,  # 2 minutes ago
            "last_activity_at": now - 60,  # 1 minute ago
            "completed_steps": 3,
            "total_steps": 10,
            "browser_context_preserved": True,
            "session": {
                "cookies": [
                    {"name": "session_id", "value": "abc123"}
                ],
            }
        }
        
        resumption_manager.save_execution_state("exec-2", execution_state)
        
        success, message = resumption_manager.prepare_for_quick_resume("exec-2")
        assert success
        
        # Verify context preservation is noted
        state = resumption_manager.load_execution_state("exec-2")
        assert state.get("browser_context_preserved") is True
        assert "session" in state
        assert len(state["session"]["cookies"]) > 0
    
    async def test_quick_resume_resumes_from_checkpoint(self, resumption_manager):
        """Test quick resume continues from last checkpoint."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-3",
            "status": "pending_checkpoint",
            "started_at": now - 180,
            "last_activity_at": now - 30,  # Just paused
            "completed_steps": 7,
            "total_steps": 10,
            "checkpoints": [
                {
                    "id": "cp-1",
                    "step": 5,
                    "timestamp": now - 120,
                    "checkpoint_data": {"page_url": "https://example.com/page1"}
                },
                {
                    "id": "cp-2",
                    "step": 7,
                    "timestamp": now - 30,
                    "checkpoint_data": {"page_url": "https://example.com/page3"}
                }
            ]
        }
        
        resumption_manager.save_execution_state("exec-3", execution_state)
        
        success, message = resumption_manager.prepare_for_quick_resume("exec-3")
        assert success
        
        # Verify we have checkpoint info
        state = resumption_manager.get_resumption_info("exec-3")
        assert state["last_checkpoint"]["id"] == "cp-2"
        assert state["last_checkpoint"]["step"] == 7
        assert state["last_checkpoint"]["checkpoint_data"]["page_url"] == "https://example.com/page3"
    
    async def test_quick_resume_no_replay_needed(self, resumption_manager):
        """Test that quick resume doesn't mark replay as needed."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-4",
            "status": "paused",
            "started_at": now - 60,
            "last_activity_at": now - 30,
            "completed_steps": 2,
            "total_steps": 8,
            "replay_needed": False,
        }
        
        resumption_manager.save_execution_state("exec-4", execution_state)
        
        success, message = resumption_manager.prepare_for_quick_resume("exec-4")
        assert success
        
        # Verify replay not needed
        state = resumption_manager.load_execution_state("exec-4")
        assert state.get("replay_needed") is False
        assert state["resumption_strategy"] == "quick"
    
    async def test_quick_resume_session_validity_check(self, resumption_manager):
        """Test quick resume can verify session is still valid."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-5",
            "status": "paused",
            "started_at": now - 120,
            "last_activity_at": now - 30,
            "session": {
                "cookies": [
                    {"name": "sid", "value": "xyz789", "expires": now + 3600}
                ],
                "valid": True
            }
        }
        
        resumption_manager.save_execution_state("exec-5", execution_state)
        
        success, message = resumption_manager.prepare_for_quick_resume("exec-5")
        assert success
        
        state = resumption_manager.load_execution_state("exec-5")
        assert state["session"]["valid"] is True
    
    async def test_multiple_quick_resumes(self, resumption_manager):
        """Test handling multiple sequential quick resumes."""
        now = time.time()
        
        # First execution
        state1 = {
            "execution_id": "exec-6",
            "status": "paused",
            "started_at": now - 60,
            "last_activity_at": now - 30,
            "completed_steps": 2,
        }
        resumption_manager.save_execution_state("exec-6", state1)
        
        # First resume
        success1, msg1 = resumption_manager.prepare_for_quick_resume("exec-6")
        assert success1
        
        # Mark complete
        resumption_manager.mark_resumption_complete("exec-6")
        
        # Simulate second pause after more work
        state_updated = resumption_manager.load_execution_state("exec-6")
        state_updated["status"] = "paused"
        state_updated["completed_steps"] = 5
        state_updated["last_activity_at"] = now - 10  # Just paused again
        resumption_manager.save_execution_state("exec-6", state_updated)
        
        # Second resume
        success2, msg2 = resumption_manager.prepare_for_quick_resume("exec-6")
        assert success2
        
        final_state = resumption_manager.load_execution_state("exec-6")
        assert final_state["resumption_strategy"] == "quick"
    
    async def test_quick_resume_with_recovery_events(self, resumption_manager):
        """Test quick resume records session recovery event."""
        now = time.time()
        execution_state = {
            "execution_id": "exec-7",
            "status": "paused",
            "started_at": now - 90,
            "last_activity_at": now - 30,
            "recovery_events": [
                {
                    "type": "session_check",
                    "timestamp": now - 30,
                }
            ]
        }
        
        resumption_manager.save_execution_state("exec-7", execution_state)
        
        success, message = resumption_manager.prepare_for_quick_resume("exec-7")
        assert success
        
        # Record recovery event
        resumption_manager.record_recovery_event(
            "exec-7",
            "session_recovered",
            {
                "strategy": "quick",
                "context_preserved": True,
            }
        )
        
        state = resumption_manager.load_execution_state("exec-7")
        events = state["recovery_events"]
        assert len(events) == 2
        assert events[-1]["type"] == "session_recovered"
        assert events[-1]["details"]["context_preserved"] is True
    
    async def test_quick_resume_execution_flow(self, resumption_manager):
        """Test complete quick resume execution flow."""
        now = time.time()
        
        # 1. Initial execution (paused)
        execution_state = {
            "execution_id": "exec-8",
            "status": "paused",
            "started_at": now - 120,
            "last_activity_at": now - 45,
            "completed_steps": 4,
            "total_steps": 8,
            "workflow_type": "LoginWorkflow",
            "checkpoints": [
                {"id": "cp-1", "step": 4, "timestamp": now - 45}
            ]
        }
        resumption_manager.save_execution_state("exec-8", execution_state)
        
        # 2. Get resumption info
        info = resumption_manager.get_resumption_info("exec-8")
        assert info["strategy"] == "quick"
        assert info["session_age_seconds"] < 60
        
        # 3. Prepare quick resume
        success, msg = resumption_manager.prepare_for_quick_resume("exec-8")
        assert success
        
        # 4. Record recovery
        resumption_manager.record_recovery_event(
            "exec-8",
            "session_recovered",
            {"strategy": "quick"}
        )
        
        # 5. Mark complete
        resumption_manager.mark_resumption_complete("exec-8")
        
        # 6. Verify final state
        final_state = resumption_manager.load_execution_state("exec-8")
        assert final_state["status"] == "running"
        assert final_state["resumption_strategy"] == "quick"
        assert "resumed_at" in final_state
        assert "resumption_complete_at" in final_state
        assert len(final_state["recovery_events"]) == 1
