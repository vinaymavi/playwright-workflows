"""Checkpoint Protocol for Agent/Human Decision Points

Defines structures for pausing workflow execution and requesting agent/human
decisions via JSON-RPC 2.0 MCP protocol.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class CheckpointQuestion(BaseModel):
    """A question/decision posed to an agent at a checkpoint."""

    question_text: str = Field(description="Human-readable question")
    question_type: str = Field(
        description="Question type: single_choice, multi_choice, free_text, yes_no"
    )
    options: Optional[list[str]] = Field(default=None, description="Available choices")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class CheckpointDecision(BaseModel):
    """Agent's response to a checkpoint question."""

    choice: Optional[str] = Field(default=None, description="Selected option (single_choice)")
    choices: Optional[list[str]] = Field(default=None, description="Selected options (multi_choice)")
    text: Optional[str] = Field(default=None, description="Free-form response text")
    confirmed: bool = Field(default=False, description="For yes_no questions")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def is_valid(self) -> bool:
        """Check if decision contains at least one response."""
        return any([self.choice, self.choices, self.text, self.confirmed])


class CheckpointRequest(BaseModel):
    """Request sent to agent via MCP for a checkpoint."""

    checkpoint_id: str = Field(description="Unique checkpoint instance ID")
    execution_id: str = Field(description="Execution ID this checkpoint belongs to")
    workflow_name: str = Field(description="Name of the workflow")
    step_name: str = Field(description="Name of step that triggered checkpoint")
    question: CheckpointQuestion
    timeout_seconds: int = Field(default=300, description="Response timeout")
    context: dict[str, Any] = Field(default_factory=dict, description="Workflow context/state")

    def to_mcp_request(self) -> dict[str, Any]:
        """Convert to MCP JSON-RPC 2.0 request format for transport.

        Returns:
            Dict suitable for JSON-RPC method parameter
        """
        return {
            "checkpoint_id": self.checkpoint_id,
            "execution_id": self.execution_id,
            "workflow": self.workflow_name,
            "step": self.step_name,
            "question": self.question.model_dump(),
            "timeout_seconds": self.timeout_seconds,
            "context": self.context,
        }


class CheckpointResponse(BaseModel):
    """Response received from agent via MCP for a checkpoint."""

    checkpoint_id: str
    execution_id: str
    decision: CheckpointDecision
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp of response")

    @staticmethod
    def from_mcp_response(data: dict[str, Any]) -> "CheckpointResponse":
        """Create CheckpointResponse from MCP JSON-RPC response.

        Args:
            data: Response dict from MCP

        Returns:
            CheckpointResponse instance
        """
        return CheckpointResponse(
            checkpoint_id=data.get("checkpoint_id"),
            execution_id=data.get("execution_id"),
            decision=CheckpointDecision(**data.get("decision", {})),
            timestamp=data.get("timestamp"))


class CheckpointProtocol:
    """Protocol manager for checkpoint communication with agents."""

    def __init__(self, mcp_client=None):
        """Initialize checkpoint protocol.

        Args:
            mcp_client: MCP client for sending requests (optional for testing)
        """
        self.mcp_client = mcp_client

    async def request_decision(
        self,
        checkpoint_request: CheckpointRequest) -> Optional[CheckpointResponse]:
        """Send checkpoint request to agent and wait for response.

        Args:
            checkpoint_request: The request to send

        Returns:
            CheckpointResponse if response received, None if timeout
        """
        if not self.mcp_client:
            raise RuntimeError("MCP client not configured for checkpoint requests")

        try:
            response_data = await self.mcp_client.call_tool(
                "workflow_checkpoint",
                checkpoint_request.to_mcp_request())
            return CheckpointResponse.from_mcp_response(response_data)
        except Exception as e:
            raise RuntimeError(f"Failed to request checkpoint decision: {e}")

    def validate_decision(
        self,
        decision: CheckpointDecision,
        question: CheckpointQuestion) -> tuple[bool, Optional[str]]:
        """Validate agent decision against question constraints.

        Args:
            decision: The decision to validate
            question: The original question

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not decision.is_valid():
            return False, "Decision contains no response"

        if question.question_type == "single_choice":
            if not decision.choice:
                return False, "single_choice requires 'choice' field"
            if question.options and decision.choice not in question.options:
                return False, f"'{decision.choice}' not in available options"

        elif question.question_type == "multi_choice":
            if not decision.choices:
                return False, "multi_choice requires 'choices' field"
            if question.options:
                invalid = set(decision.choices) - set(question.options)
                if invalid:
                    return False, f"Invalid choices: {invalid}"

        elif question.question_type == "yes_no":
            if not isinstance(decision.confirmed, bool):
                return False, "yes_no requires boolean 'confirmed' field"

        elif question.question_type == "free_text":
            if not decision.text:
                return False, "free_text requires 'text' field"

        return True, None
