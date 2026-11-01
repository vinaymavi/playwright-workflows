"""Unit tests for execution module."""

import pytest

from src.framework.errors import WorkflowStateError
from src.framework.execution import (
    CheckpointState,
    Execution,
    ExecutionState,
    ExecutionStateData,
    StepResult,
)


class TestExecutionState:
    """Test ExecutionState enum."""

    def test_state_values(self):
        """Test all required state values exist."""
        assert ExecutionState.PENDING.value == "pending"
        assert ExecutionState.RUNNING.value == "running"
        assert ExecutionState.PAUSED.value == "paused"
        assert ExecutionState.COMPLETED.value == "completed"
        assert ExecutionState.FAILED.value == "failed"
        assert ExecutionState.CANCELLED.value == "cancelled"

    def test_state_ordering(self):
        """Test state ordering in enum."""
        states = list(ExecutionState)
        assert len(states) == 6


class TestStepResult:
    """Test StepResult pydantic model."""

    def test_success_result(self):
        """Test successful step result."""
        result = StepResult(
            name="navigate",
            status="success",
            output={"url": "https://example.com"},
        )
        assert result.name == "navigate"
        assert result.status == "success"
        assert result.output["url"] == "https://example.com"

    def test_failure_result(self):
        """Test failed step result."""
        result = StepResult(
            name="click",
            status="failed",
            error="Element not found",
        )
        assert result.status == "failed"
        assert result.error == "Element not found"

    def test_result_with_duration(self):
        """Test step result with execution duration."""
        result = StepResult(
            name="fill_form",
            status="success",
            output={"fields_filled": 5},
            duration_seconds=2.5,
            retry_count=1,
        )
        assert result.duration_seconds == 2.5
        assert result.retry_count == 1

    def test_result_serialization(self):
        """Test step result JSON serialization."""
        result = StepResult(
            name="fill_form",
            status="success",
            output={"fields_filled": 5},
        )
        json_data = result.model_dump_json()
        assert "fill_form" in json_data
        assert "success" in json_data


class TestCheckpointState:
    """Test CheckpointState pydantic model."""

    def test_checkpoint_creation(self):
        """Test checkpoint state initialization."""
        checkpoint = CheckpointState(
            checkpoint_id="cp-001",
            question={"text": "Confirm form submission?", "type": "yes_no"},
        )
        assert checkpoint.checkpoint_id == "cp-001"
        assert checkpoint.question["text"] == "Confirm form submission?"

    def test_checkpoint_with_response(self):
        """Test checkpoint with response data."""
        checkpoint = CheckpointState(
            checkpoint_id="cp-002",
            question={"text": "Select option", "options": ["A", "B", "C"]},
            response={"choice": "A"},
            state_snapshot={"form_values": {"name": "John"}},
        )
        assert checkpoint.response["choice"] == "A"
        assert checkpoint.state_snapshot["form_values"]["name"] == "John"

    def test_checkpoint_timeout(self):
        """Test checkpoint with custom timeout."""
        checkpoint = CheckpointState(
            checkpoint_id="cp-003",
            question={"text": "Verify credentials"},
            timeout_seconds=600,
        )
        assert checkpoint.timeout_seconds == 600


class TestExecutionStateData:
    """Test ExecutionStateData pydantic model."""

    def test_state_data_creation(self):
        """Test execution state data initialization."""
        state_data = ExecutionStateData(
            execution_id="exec-001",
            state=ExecutionState.RUNNING,
            base_url="https://example.com",
        )
        assert state_data.execution_id == "exec-001"
        assert state_data.state == ExecutionState.RUNNING
        assert state_data.base_url == "https://example.com"

    def test_state_data_with_steps(self):
        """Test state data with step results."""
        step1 = StepResult(name="init", status="success")
        step2 = StepResult(name="navigate", status="success", output={"page": "/"})

        state_data = ExecutionStateData(
            execution_id="exec-001",
            state=ExecutionState.RUNNING,
            base_url="https://example.com",
            steps=[step1, step2],
        )
        assert len(state_data.steps) == 2
        assert state_data.steps[0].name == "init"
        assert state_data.steps[1].output["page"] == "/"

    def test_state_data_with_error(self):
        """Test state data with error information."""
        state_data = ExecutionStateData(
            execution_id="exec-001",
            state=ExecutionState.FAILED,
            base_url="https://example.com",
            error_message="Step execution failed",
            error_code="STEP_FAILED",
        )
        assert state_data.error_message == "Step execution failed"
        assert state_data.error_code == "STEP_FAILED"

    def test_state_data_serialization(self):
        """Test state data JSON serialization."""
        state_data = ExecutionStateData(
            execution_id="exec-001",
            state=ExecutionState.RUNNING,
            base_url="https://example.com",
        )
        json_data = state_data.model_dump_json()
        assert "exec-001" in json_data
        assert "running" in json_data


class TestExecution:
    """Test Execution state machine."""

    def test_execution_initialization(self):
        """Test execution creation."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
        )
        assert execution.execution_id == "exec-001"
        assert execution.base_url == "https://example.com"
        assert execution._state.state == ExecutionState.PENDING

    def test_pending_to_running_transition(self, tmp_path):
        """Test valid transition from PENDING to RUNNING."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={"username": "test"})
        assert execution._state.state == ExecutionState.RUNNING
        assert execution._state.input_params == {"username": "test"}

    def test_running_to_paused_transition(self, tmp_path):
        """Test valid transition from RUNNING to PAUSED."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={})
        
        checkpoint = CheckpointState(
            checkpoint_id="cp-001",
            question={"text": "Confirm?"},
        )
        execution.pause(checkpoint)
        assert execution._state.state == ExecutionState.PAUSED

    def test_paused_to_running_transition(self, tmp_path):
        """Test valid transition from PAUSED to RUNNING (resume)."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={})
        
        checkpoint = CheckpointState(
            checkpoint_id="cp-001",
            question={"text": "Confirm?"},
        )
        execution.pause(checkpoint)
        
        response = {"choice": "yes"}
        execution.resume(response)
        assert execution._state.state == ExecutionState.RUNNING

    def test_running_to_completed_transition(self, tmp_path):
        """Test valid transition from RUNNING to COMPLETED."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={})
        execution.complete(output={"status": "success"})
        assert execution._state.state == ExecutionState.COMPLETED

    def test_running_to_failed_transition(self, tmp_path):
        """Test valid transition from RUNNING to FAILED."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={})
        execution.fail(error_message="Execution error occurred")
        assert execution._state.state == ExecutionState.FAILED
        assert execution._state.error_message == "Execution error occurred"

    def test_invalid_double_start(self, tmp_path):
        """Test invalid transition: cannot start already running execution."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={})
        with pytest.raises(WorkflowStateError):
            execution.start(input_params={})

    def test_invalid_pause_paused_execution(self, tmp_path):
        """Test invalid transition: cannot pause already paused execution."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={})
        
        checkpoint = CheckpointState(
            checkpoint_id="cp-001",
            question={"text": "Confirm?"},
        )
        execution.pause(checkpoint)
        
        with pytest.raises(WorkflowStateError):
            execution.pause(checkpoint)

    def test_invalid_resume_running_execution(self, tmp_path):
        """Test invalid transition: cannot resume running execution."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={})
        with pytest.raises(WorkflowStateError):
            execution.resume(response={})

    def test_invalid_complete_pending_execution(self, tmp_path):
        """Test invalid transition: cannot complete pending execution."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        with pytest.raises(WorkflowStateError):
            execution.complete(output={})

    def test_invalid_complete_completed_execution(self, tmp_path):
        """Test invalid transition: cannot complete completed execution."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={})
        execution.complete(output={})
        with pytest.raises(WorkflowStateError):
            execution.complete(output={})

    def test_cancel_from_running(self, tmp_path):
        """Test cancellation from RUNNING state."""
        execution = Execution(
            execution_id="exec-001",
            base_url="https://example.com",
            data_dir=tmp_path,
        )
        execution.start(input_params={})
        execution.cancel()
        assert execution._state.state == ExecutionState.CANCELLED


    def test_cancel_from_paused(self):
        """Test cancellation from PAUSED state."""
        execution = Execution(
            execution_id="exec-001",
        )
        execution.start({})
        checkpoint = CheckpointState(
            checkpoint_id="ckpt-001",
            question={"prompt": "Continue?"}
        )
        execution.pause(checkpoint)
        execution.cancel()
        assert execution.get_state() == ExecutionState.CANCELLED

    def test_add_completed_step(self):
        """Test adding completed steps."""
        execution = Execution(
            execution_id="exec-001",
        )
        step = StepResult(name="navigate", status="success")
        execution.add_step_result(step)
        assert len(execution._state.steps) == 1
        assert execution._state.steps[0].name == "navigate"

    def test_get_current_step(self):
        """Test retrieving current step."""
        execution = Execution(
            execution_id="exec-001",
        )
        execution._state.current_step = "fill_form"
        assert execution._state.current_step == "fill_form"

    def test_state_persistence(self):
        """Test that state is persistent across operations."""
        execution = Execution(
            execution_id="exec-001",
        )
        execution.start({})
        checkpoint = CheckpointState(
            checkpoint_id="ckpt-001",
            question={"prompt": "Continue?"}
        )
        execution.pause(checkpoint)
        state_before = execution.get_state()
        execution.resume()
        execution.pause(checkpoint)
        state_after = execution.get_state()
        assert state_before == state_after == ExecutionState.PAUSED
