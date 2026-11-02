"""Workflow Execution Resumption Management

Handles resumption of paused or failed workflows with smart recovery strategies:
- Quick resume (<5 min): Restore browser context, continue from checkpoint
- Slow resume (>5 min): Replay steps, detect auth failures, trigger re-auth if needed

Supports both automatic resumption and manual resume via CLI.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional, Tuple

from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class ResumptionStrategy:
    """Determines resumption strategy based on execution state and time."""

    QUICK_RESUME_THRESHOLD = 300  # 5 minutes

    @staticmethod
    def determine_strategy(execution_state: dict[str, Any]) -> str:
        """Determine resume strategy based on execution age.

        Args:
            execution_state: Loaded execution state dict

        Returns:
            "quick" if last activity within 5 min, "slow" otherwise
        """
        now = time.time()
        last_activity = execution_state.get("last_activity_at", execution_state.get("started_at", now))

        # Handle ISO timestamp strings
        if isinstance(last_activity, str):
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                last_activity = dt.timestamp()
            except (ValueError, AttributeError):
                last_activity = now

        age_seconds = now - last_activity

        if age_seconds < ResumptionStrategy.QUICK_RESUME_THRESHOLD:
            return "quick"
        return "slow"


class ResumptionManager:
    """Manages workflow resumption with recovery strategies."""

    def __init__(self, execution_dir: Optional[Path] = None):
        """Initialize resumption manager.

        Args:
            execution_dir: Directory for execution state storage
        """
        if execution_dir is None:
            execution_dir = Path(__file__).parent.parent.parent / "data" / "executions"

        self.execution_dir = Path(execution_dir)
        self.execution_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ResumptionManager initialized with execution_dir: {execution_dir}")

    def load_execution_state(self, execution_id: str) -> Optional[dict[str, Any]]:
        """Load execution state from storage.

        Args:
            execution_id: Execution ID to load

        Returns:
            Execution state dict if found, None otherwise
        """
        execution_file = self.execution_dir / f"{execution_id}.json"

        if not execution_file.exists():
            logger.warning(f"Execution state not found: {execution_id}")
            return None

        try:
            with open(execution_file, "r") as f:
                state = json.load(f)

            logger.debug(f"Loaded execution state for: {execution_id}")
            return state

        except Exception as e:
            logger.error(f"Failed to load execution state: {e}", extra={"execution_id": execution_id})
            return None

    def save_execution_state(self, execution_id: str, state: dict[str, Any]) -> bool:
        """Save execution state to storage.

        Args:
            execution_id: Execution ID
            state: Execution state to save

        Returns:
            True if successful, False otherwise
        """
        execution_file = self.execution_dir / f"{execution_id}.json"
        temp_file = execution_file.with_suffix(".json.tmp")

        try:
            # Write to temp file
            with open(temp_file, "w") as f:
                json.dump(state, f, indent=2)

            # Atomic rename
            temp_file.replace(execution_file)

            logger.debug(f"Saved execution state for: {execution_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save execution state: {e}", extra={"execution_id": execution_id})
            if temp_file.exists():
                temp_file.unlink()
            return False

    def get_resumption_info(self, execution_id: str) -> Optional[dict[str, Any]]:
        """Get resumption information for an execution.

        Returns dict with:
        - execution_id
        - status
        - strategy: "quick" or "slow"
        - session_age_seconds: Time since last activity
        - last_checkpoint: Last checkpoint reached
        - completed_steps: Steps completed so far
        - total_steps: Total workflow steps

        Args:
            execution_id: Execution ID to inspect

        Returns:
            Resumption info dict or None if not found
        """
        state = self.load_execution_state(execution_id)
        if not state:
            return None

        strategy = ResumptionStrategy.determine_strategy(state)

        now = time.time()
        last_activity = state.get("last_activity_at", state.get("started_at", now))
        if isinstance(last_activity, str):
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                last_activity = dt.timestamp()
            except (ValueError, AttributeError):
                last_activity = now

        session_age = now - last_activity

        last_checkpoint = None
        checkpoints = state.get("checkpoints", [])
        if checkpoints:
            last_checkpoint = checkpoints[-1]

        return {
            "execution_id": execution_id,
            "status": state.get("status", "unknown"),
            "strategy": strategy,
            "session_age_seconds": session_age,
            "last_checkpoint": last_checkpoint,
            "completed_steps": state.get("completed_steps", 0),
            "total_steps": state.get("total_steps", 0),
            "workflow_type": state.get("workflow_type"),
            "started_at": state.get("started_at"),
            "last_activity_at": state.get("last_activity_at"),
        }

    def prepare_for_quick_resume(
        self,
        execution_id: str) -> Tuple[bool, Optional[str]]:
        """Prepare execution for quick resumption (<5 min).

        Quick resume strategy:
        - Keep browser context alive
        - Verify session cookies are still valid
        - Resume from last checkpoint

        Args:
            execution_id: Execution ID to resume

        Returns:
            Tuple of (success, message)
        """
        state = self.load_execution_state(execution_id)
        if not state:
            return False, f"Execution not found: {execution_id}"

        # Verify execution can be resumed
        status = state.get("status")
        if status not in ["paused", "pending_checkpoint", "failed"]:
            return False, f"Cannot resume execution in status: {status}"

        logger.info(
            f"Preparing quick resume for execution: {execution_id}",
            extra={"status": status}
        )

        # Update state to mark resumption
        state["resumed_at"] = time.time()
        state["resumption_strategy"] = "quick"
        state["status"] = "resuming"

        if not self.save_execution_state(execution_id, state):
            return False, "Failed to save execution state"

        return True, "Execution ready for quick resume"

    def prepare_for_slow_resume(
        self,
        execution_id: str) -> Tuple[bool, Optional[str]]:
        """Prepare execution for slow resumption (>5 min).

        Slow resume strategy:
        - Close browser context
        - Replay steps up to last checkpoint
        - Detect 401/403 auth failures
        - Trigger re-authentication if needed
        - Resume from checkpoint

        Args:
            execution_id: Execution ID to resume

        Returns:
            Tuple of (success, message)
        """
        state = self.load_execution_state(execution_id)
        if not state:
            return False, f"Execution not found: {execution_id}"

        # Verify execution can be resumed
        status = state.get("status")
        if status not in ["paused", "pending_checkpoint", "failed"]:
            return False, f"Cannot resume execution in status: {status}"

        logger.info(
            f"Preparing slow resume for execution: {execution_id}",
            extra={"status": status}
        )

        # Update state to mark resumption
        state["resumed_at"] = time.time()
        state["resumption_strategy"] = "slow"
        state["status"] = "resuming"
        state["replay_needed"] = True

        if not self.save_execution_state(execution_id, state):
            return False, "Failed to save execution state"

        return True, "Execution ready for slow resume (replay required)"

    def mark_resumption_complete(self, execution_id: str) -> bool:
        """Mark resumption as complete and update state.

        Args:
            execution_id: Execution ID

        Returns:
            True if successful
        """
        state = self.load_execution_state(execution_id)
        if not state:
            logger.warning(f"Execution not found: {execution_id}")
            return False

        state["status"] = "running"
        state["resumption_complete_at"] = time.time()

        return self.save_execution_state(execution_id, state)

    def record_recovery_event(
        self,
        execution_id: str,
        event_type: str,
        details: Optional[dict[str, Any]] = None) -> bool:
        """Record a recovery event in the execution state.

        Supported event types: session_expired, session_recovered, re_auth, replay_started, replay_complete

        Args:
            execution_id: Execution ID
            event_type: Type of recovery event
            details: Additional event details

        Returns:
            True if recorded successfully
        """
        state = self.load_execution_state(execution_id)
        if not state:
            logger.warning(f"Execution not found: {execution_id}")
            return False

        if "recovery_events" not in state:
            state["recovery_events"] = []

        event = {
            "type": event_type,
            "timestamp": time.time(),
            "details": details or {},
        }

        state["recovery_events"].append(event)

        logger.info(
            f"Recorded recovery event: {event_type}",
            extra={"execution_id": execution_id, "details": details}
        )

        return self.save_execution_state(execution_id, state)
