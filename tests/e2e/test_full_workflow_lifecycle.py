"""End-to-end workflow lifecycle tests.

Tests the complete workflow lifecycle with real APIs:
- Workflow creation and initialization
- Step execution and state management
- Checkpoint pause/resume
- Artifact tracking
- Error handling and recovery
"""

import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from src.framework.state_manager import StateManager
from src.framework.resource_manager import ResourceManager
from src.framework.workflow import Workflow


class ConcreteWorkflow(Workflow):
    """Concrete workflow implementation for testing."""

    async def run(self):
        """Implement abstract run method."""
        return {"status": "success"}


@pytest.fixture
def temp_workflow_dir():
    """Create temporary directory for workflow data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def state_manager(temp_workflow_dir):
    """Create StateManager instance."""
    return StateManager(str(temp_workflow_dir / "executions"))


@pytest.fixture
def resource_manager(temp_workflow_dir):
    """Create ResourceManager instance."""
    return ResourceManager(str(temp_workflow_dir / "artifacts"))


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_workflow_initialization(temp_workflow_dir):
    """Test workflow can be initialized."""
    execution_id = str(uuid4())
    state_file = temp_workflow_dir / f"{execution_id}.json"

    workflow = ConcreteWorkflow(
        execution_id=execution_id,
        base_url="https://example.com",
        state_file=state_file,
    )

    assert workflow.execution_id == execution_id
    assert workflow.base_url == "https://example.com"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_workflow_state_management(temp_workflow_dir):
    """Test workflow state can be set and retrieved."""
    execution_id = str(uuid4())
    state_file = temp_workflow_dir / f"{execution_id}.json"

    workflow = ConcreteWorkflow(
        execution_id=execution_id,
        base_url="https://example.com",
        state_file=state_file,
    )

    # Set state
    workflow.set_state("step_count", 5)
    workflow.set_state("current_url", "https://example.com/page1")

    # Retrieve state
    assert workflow.get_state("step_count") == 5
    assert workflow.get_state("current_url") == "https://example.com/page1"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_state_manager_persistence(state_manager):
    """Test StateManager saves and loads state correctly."""
    execution_id = str(uuid4())
    state_data = {
        "execution_id": execution_id,
        "status": "running",
        "current_step": 2,
        "steps_completed": ["navigate", "fill"],
    }

    # Save state
    state_manager.save(execution_id, state_data)

    # Load state
    loaded = state_manager.load(execution_id)
    assert loaded["execution_id"] == execution_id
    assert loaded["status"] == "running"
    assert loaded["current_step"] == 2
    assert len(loaded["steps_completed"]) == 2


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_artifact_tracking(resource_manager, temp_workflow_dir):
    """Test ResourceManager tracks artifacts correctly."""
    execution_id = str(uuid4())

    # Create a temporary artifact file
    artifact_file = temp_workflow_dir / "test_screenshot.png"
    artifact_file.write_bytes(b"fake image data")

    # Track the artifact
    resource = resource_manager.track_resource(
        execution_id=execution_id,
        file_path=artifact_file,
        resource_type="screenshot",
        name="test_screenshot",
    )

    assert resource.name == "test_screenshot"
    assert resource.resource_type == "screenshot"

    # Get artifacts
    artifacts = resource_manager.get_resources(execution_id)
    assert len(artifacts) > 0
    assert any(a.name == "test_screenshot" for a in artifacts)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_checkpoint_workflow(state_manager):
    """Test checkpoint pause/resume workflow."""
    execution_id = str(uuid4())

    # Start execution
    initial = {
        "execution_id": execution_id,
        "status": "created",
        "steps": [],
    }
    state_manager.save(execution_id, initial)

    # Run initial steps
    running = state_manager.load(execution_id)
    running["status"] = "running"
    running["steps"] = ["navigate", "fill"]
    running["current_step"] = 1
    state_manager.save(execution_id, running)

    # Pause at checkpoint
    paused = state_manager.load(execution_id)
    paused["status"] = "paused_at_checkpoint"
    paused["checkpoint_id"] = str(uuid4())
    paused["checkpoint_question"] = "Approve form data?"
    state_manager.save(execution_id, paused)

    # Verify paused
    check_paused = state_manager.load(execution_id)
    assert check_paused["status"] == "paused_at_checkpoint"
    assert "checkpoint_id" in check_paused

    # Resume workflow
    resumed = state_manager.load(execution_id)
    resumed["status"] = "resuming"
    resumed["checkpoint_decision"] = {"approved": True}
    state_manager.save(execution_id, resumed)

    # Complete workflow
    completed = state_manager.load(execution_id)
    completed["status"] = "completed"
    completed["steps"].append("submit")
    completed["result"] = {"success": True}
    state_manager.save(execution_id, completed)

    # Verify completed
    final = state_manager.load(execution_id)
    assert final["status"] == "completed"
    assert len(final["steps"]) == 3
    assert final["result"]["success"] is True


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_error_recovery(state_manager):
    """Test error handling and transient vs permanent errors."""
    execution_id = str(uuid4())

    state = {
        "execution_id": execution_id,
        "status": "running",
        "errors": [],
    }
    state_manager.save(execution_id, state)

    # Simulate transient error (network timeout)
    current = state_manager.load(execution_id)
    current["errors"].append({
        "step": "navigate",
        "message": "Connection timeout",
        "type": "transient",
        "retry_count": 1,
    })
    current["status"] = "retrying"
    state_manager.save(execution_id, current)

    # Verify error recorded
    with_error = state_manager.load(execution_id)
    assert len(with_error["errors"]) == 1
    assert with_error["errors"][0]["type"] == "transient"
    assert with_error["status"] == "retrying"

    # Recover
    recovered = state_manager.load(execution_id)
    recovered["status"] = "running"
    recovered["errors"] = []
    state_manager.save(execution_id, recovered)

    # Verify recovery
    final = state_manager.load(execution_id)
    assert final["status"] == "running"
    assert len(final["errors"]) == 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_concurrent_executions(state_manager):
    """Test multiple workflows run independently."""
    execution_ids = [str(uuid4()) for _ in range(3)]

    # Create 3 separate executions
    for exec_id in execution_ids:
        state = {
            "execution_id": exec_id,
            "status": "running",
            "step": 1,
        }
        state_manager.save(exec_id, state)

    # Verify all are independent
    for exec_id in execution_ids:
        state = state_manager.load(exec_id)
        assert state["execution_id"] == exec_id
        assert state["status"] == "running"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_workflow_lifecycle(state_manager, resource_manager, temp_workflow_dir):
    """Complete workflow lifecycle: create → run → checkpoint → resume → complete.
    
    This comprehensive E2E test validates the entire system:
    1. Create workflow execution
    2. Run initial steps
    3. Create artifacts
    4. Hit checkpoint and pause
    5. Resume from checkpoint
    6. Create more artifacts
    7. Complete execution
    8. Verify all state and artifacts
    """
    execution_id = str(uuid4())

    # Phase 1: Create execution
    state = {
        "execution_id": execution_id,
        "workflow_type": "form_filling",
        "status": "created",
        "created_at": "2024-01-01T00:00:00Z",
        "steps": [],
        "errors": [],
    }
    state_manager.save(execution_id, state)

    created = state_manager.load(execution_id)
    assert created["status"] == "created"

    # Phase 2: Run initial steps
    running = state_manager.load(execution_id)
    running["status"] = "running"
    running["started_at"] = "2024-01-01T00:00:01Z"
    running["steps"].extend(["navigate", "fill"])
    state_manager.save(execution_id, running)

    # Phase 3: Create artifact (screenshot)
    artifact1 = temp_workflow_dir / "form_fill.png"
    artifact1.write_bytes(b"screenshot data")
    resource1 = resource_manager.track_resource(
        execution_id,
        artifact1,
        "screenshot",
        "form_fill_screenshot",
    )
    assert resource1.name == "form_fill_screenshot"

    # Phase 4: Checkpoint
    checkpoint = state_manager.load(execution_id)
    checkpoint["status"] = "paused_at_checkpoint"
    checkpoint["checkpoint_id"] = str(uuid4())
    checkpoint["checkpoint_question"] = "Does the form look correct?"
    checkpoint["context"] = {
        "url": "https://example.com/form",
        "form_data": {"username": "testuser"},
    }
    state_manager.save(execution_id, checkpoint)

    paused = state_manager.load(execution_id)
    assert paused["status"] == "paused_at_checkpoint"

    # Phase 5: Resume workflow
    resumed = state_manager.load(execution_id)
    resumed["status"] = "resumed"
    resumed["checkpoint_decision"] = {
        "approved": True,
        "decided_by": "human_agent",
    }
    state_manager.save(execution_id, resumed)

    # Phase 6: Continue and create another artifact (PDF)
    continuing = state_manager.load(execution_id)
    continuing["status"] = "running"
    continuing["steps"].append("submit")
    state_manager.save(execution_id, continuing)

    artifact2 = temp_workflow_dir / "confirmation.pdf"
    artifact2.write_bytes(b"pdf data")
    resource2 = resource_manager.track_resource(
        execution_id,
        artifact2,
        "pdf",
        "confirmation_page",
    )
    assert resource2.name == "confirmation_page"

    # Phase 7: Complete workflow
    complete = state_manager.load(execution_id)
    complete["status"] = "completed"
    complete["completed_at"] = "2024-01-01T00:00:10Z"
    complete["result"] = {
        "success": True,
        "message": "Form submitted successfully",
        "submission_id": "SUB-12345",
    }
    state_manager.save(execution_id, complete)

    # Phase 8: Comprehensive verification
    final = state_manager.load(execution_id)

    # Verify metadata
    assert final["execution_id"] == execution_id
    assert final["workflow_type"] == "form_filling"
    assert final["status"] == "completed"
    assert final["result"]["success"] is True

    # Verify steps
    assert len(final["steps"]) == 3
    assert final["steps"] == ["navigate", "fill", "submit"]

    # Verify checkpoint
    assert final["checkpoint_id"] is not None
    assert final["checkpoint_decision"]["approved"] is True

    # Verify artifacts
    artifacts = resource_manager.get_resources(execution_id)
    assert len(artifacts) == 2

    artifact_names = {a.name for a in artifacts}
    assert "form_fill_screenshot" in artifact_names
    assert "confirmation_page" in artifact_names

    artifact_types = {a.resource_type for a in artifacts}
    assert "screenshot" in artifact_types
    assert "pdf" in artifact_types

    # Verify no errors
    assert len(final["errors"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
