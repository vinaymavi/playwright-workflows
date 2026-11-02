"""Mock MCP Agent Client for Testing Checkpoints

Provides a mock agent client that simulates agent responses to checkpoints
without requiring a real MCP server connection. Used for unit and integration
testing of checkpoint pause/resume workflows.
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio

from src.framework.checkpoint import (
    CheckpointRequest,
    CheckpointResponse,
    CheckpointDecision,
)


@dataclass
class CheckpointDecisionStrategy:
    """Strategy for simulating agent decision responses."""

    decision_delay_ms: int = 0
    """Delay before agent responds (simulates thinking time)"""

    auto_approve: bool = True
    """If True, automatically approve checkpoints"""

    approval_choice: str = "proceed"
    """Default choice for approvals"""

    rejection_choice: str = "cancel"
    """Default choice for rejections"""

    response_overrides: Dict[str, CheckpointDecision] = None
    """Map checkpoint_id -> CheckpointDecision for custom responses"""

    def __post_init__(self):
        if self.response_overrides is None:
            self.response_overrides = {}


class MockAgentClient:
    """Mock MCP agent client for testing checkpoint workflows.

    Simulates agent responses to checkpoint questions without requiring
    a real MCP server. Supports configurable delays, approval strategies,
    and per-checkpoint response overrides.

    Example:
        ```python
        client = MockAgentClient(
            strategy=CheckpointDecisionStrategy(
                decision_delay_ms=100,
                auto_approve=True,
            )
        )

        # Workflow calls: response = await client.resolve_checkpoint(checkpoint_id)
        # Client automatically returns "proceed" decision after 100ms delay
        ```
    """

    def __init__(self, strategy: Optional[CheckpointDecisionStrategy] = None):
        """Initialize mock agent client.

        Args:
            strategy: DecisionStrategy controlling how client responds.
                     Defaults to immediate auto-approve.
        """
        self.strategy = strategy or CheckpointDecisionStrategy()
        self.checkpoint_history: list[Dict[str, Any]] = []
        self.resolved_checkpoints: Dict[str, CheckpointDecision] = {}
        self.pending_checkpoints: Dict[str, CheckpointRequest] = {}

    async def resolve_checkpoint(
        self,
        checkpoint_id: str,
        checkpoint_request: CheckpointRequest,
    ) -> CheckpointResponse:
        """Simulate resolving a checkpoint with agent decision.

        Args:
            checkpoint_id: ID of checkpoint to resolve
            checkpoint_request: The checkpoint request (for context)

        Returns:
            CheckpointResponse with simulated agent decision

        Raises:
            ValueError: If checkpoint_id not found in pending checkpoints
        """
        # Store in pending checkpoints
        self.pending_checkpoints[checkpoint_id] = checkpoint_request

        # Simulate agent processing time
        if self.strategy.decision_delay_ms > 0:
            await asyncio.sleep(self.strategy.decision_delay_ms / 1000.0)

        # Check for override decision
        if checkpoint_id in self.strategy.response_overrides:
            decision = self.strategy.response_overrides[checkpoint_id]
        else:
            # Use strategy to generate decision
            decision = self._generate_decision(checkpoint_request)

        # Create response
        response = CheckpointResponse(
            checkpoint_id=checkpoint_id,
            execution_id=checkpoint_request.execution_id,
            decision=decision,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        # Track history
        self.checkpoint_history.append({
            "checkpoint_id": checkpoint_id,
            "request": checkpoint_request.model_dump(),
            "response": response.model_dump(),
            "resolved_at": response.timestamp,
        })

        # Track resolved
        self.resolved_checkpoints[checkpoint_id] = decision

        return response

    def _generate_decision(
        self,
        checkpoint_request: CheckpointRequest,
    ) -> CheckpointDecision:
        """Generate a decision based on strategy and question type.

        Args:
            checkpoint_request: The checkpoint request

        Returns:
            CheckpointDecision instance
        """
        question = checkpoint_request.question
        decision = CheckpointDecision()

        if not self.strategy.auto_approve:
            # Generate rejection
            if question.question_type == "single_choice":
                decision.choice = self.strategy.rejection_choice
            elif question.question_type == "yes_no":
                decision.confirmed = False
            elif question.question_type == "free_text":
                decision.text = "rejected"
            elif question.question_type == "multi_choice":
                decision.choices = []
        else:
            # Generate approval
            if question.question_type == "single_choice":
                if (
                    question.options
                    and self.strategy.approval_choice in question.options
                ):
                    decision.choice = self.strategy.approval_choice
                else:
                    # Default to first option
                    decision.choice = question.options[0] if question.options else "yes"
            elif question.question_type == "yes_no":
                decision.confirmed = True
            elif question.question_type == "free_text":
                decision.text = "approved"
            elif question.question_type == "multi_choice":
                # Select all available options
                decision.choices = question.options or []

        return decision

    def get_checkpoint_history(self) -> list[Dict[str, Any]]:
        """Get complete history of checkpoints processed.

        Returns:
            List of checkpoint records (request, response, timing)
        """
        return self.checkpoint_history.copy()

    def get_checkpoint_request(self, checkpoint_id: str) -> Optional[CheckpointRequest]:
        """Retrieve a stored checkpoint request.

        Args:
            checkpoint_id: ID of checkpoint to retrieve

        Returns:
            CheckpointRequest if found, None otherwise
        """
        return self.pending_checkpoints.get(checkpoint_id)

    def get_checkpoint_decision(self, checkpoint_id: str) -> Optional[CheckpointDecision]:
        """Retrieve the decision made for a checkpoint.

        Args:
            checkpoint_id: ID of checkpoint

        Returns:
            CheckpointDecision if found, None otherwise
        """
        return self.resolved_checkpoints.get(checkpoint_id)

    def set_override_decision(
        self,
        checkpoint_id: str,
        decision: CheckpointDecision,
    ) -> None:
        """Set a custom response for a specific checkpoint ID.

        Args:
            checkpoint_id: ID to override
            decision: Decision to return for that checkpoint
        """
        self.strategy.response_overrides[checkpoint_id] = decision

    def clear_overrides(self) -> None:
        """Clear all checkpoint decision overrides."""
        self.strategy.response_overrides.clear()

    def reset(self) -> None:
        """Reset client state (history, resolved, overrides)."""
        self.checkpoint_history.clear()
        self.resolved_checkpoints.clear()
        self.pending_checkpoints.clear()
        self.clear_overrides()

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about checkpoint processing.

        Returns:
            Dict with counts and summaries
        """
        approvals = sum(
            1 for d in self.resolved_checkpoints.values()
            if d.choice == self.strategy.approval_choice
        )
        rejections = sum(
            1 for d in self.resolved_checkpoints.values()
            if d.choice == self.strategy.rejection_choice
        )

        return {
            "total_checkpoints": len(self.checkpoint_history),
            "approvals": approvals,
            "rejections": rejections,
            "pending": len(self.pending_checkpoints),
            "response_time_ms": self.strategy.decision_delay_ms,
            "auto_approve_enabled": self.strategy.auto_approve,
        }


class MockAgentClientFixture:
    """Pytest fixture helper for mock agent client.

    Provides a pre-configured mock client for use in tests with
    various strategy configurations.

    Example:
        ```python
        @pytest.fixture
        def mock_agent():
            return MockAgentClientFixture().with_auto_approve().client

        async def test_something(mock_agent):
            response = await mock_agent.resolve_checkpoint(...)
        ```
    """

    def __init__(self):
        """Initialize fixture."""
        self.client = MockAgentClient()

    def with_auto_approve(self, enabled: bool = True) -> "MockAgentClientFixture":
        """Enable or disable auto-approval strategy.

        Args:
            enabled: If True, automatically approve all checkpoints

        Returns:
            Self for chaining
        """
        self.client.strategy.auto_approve = enabled
        return self

    def with_delay(self, delay_ms: int) -> "MockAgentClientFixture":
        """Set response delay to simulate agent thinking time.

        Args:
            delay_ms: Delay in milliseconds

        Returns:
            Self for chaining
        """
        self.client.strategy.decision_delay_ms = delay_ms
        return self

    def with_rejection(self) -> "MockAgentClientFixture":
        """Configure to reject all checkpoints.

        Returns:
            Self for chaining
        """
        self.client.strategy.auto_approve = False
        return self

    def with_override(
        self,
        checkpoint_id: str,
        decision: CheckpointDecision,
    ) -> "MockAgentClientFixture":
        """Add a custom response override for a checkpoint.

        Args:
            checkpoint_id: Checkpoint to override
            decision: Decision to return

        Returns:
            Self for chaining
        """
        self.client.set_override_decision(checkpoint_id, decision)
        return self

    def get_client(self) -> MockAgentClient:
        """Get the configured client.

        Returns:
            MockAgentClient instance
        """
        return self.client
