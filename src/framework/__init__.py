"""Playwright workflow orchestration framework.

This module provides the core building blocks for creating automated web workflows
with checkpoint-based human/agent intervention support.

Public API:
- Workflow: Base class for workflow implementations
- step: Decorator for workflow steps with retry and error handling
- retry: General-purpose retry decorator
- Execution: Execution state machine
- Checkpoint classes: CheckpointQuestion, CheckpointRequest, CheckpointResponse
- Error classes: WorkflowError, PermanentError, TransientError, etc.
- StateManager: JSON-based state persistence
- SessionManager: Browser context lifecycle management

Example:
    from playwright_workflows.framework import Workflow, step

    class LoginWorkflow(Workflow):
        workflow_type = "login_workflow"
        version = "1.0.0"
        description = "Login to web application"

        async def run(self, username: str, password: str) -> dict:
            await self.navigate(f"{self.base_url}/login")
            await self.fill("#username", username)
            await self.fill("#password", password)

            decision = await self.checkpoint(
                question=CheckpointQuestion(
                    question_text="Ready to submit login?"
                ),
                timeout_seconds=300
            )

            await self.click("button[type='submit']")
            return {"status": "logged_in"}
"""

from .checkpoint import (
    CheckpointQuestion,
    CheckpointRequest,
    CheckpointResponse,
    CheckpointProtocol,
)
from .decorators import step, retry
from .errors import (
    WorkflowError,
    WorkflowCheckpointTimeout,
    PermanentError,
    TransientError,
    WorkflowStateError,
)
from .execution import Execution, ExecutionState
from .retry_handler import RetryPolicy, with_retry, with_retry_sync
from .session_manager import SessionManager
from .state_manager import StateManager
from .workflow import Workflow

__all__ = [
    # Workflow base class
    "Workflow",
    # Decorators
    "step",
    "retry",
    # Checkpoint protocol
    "CheckpointQuestion",
    "CheckpointRequest",
    "CheckpointResponse",
    "CheckpointProtocol",
    # Execution tracking
    "Execution",
    "ExecutionState",
    # Error hierarchy
    "WorkflowError",
    "WorkflowCheckpointTimeout",
    "PermanentError",
    "TransientError",
    "WorkflowStateError",
    # Retry policy
    "RetryPolicy",
    "with_retry",
    "with_retry_sync",
    # State management
    "StateManager",
    "SessionManager",
]

__version__ = "0.1.0"
