"""Unit tests for checkpoint module."""

import pytest
from unittest.mock import MagicMock

from src.framework.checkpoint import (
    CheckpointDecision,
    CheckpointProtocol,
    CheckpointQuestion,
    CheckpointRequest,
    CheckpointResponse,
)


class TestCheckpointQuestion:
    """Test CheckpointQuestion pydantic model."""

    def test_question_creation(self):
        """Test basic question creation."""
        question = CheckpointQuestion(
            question_text="Should we proceed with form submission?",
            question_type="yes_no",
        )
        assert question.question_text == "Should we proceed with form submission?"
        assert question.question_type == "yes_no"

    def test_question_with_options(self):
        """Test question with options."""
        question = CheckpointQuestion(
            question_text="Select action",
            question_type="single_choice",
            options=["proceed", "retry", "cancel"],
        )
        assert len(question.options) == 3
        assert "proceed" in question.options

    def test_question_serialization(self):
        """Test JSON serialization."""
        question = CheckpointQuestion(
            question_text="Continue?",
            question_type="yes_no",
        )
        json_str = question.model_dump_json()
        assert "Continue?" in json_str
        assert "yes_no" in json_str


class TestCheckpointDecision:
    """Test CheckpointDecision pydantic model."""

    def test_decision_single_choice(self):
        """Test single choice decision."""
        decision = CheckpointDecision(choice="proceed")
        assert decision.choice == "proceed"
        assert decision.is_valid() is True

    def test_decision_yes_no(self):
        """Test yes_no decision."""
        decision = CheckpointDecision(confirmed=True)
        assert decision.confirmed is True
        assert decision.is_valid() is True

    def test_decision_free_text(self):
        """Test free text decision."""
        decision = CheckpointDecision(text="Corrected value: John Doe")
        assert decision.text == "Corrected value: John Doe"
        assert decision.is_valid() is True

    def test_decision_multi_choice(self):
        """Test multi-choice decision."""
        decision = CheckpointDecision(choices=["option1", "option2"])
        assert len(decision.choices) == 2
        assert decision.is_valid() is True

    def test_invalid_empty_decision(self):
        """Test that empty decision is invalid."""
        decision = CheckpointDecision()
        assert decision.is_valid() is False

    def test_decision_serialization(self):
        """Test JSON serialization."""
        decision = CheckpointDecision(choice="yes")
        json_str = decision.model_dump_json()
        assert "yes" in json_str


class TestCheckpointRequest:
    """Test CheckpointRequest pydantic model."""

    def test_request_creation(self):
        """Test checkpoint request creation."""
        question = CheckpointQuestion(
            question_text="Proceed?",
            question_type="yes_no",
        )
        request = CheckpointRequest(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            workflow_name="login_form",
            step_name="verify_credentials",
            question=question,
        )
        assert request.checkpoint_id == "cp-001"
        assert request.execution_id == "exec-001"
        assert request.workflow_name == "login_form"

    def test_request_with_context_and_timeout(self):
        """Test request with context and timeout."""
        question = CheckpointQuestion(
            question_text="Approve?",
            question_type="yes_no",
        )
        request = CheckpointRequest(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            workflow_name="form_submit",
            step_name="final_check",
            question=question,
            timeout_seconds=600,
            context={"form_id": "form-123"},
        )
        assert request.timeout_seconds == 600
        assert request.context["form_id"] == "form-123"

    def test_request_to_mcp_format(self):
        """Test conversion to MCP request format."""
        question = CheckpointQuestion(
            question_text="Approve?",
            question_type="yes_no",
        )
        request = CheckpointRequest(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            workflow_name="test_wf",
            step_name="test_step",
            question=question,
        )
        mcp_request = request.to_mcp_request()
        assert mcp_request["checkpoint_id"] == "cp-001"
        assert mcp_request["execution_id"] == "exec-001"
        assert "question" in mcp_request


class TestCheckpointResponse:
    """Test CheckpointResponse pydantic model."""

    def test_response_creation(self):
        """Test checkpoint response creation."""
        decision = CheckpointDecision(confirmed=True)
        response = CheckpointResponse(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            decision=decision,
        )
        assert response.checkpoint_id == "cp-001"
        assert response.execution_id == "exec-001"
        assert response.decision.confirmed is True

    def test_response_with_timestamp(self):
        """Test response with timestamp."""
        decision = CheckpointDecision(choice="proceed")
        response = CheckpointResponse(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            decision=decision,
            timestamp="2024-01-01T12:00:00Z",
        )
        assert response.timestamp == "2024-01-01T12:00:00Z"

    def test_response_from_mcp_response(self):
        """Test creating response from MCP dict."""
        mcp_data = {
            "checkpoint_id": "cp-001",
            "execution_id": "exec-001",
            "decision": {"choice": "proceed"},
            "timestamp": "2024-01-01T12:00:00Z",
        }
        response = CheckpointResponse.from_mcp_response(mcp_data)
        assert response.checkpoint_id == "cp-001"
        assert response.decision.choice == "proceed"

    def test_response_serialization(self):
        """Test response serialization."""
        decision = CheckpointDecision(confirmed=True)
        response = CheckpointResponse(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            decision=decision,
        )
        json_str = response.model_dump_json()
        assert "cp-001" in json_str


class TestCheckpointProtocol:
    """Test CheckpointProtocol manager."""

    def test_protocol_initialization(self):
        """Test protocol initialization without MCP client."""
        protocol = CheckpointProtocol()
        assert protocol.mcp_client is None

    def test_protocol_with_mcp_client(self):
        """Test protocol initialization with MCP client."""
        mock_client = MagicMock()
        protocol = CheckpointProtocol(mcp_client=mock_client)
        assert protocol.mcp_client is mock_client

    def test_create_checkpoint_request(self):
        """Test creating checkpoint request."""
        protocol = CheckpointProtocol()
        question = CheckpointQuestion(
            question_text="Proceed?",
            question_type="yes_no",
        )
        request = CheckpointRequest(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            workflow_name="test",
            step_name="verify",
            question=question,
            timeout_seconds=300,
        )
        assert request.checkpoint_id == "cp-001"
        assert request.timeout_seconds == 300

    def test_validate_decision(self):
        """Test decision validation."""
        decision_valid = CheckpointDecision(confirmed=True)
        assert decision_valid.is_valid() is True

        decision_invalid = CheckpointDecision()
        assert decision_invalid.is_valid() is False

    def test_checkpoint_request_contains_metadata(self):
        """Test that checkpoint request contains all required metadata."""
        question = CheckpointQuestion(
            question_text="Verify email?",
            question_type="yes_no",
        )
        request = CheckpointRequest(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            workflow_name="email_verification",
            step_name="validate_email",
            question=question,
            timeout_seconds=600,
            context={"email": "test@example.com"},
        )
        assert request.checkpoint_id == "cp-001"
        assert request.execution_id == "exec-001"
        assert request.step_name == "validate_email"
        assert request.context["email"] == "test@example.com"

    def test_serialize_request_for_mcp(self):
        """Test request serialization for MCP transport."""
        question = CheckpointQuestion(
            question_text="Continue?",
            question_type="yes_no",
        )
        request = CheckpointRequest(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            workflow_name="test",
            step_name="test_step",
            question=question,
        )
        # Should be JSON-serializable
        json_data = request.model_dump()
        assert isinstance(json_data, dict)
        assert json_data["checkpoint_id"] == "cp-001"

    def test_serialize_response_for_mcp(self):
        """Test response serialization for MCP transport."""
        decision = CheckpointDecision(confirmed=True)
        response = CheckpointResponse(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            decision=decision,
        )
        # Should be JSON-serializable
        json_data = response.model_dump()
        assert isinstance(json_data, dict)
        assert json_data["checkpoint_id"] == "cp-001"
        assert json_data["decision"]["confirmed"] is True
