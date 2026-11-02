"""Checkpoint Store - Persist checkpoints to disk for recovery and query.

This module provides JSON-based persistence for checkpoints, enabling:
- Quick lookup of pending checkpoints
- Recovery after process crash or timeout
- Audit trail of all checkpoint decisions
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.utils.logging import setup_logger


class CheckpointStore:
    """Manages persistent storage of checkpoints to JSON files."""

    def __init__(self, store_dir: str = "data/checkpoints"):
        """Initialize checkpoint store.

        Args:
            store_dir: Directory where checkpoint files are stored
        """
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.logger = setup_logger(__name__)

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get the file path for a checkpoint.

        Args:
            checkpoint_id: The checkpoint UUID

        Returns:
            Path to the checkpoint JSON file
        """
        return self.store_dir / f"{checkpoint_id}.json"

    def _get_execution_index_path(self, execution_id: str) -> Path:
        """Get the file path for an execution's checkpoint index.

        Args:
            execution_id: The execution UUID

        Returns:
            Path to the execution's checkpoint index file
        """
        return self.store_dir / f"execution_{execution_id}_index.json"

    def save(self, checkpoint_data: dict[str, Any]) -> str:
        """Save a checkpoint to disk.

        Args:
            checkpoint_data: Dictionary containing checkpoint information

        Returns:
            The checkpoint_id of the saved checkpoint

        Raises:
            ValueError: If checkpoint_data missing required fields
        """
        if "checkpoint_id" not in checkpoint_data:
            checkpoint_data["checkpoint_id"] = str(uuid.uuid4())

        if "execution_id" not in checkpoint_data:
            raise ValueError("checkpoint_data must include 'execution_id'")

        if "created_at" not in checkpoint_data:
            checkpoint_data["created_at"] = datetime.utcnow().isoformat() + "Z"

        checkpoint_id = checkpoint_data["checkpoint_id"]
        execution_id = checkpoint_data["execution_id"]

        # Save checkpoint file
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        try:
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint_data, f, indent=2)
            self.logger.info(f"Saved checkpoint {checkpoint_id}")
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint {checkpoint_id}: {e}")
            raise

        # Update execution index
        self._update_execution_index(execution_id, checkpoint_id)

        return checkpoint_id

    def load(self, checkpoint_id: str) -> Optional[dict[str, Any]]:
        """Load a checkpoint from disk.

        Args:
            checkpoint_id: The checkpoint UUID

        Returns:
            Checkpoint data dictionary, or None if not found
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)

        if not checkpoint_path.exists():
            self.logger.warning(f"Checkpoint {checkpoint_id} not found")
            return None

        try:
            with open(checkpoint_path, "r") as f:
                data = json.load(f)
            self.logger.info(f"Loaded checkpoint {checkpoint_id}")
            return data
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def get_pending(self, execution_id: str) -> list[dict[str, Any]]:
        """Get all pending checkpoints for an execution.

        Args:
            execution_id: The execution UUID

        Returns:
            List of pending checkpoint data dictionaries
        """
        pending = []
        index_path = self._get_execution_index_path(execution_id)

        if not index_path.exists():
            return pending

        try:
            with open(index_path, "r") as f:
                index_data = json.load(f)

            checkpoint_ids = index_data.get("checkpoints", [])

            for cp_id in checkpoint_ids:
                checkpoint = self.load(cp_id)
                if checkpoint and checkpoint.get("status") == "pending":
                    pending.append(checkpoint)

            self.logger.info(f"Found {len(pending)} pending checkpoints for execution {execution_id}")
            return pending

        except Exception as e:
            self.logger.error(f"Failed to get pending checkpoints for {execution_id}: {e}")
            return pending

    def mark_resolved(self, checkpoint_id: str, decision: dict[str, Any], timestamp: Optional[str] = None) -> bool:
        """Mark a checkpoint as resolved with agent decision.

        Args:
            checkpoint_id: The checkpoint UUID
            decision: The agent's decision
            timestamp: Resolution timestamp (ISO8601, defaults to now)

        Returns:
            True if successful, False otherwise
        """
        checkpoint = self.load(checkpoint_id)
        if not checkpoint:
            self.logger.error(f"Cannot mark unknown checkpoint {checkpoint_id} as resolved")
            return False

        checkpoint["status"] = "resolved"
        checkpoint["response"] = decision
        checkpoint["resolved_at"] = timestamp or (datetime.utcnow().isoformat() + "Z")

        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        try:
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint, f, indent=2)
            self.logger.info(f"Marked checkpoint {checkpoint_id} as resolved")
            return True
        except Exception as e:
            self.logger.error(f"Failed to mark checkpoint {checkpoint_id} as resolved: {e}")
            return False

    def mark_timeout(self, checkpoint_id: str, timeout_strategy: str, timestamp: Optional[str] = None) -> bool:
        """Mark a checkpoint as timed out.

        Args:
            checkpoint_id: The checkpoint UUID
            timeout_strategy: How to handle timeout ('keep_alive' or 'replay')
            timestamp: Timeout timestamp (ISO8601, defaults to now)

        Returns:
            True if successful, False otherwise
        """
        checkpoint = self.load(checkpoint_id)
        if not checkpoint:
            self.logger.error(f"Cannot mark unknown checkpoint {checkpoint_id} as timed out")
            return False

        checkpoint["status"] = "timeout"
        checkpoint["timeout_strategy"] = timeout_strategy
        checkpoint["timeout_at"] = timestamp or (datetime.utcnow().isoformat() + "Z")

        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        try:
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint, f, indent=2)
            self.logger.info(f"Marked checkpoint {checkpoint_id} as timed out ({timeout_strategy})")
            return True
        except Exception as e:
            self.logger.error(f"Failed to mark checkpoint {checkpoint_id} as timed out: {e}")
            return False

    def query_execution_checkpoints(self, execution_id: str, status: Optional[str] = None) -> list[dict[str, Any]]:
        """Query all checkpoints for an execution, optionally filtered by status.

        Args:
            execution_id: The execution UUID
            status: Optional status filter ('pending', 'resolved', 'timeout', 'error')

        Returns:
            List of matching checkpoint data dictionaries
        """
        results = []
        index_path = self._get_execution_index_path(execution_id)

        if not index_path.exists():
            return results

        try:
            with open(index_path, "r") as f:
                index_data = json.load(f)

            checkpoint_ids = index_data.get("checkpoints", [])

            for cp_id in checkpoint_ids:
                checkpoint = self.load(cp_id)
                if checkpoint:
                    if status is None or checkpoint.get("status") == status:
                        results.append(checkpoint)

            self.logger.info(f"Query: Found {len(results)} checkpoints for {execution_id} (status={status})")
            return results

        except Exception as e:
            self.logger.error(f"Failed to query checkpoints for {execution_id}: {e}")
            return results

    def list_all_checkpoints(self) -> list[str]:
        """List all checkpoint IDs in the store.

        Returns:
            List of checkpoint file names
        """
        try:
            checkpoints = [f.stem for f in self.store_dir.glob("*.json") if not f.name.startswith("execution_")]
            self.logger.info(f"Listed {len(checkpoints)} checkpoints in store")
            return checkpoints
        except Exception as e:
            self.logger.error(f"Failed to list checkpoints: {e}")
            return []

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint from storage (use with caution - audit trail loss).

        Args:
            checkpoint_id: The checkpoint UUID

        Returns:
            True if deleted, False if not found or error
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)

        if not checkpoint_path.exists():
            self.logger.warning(f"Checkpoint {checkpoint_id} not found for deletion")
            return False

        try:
            checkpoint_path.unlink()
            self.logger.info(f"Deleted checkpoint {checkpoint_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            return False

    def _update_execution_index(self, execution_id: str, checkpoint_id: str) -> None:
        """Update the execution's checkpoint index with a new checkpoint.

        Args:
            execution_id: The execution UUID
            checkpoint_id: The checkpoint UUID to add
        """
        index_path = self._get_execution_index_path(execution_id)

        index_data = {"execution_id": execution_id, "checkpoints": []}

        if index_path.exists():
            try:
                with open(index_path, "r") as f:
                    index_data = json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to read execution index for {execution_id}: {e}")

        if checkpoint_id not in index_data.get("checkpoints", []):
            index_data["checkpoints"].append(checkpoint_id)

        try:
            with open(index_path, "w") as f:
                json.dump(index_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to update execution index for {execution_id}: {e}")


# Global store instance
_store_instance: Optional[CheckpointStore] = None


def get_checkpoint_store(store_dir: str = "data/checkpoints") -> CheckpointStore:
    """Get or create the global checkpoint store instance.

    Args:
        store_dir: Directory where checkpoint files are stored (only used on first call)

    Returns:
        CheckpointStore instance
    """
    global _store_instance
    if _store_instance is None:
        _store_instance = CheckpointStore(store_dir)
    return _store_instance
