"""Unit Tests for MockAgentClient

Tests the mock agent client fixture used for testing checkpoint workflows.
"""

import pytest
import asyncio
from datetime import datetime

from src.framework.checkpoint import (
    CheckpointQuestion,
    CheckpointDecision,
    CheckpointRequest,
)
from tests.fixtures.mock_agent_client import (
    MockAgentClient,
    CheckpointDecisionStrategy,
    MockAgentClientFixture,
)


class TestCheckpointDecisionStrategy:
    """Tests for decision strategy configuration."""

    def test_default_strategy(self):
        """Verify default strategy is auto-approve with no delay."""
        strategy = CheckpointDecisionStrategy()
        assert strategy.auto_approve is True
        assert strategy.decision_delay_ms == 0
        assert strategy.approval_choice == "proceed"
        assert strategy.rejection_choice == "cancel"
        assert strategy.response_overrides == {}

    def test_custom_strategy(self):
        """Test custom strategy configuration."""
        overrides = {"cp1": CheckpointDecision(choice="custom")}
        strategy = CheckpointDecisionStrategy(
            decision_delay_ms=500,
            auto_approve=False,
            approval_choice="approve",
            rejection_choice="deny",
            response_overrides=overrides,
        )
        assert strategy.decision_delay_ms == 500
        assert strategy.auto_approve is False
        assert strategy.approval_choice == "approve"
        assert strategy.rejection_choice == "deny"
        assert strategy.response_overrides == overrides


class TestMockAgentClientBasic:
    """Basic tests for MockAgentClient initialization and state."""

    def test_initialization(self):
        """Test client initialization with default strategy."""
        client = MockAgentClient()
        assert client.strategy is not None
        assert client.strategy.auto_approve is True
        assert client.checkpoint_history == []
        assert client.resolved_checkpoints == {}
        assert client.pending_checkpoints == {}

    def test_initialization_with_custom_strategy(self):
        """Test client initialization with custom strategy."""
        strategy = CheckpointDecisionStrategy(auto_approve=False, decision_delay_ms=100)
        client = MockAgentClient(strategy)
        assert client.strategy == strategy
        assert client.strategy.auto_approve is False
        assert client.strategy.decision_delay_ms == 100


class TestMockAgentClientAutoApprove:
    """Tests for auto-approval behavior."""

    @pytest.mark.asyncio
    async def test_auto_approve_single_choice(self):
        """Test auto-approval for single choice question."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(auto_approve=True, approval_choice="proceed")
        )

        question = CheckpointQuestion(
            question_text="Proceed?",
            question_type="single_choice",
            options=["proceed", "cancel"],
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await client.resolve_checkpoint("cp1", request)

        assert response.checkpoint_id == "cp1"
        assert response.execution_id == "exec1"
        assert response.decision.choice == "proceed"
        assert response.decision.is_valid()

    @pytest.mark.asyncio
    async def test_auto_approve_yes_no(self):
        """Test auto-approval for yes/no question."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(auto_approve=True)
        )

        question = CheckpointQuestion(
            question_text="Continue?",
            question_type="yes_no",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await client.resolve_checkpoint("cp1", request)

        assert response.decision.confirmed is True

    @pytest.mark.asyncio
    async def test_auto_approve_multi_choice(self):
        """Test auto-approval for multi-choice question."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(auto_approve=True)
        )

        question = CheckpointQuestion(
            question_text="Select options:",
            question_type="multi_choice",
            options=["option_a", "option_b", "option_c"],
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await client.resolve_checkpoint("cp1", request)

        assert response.decision.choices == ["option_a", "option_b", "option_c"]

    @pytest.mark.asyncio
    async def test_auto_approve_free_text(self):
        """Test auto-approval for free text question."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(auto_approve=True)
        )

        question = CheckpointQuestion(
            question_text="Provide feedback:",
            question_type="free_text",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await client.resolve_checkpoint("cp1", request)

        assert response.decision.text == "approved"


class TestMockAgentClientReject:
    """Tests for rejection behavior."""

    @pytest.mark.asyncio
    async def test_reject_single_choice(self):
        """Test rejection for single choice question."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(auto_approve=False, rejection_choice="cancel")
        )

        question = CheckpointQuestion(
            question_text="Proceed?",
            question_type="single_choice",
            options=["proceed", "cancel"],
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await client.resolve_checkpoint("cp1", request)

        assert response.decision.choice == "cancel"

    @pytest.mark.asyncio
    async def test_reject_yes_no(self):
        """Test rejection for yes/no question."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(auto_approve=False)
        )

        question = CheckpointQuestion(
            question_text="Continue?",
            question_type="yes_no",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await client.resolve_checkpoint("cp1", request)

        assert response.decision.confirmed is False

    @pytest.mark.asyncio
    async def test_reject_multi_choice(self):
        """Test rejection for multi-choice question (empty selection)."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(auto_approve=False)
        )

        question = CheckpointQuestion(
            question_text="Select options:",
            question_type="multi_choice",
            options=["option_a", "option_b"],
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await client.resolve_checkpoint("cp1", request)

        assert response.decision.choices == []


class TestMockAgentClientDelay:
    """Tests for response delay simulation."""

    @pytest.mark.asyncio
    async def test_no_delay_by_default(self):
        """Verify no delay by default."""
        client = MockAgentClient()

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="yes_no",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        start = datetime.now()
        await client.resolve_checkpoint("cp1", request)
        elapsed_ms = (datetime.now() - start).total_seconds() * 1000

        # Should be nearly instant
        assert elapsed_ms < 50  # Generous tolerance

    @pytest.mark.asyncio
    async def test_delay_simulation(self):
        """Test that delay is respected."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(decision_delay_ms=100)
        )

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="yes_no",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        start = datetime.now()
        await client.resolve_checkpoint("cp1", request)
        elapsed_ms = (datetime.now() - start).total_seconds() * 1000

        # Should delay approximately 100ms (allow 20ms tolerance for test variability)
        assert 80 <= elapsed_ms < 150


class TestMockAgentClientOverrides:
    """Tests for decision overrides."""

    @pytest.mark.asyncio
    async def test_override_single_checkpoint(self):
        """Test overriding decision for a specific checkpoint."""
        custom_decision = CheckpointDecision(choice="custom_choice")
        client = MockAgentClient(
            CheckpointDecisionStrategy(
                auto_approve=True,
                response_overrides={"cp1": custom_decision}
            )
        )

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="single_choice",
            options=["custom_choice", "other"],
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response = await client.resolve_checkpoint("cp1", request)

        assert response.decision.choice == "custom_choice"

    @pytest.mark.asyncio
    async def test_multiple_overrides(self):
        """Test different overrides for different checkpoints."""
        decision1 = CheckpointDecision(choice="choice1")
        decision2 = CheckpointDecision(choice="choice2")
        client = MockAgentClient(
            CheckpointDecisionStrategy(
                response_overrides={"cp1": decision1, "cp2": decision2}
            )
        )

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="single_choice",
            options=["choice1", "choice2"],
        )

        request1 = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        request2 = CheckpointRequest(
            checkpoint_id="cp2",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        response1 = await client.resolve_checkpoint("cp1", request1)
        response2 = await client.resolve_checkpoint("cp2", request2)

        assert response1.decision.choice == "choice1"
        assert response2.decision.choice == "choice2"

    def test_set_override_after_init(self):
        """Test setting override after client initialization."""
        client = MockAgentClient()
        decision = CheckpointDecision(choice="override")

        client.set_override_decision("cp1", decision)

        assert client.strategy.response_overrides["cp1"] == decision

    def test_clear_overrides(self):
        """Test clearing all overrides."""
        decision = CheckpointDecision(choice="override")
        client = MockAgentClient(
            CheckpointDecisionStrategy(response_overrides={"cp1": decision})
        )

        client.clear_overrides()

        assert client.strategy.response_overrides == {}


class TestMockAgentClientHistoryTracking:
    """Tests for checkpoint history tracking."""

    @pytest.mark.asyncio
    async def test_history_tracking(self):
        """Verify checkpoints are tracked in history."""
        client = MockAgentClient()

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="yes_no",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        await client.resolve_checkpoint("cp1", request)

        history = client.get_checkpoint_history()
        assert len(history) == 1
        assert history[0]["checkpoint_id"] == "cp1"
        assert history[0]["request"]["checkpoint_id"] == "cp1"
        assert "response" in history[0]
        assert "resolved_at" in history[0]

    @pytest.mark.asyncio
    async def test_multiple_checkpoints_in_history(self):
        """Verify multiple checkpoints are tracked."""
        client = MockAgentClient()

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="yes_no",
        )

        for i in range(3):
            request = CheckpointRequest(
                checkpoint_id=f"cp{i}",
                execution_id="exec1",
                workflow_name="TestWorkflow",
                step_name="test_step",
                question=question,
                timeout_seconds=300,
            )
            await client.resolve_checkpoint(f"cp{i}", request)

        history = client.get_checkpoint_history()
        assert len(history) == 3
        assert [h["checkpoint_id"] for h in history] == ["cp0", "cp1", "cp2"]

    def test_get_checkpoint_request(self):
        """Test retrieving stored checkpoint request."""
        client = MockAgentClient()

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="yes_no",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        # Add to pending (normally done during resolve_checkpoint)
        client.pending_checkpoints["cp1"] = request

        retrieved = client.get_checkpoint_request("cp1")
        assert retrieved == request

    def test_get_checkpoint_request_not_found(self):
        """Test retrieving non-existent checkpoint request."""
        client = MockAgentClient()
        retrieved = client.get_checkpoint_request("nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_checkpoint_decision(self):
        """Test retrieving checkpoint decision."""
        client = MockAgentClient()

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="yes_no",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        await client.resolve_checkpoint("cp1", request)

        decision = client.get_checkpoint_decision("cp1")
        assert decision is not None
        assert decision.confirmed is True

    def test_get_checkpoint_decision_not_found(self):
        """Test retrieving non-existent checkpoint decision."""
        client = MockAgentClient()
        decision = client.get_checkpoint_decision("nonexistent")
        assert decision is None


class TestMockAgentClientReset:
    """Tests for client reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_history(self):
        """Test that reset clears history."""
        client = MockAgentClient()

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="yes_no",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        await client.resolve_checkpoint("cp1", request)
        assert len(client.get_checkpoint_history()) == 1

        client.reset()
        assert len(client.get_checkpoint_history()) == 0

    @pytest.mark.asyncio
    async def test_reset_clears_resolved(self):
        """Test that reset clears resolved checkpoints."""
        client = MockAgentClient()

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="yes_no",
        )

        request = CheckpointRequest(
            checkpoint_id="cp1",
            execution_id="exec1",
            workflow_name="TestWorkflow",
            step_name="test_step",
            question=question,
            timeout_seconds=300,
        )

        await client.resolve_checkpoint("cp1", request)
        assert client.get_checkpoint_decision("cp1") is not None

        client.reset()
        assert client.get_checkpoint_decision("cp1") is None

    def test_reset_clears_overrides(self):
        """Test that reset clears overrides."""
        decision = CheckpointDecision(choice="override")
        client = MockAgentClient(
            CheckpointDecisionStrategy(response_overrides={"cp1": decision})
        )

        assert "cp1" in client.strategy.response_overrides

        client.reset()
        assert client.strategy.response_overrides == {}


class TestMockAgentClientStatistics:
    """Tests for statistics tracking."""

    @pytest.mark.asyncio
    async def test_statistics_with_approvals(self):
        """Test statistics tracking for approvals."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(auto_approve=True, approval_choice="proceed")
        )

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="single_choice",
            options=["proceed", "cancel"],
        )

        for i in range(3):
            request = CheckpointRequest(
                checkpoint_id=f"cp{i}",
                execution_id="exec1",
                workflow_name="TestWorkflow",
                step_name="test_step",
                question=question,
                timeout_seconds=300,
            )
            await client.resolve_checkpoint(f"cp{i}", request)

        stats = client.get_statistics()
        assert stats["total_checkpoints"] == 3
        assert stats["approvals"] == 3
        assert stats["rejections"] == 0

    @pytest.mark.asyncio
    async def test_statistics_with_rejections(self):
        """Test statistics tracking for rejections."""
        client = MockAgentClient(
            CheckpointDecisionStrategy(auto_approve=False, rejection_choice="cancel")
        )

        question = CheckpointQuestion(
            question_text="Test?",
            question_type="single_choice",
            options=["proceed", "cancel"],
        )

        for i in range(2):
            request = CheckpointRequest(
                checkpoint_id=f"cp{i}",
                execution_id="exec1",
                workflow_name="TestWorkflow",
                step_name="test_step",
                question=question,
                timeout_seconds=300,
            )
            await client.resolve_checkpoint(f"cp{i}", request)

        stats = client.get_statistics()
        assert stats["total_checkpoints"] == 2
        assert stats["approvals"] == 0
        assert stats["rejections"] == 2


class TestMockAgentClientFixture:
    """Tests for MockAgentClientFixture helper."""

    def test_fixture_initialization(self):
        """Test fixture initialization."""
        fixture = MockAgentClientFixture()
        assert fixture.client is not None
        assert isinstance(fixture.client, MockAgentClient)

    def test_fixture_with_auto_approve(self):
        """Test fixture auto-approve configuration."""
        fixture = MockAgentClientFixture().with_auto_approve(True)
        assert fixture.client.strategy.auto_approve is True

        fixture.with_auto_approve(False)
        assert fixture.client.strategy.auto_approve is False

    def test_fixture_with_delay(self):
        """Test fixture delay configuration."""
        fixture = MockAgentClientFixture().with_delay(500)
        assert fixture.client.strategy.decision_delay_ms == 500

    def test_fixture_with_rejection(self):
        """Test fixture rejection configuration."""
        fixture = MockAgentClientFixture().with_rejection()
        assert fixture.client.strategy.auto_approve is False

    def test_fixture_chaining(self):
        """Test that fixture methods can be chained."""
        fixture = MockAgentClientFixture().with_auto_approve(False).with_delay(200)
        assert fixture.client.strategy.auto_approve is False
        assert fixture.client.strategy.decision_delay_ms == 200

    def test_fixture_get_client(self):
        """Test getting client from fixture."""
        fixture = MockAgentClientFixture().with_auto_approve(True)
        client = fixture.get_client()
        assert client == fixture.client
        assert client.strategy.auto_approve is True

    def test_fixture_with_override(self):
        """Test fixture with custom override."""
        decision = CheckpointDecision(choice="custom")
        fixture = MockAgentClientFixture().with_override("cp1", decision)
        assert fixture.client.strategy.response_overrides["cp1"] == decision
