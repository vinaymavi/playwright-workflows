"""Workflow Execution State Machine

Manages execution lifecycle and state persistence for workflow runs.
Provides state transitions (pending → running → paused → completed/failed)
and JSON-based state storage with file locking for concurrent safety.
"""

import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from .errors import WorkflowStateError


class ExecutionState(str, Enum):
    """Possible states for a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepResult(BaseModel):
    """Result of a step execution."""

    name: str
    status: str = Field(description="Step status: success, failed, skipped")
    output: Optional[dict[str, Any]] = Field(default=None, description="Step output data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration")
    retry_count: int = Field(default=0, description="Number of retries")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CheckpointState(BaseModel):
    """State of a checkpoint in the execution."""

    checkpoint_id: str
    question: dict[str, Any] = Field(description="Question posed to agent")
    response: Optional[dict[str, Any]] = Field(default=None, description="Agent's response")
    state_snapshot: Optional[dict[str, Any]] = Field(
        default=None, description="Workflow state at checkpoint"
    )
    timeout_seconds: int = Field(default=300, description="Response timeout")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    responded_at: Optional[str] = Field(default=None, description="When agent responded")


class ExecutionStateData(BaseModel):
    """Complete execution state persisted to JSON."""

    execution_id: str
    state: ExecutionState
    base_url: str
    input_params: dict[str, Any] = Field(default_factory=dict)
    output: Optional[dict[str, Any]] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None)
    steps: list[StepResult] = Field(default_factory=list, description="Completed steps")
    checkpoints: list[CheckpointState] = Field(
        default_factory=list, description="Checkpoints encountered"
    )
    current_step: Optional[str] = Field(default=None, description="Currently executing step")
    workflow_state: dict[str, Any] = Field(
        default_factory=dict, description="User-defined workflow state"
    )
    resources: list[dict[str, Any]] = Field(
        default_factory=list, description="Tracked artifacts (screenshots, PDFs)"
    )
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = Field(default=None)
    paused_at: Optional[str] = Field(default=None)
    resumed_at: Optional[str] = Field(default=None)
    completed_at: Optional[str] = Field(default=None)


class Execution:
    """Manages execution lifecycle and state persistence.

    Implements state machine with valid transitions:
    - pending → running (on start)
    - running → paused (on checkpoint) | completed (on success) | failed (on error)
    - paused → running (on resume) | failed (on timeout) | cancelled (on agent cancel)
    - completed/failed/cancelled: terminal states
    """

    def __init__(
        self,
        execution_id: Optional[str] = None,
        base_url: str = "",
        data_dir: Optional[Path] = None,
        max_retries: int = 3):
        """Initialize execution with optional ID and configuration.

        Args:
            execution_id: UUID for this execution (auto-generated if not provided)
            base_url: Base URL for workflow navigation
            data_dir: Directory for persisting state (defaults to data/executions/)
            max_retries: Max automatic retries per step
        """
        self.execution_id = execution_id or str(uuid.uuid4())
        self.base_url = base_url
        self.max_retries = max_retries

        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "executions"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.data_dir / f"{self.execution_id}.json"
        self._state: ExecutionStateData = ExecutionStateData(
            execution_id=self.execution_id, base_url=base_url, state=ExecutionState.PENDING
        )

    def start(self, input_params: dict[str, Any]) -> None:
        """Transition execution from PENDING to RUNNING.

        Args:
            input_params: Input parameters for the workflow

        Raises:
            WorkflowStateError: If already running or in terminal state
        """
        if self._state.state != ExecutionState.PENDING:
            raise WorkflowStateError(
                "Cannot start execution that is not in PENDING state",
                current_state=self._state.state.value,
                requested_state="running")

        self._state.state = ExecutionState.RUNNING
        self._state.input_params = input_params
        self._state.started_at = datetime.utcnow().isoformat()
        self.save()

    def pause(self, checkpoint: CheckpointState) -> None:
        """Transition execution from RUNNING to PAUSED at checkpoint.

        Args:
            checkpoint: The checkpoint that triggered pause

        Raises:
            WorkflowStateError: If not currently running
        """
        if self._state.state != ExecutionState.RUNNING:
            raise WorkflowStateError(
                "Can only pause execution that is RUNNING",
                current_state=self._state.state.value,
                requested_state="paused")

        self._state.state = ExecutionState.PAUSED
        self._state.paused_at = datetime.utcnow().isoformat()
        self._state.checkpoints.append(checkpoint)
        self.save()

    def resume(self, response: Optional[dict[str, Any]] = None) -> None:
        """Transition execution from PAUSED back to RUNNING.

        Args:
            response: Optional response from agent/human to the checkpoint question

        Raises:
            WorkflowStateError: If not currently paused
        """
        if self._state.state != ExecutionState.PAUSED:
            raise WorkflowStateError(
                "Can only resume execution that is PAUSED",
                current_state=self._state.state.value,
                requested_state="running")

        # Update latest checkpoint with response if provided
        if response is not None and self._state.checkpoints:
            self._state.checkpoints[-1].response = response
            self._state.checkpoints[-1].responded_at = datetime.utcnow().isoformat()

        self._state.state = ExecutionState.RUNNING
        self._state.resumed_at = datetime.utcnow().isoformat()
        self.save()

    def complete(self, output: Optional[dict[str, Any]] = None) -> None:
        """Transition execution to COMPLETED state.

        Args:
            output: Final output/result of the workflow

        Raises:
            WorkflowStateError: If not in RUNNING or PAUSED state
        """
        if self._state.state not in (ExecutionState.RUNNING, ExecutionState.PAUSED):
            raise WorkflowStateError(
                "Can only complete execution that is RUNNING or PAUSED",
                current_state=self._state.state.value,
                requested_state="completed")

        self._state.state = ExecutionState.COMPLETED
        self._state.output = output
        self._state.completed_at = datetime.utcnow().isoformat()
        self.save()

    def fail(self, error_message: str, error_code: Optional[str] = None) -> None:
        """Transition execution to FAILED state.

        Args:
            error_message: Description of failure
            error_code: Classification code for error

        Raises:
            WorkflowStateError: If in terminal state
        """
        if self._state.state in (ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED):
            raise WorkflowStateError(
                f"Cannot fail execution in terminal state {self._state.state.value}",
                current_state=self._state.state.value,
                requested_state="failed")

        self._state.state = ExecutionState.FAILED
        self._state.error_message = error_message
        self._state.error_code = error_code
        self._state.completed_at = datetime.utcnow().isoformat()
        self.save()

    def cancel(self) -> None:
        """Transition execution to CANCELLED state.

        Raises:
            WorkflowStateError: If already in terminal state
        """
        if self._state.state in (ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED):
            raise WorkflowStateError(
                f"Cannot cancel execution in terminal state {self._state.state.value}",
                current_state=self._state.state.value,
                requested_state="cancelled")

        self._state.state = ExecutionState.CANCELLED
        self._state.completed_at = datetime.utcnow().isoformat()
        self.save()

    def add_step_result(self, step: StepResult) -> None:
        """Record result of a step execution.

        Args:
            step: The completed step result
        """
        self._state.steps.append(step)
        self.save()

    def set_workflow_state(self, key: str, value: Any) -> None:
        """Store user-defined workflow state.

        Args:
            key: State key
            value: State value (must be JSON-serializable)
        """
        self._state.workflow_state[key] = value
        self.save()

    def get_workflow_state(self, key: str, default: Any = None) -> Any:
        """Retrieve user-defined workflow state.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            The stored value or default
        """
        return self._state.workflow_state.get(key, default)

    def save(self) -> None:
        """Persist execution state to JSON file with file locking.

        Uses atomic write (write to temp, then rename) for crash safety.
        File locking prevents concurrent modifications.
        """
        from ..utils.file_locking import atomic_write_json

        atomic_write_json(self.state_file, self._state.model_dump(exclude_none=False))

    def load(self) -> bool:
        """Load execution state from JSON file.

        Returns:
            True if file found and loaded, False if not found
        """
        if not self.state_file.exists():
            return False

        with open(self.state_file, "r") as f:
            data = json.load(f)

        self._state = ExecutionStateData(**data)
        return True

    def get_state(self) -> ExecutionState:
        """Get current execution state."""
        return self._state.state

    def is_terminal(self) -> bool:
        """Check if execution is in a terminal state."""
        return self._state.state in (
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED)

    def to_dict(self) -> dict[str, Any]:
        """Export execution state as dictionary."""
        return self._state.model_dump(exclude_none=False)
