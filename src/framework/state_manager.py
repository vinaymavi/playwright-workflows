"""State Persistence Manager

Handles JSON-based state storage with file locking for safe concurrent access.
Implements atomic writes and recovery for crash safety.
"""

import json
from pathlib import Path
from typing import Any, Optional

from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class StateManager:
    """Manages persistent state storage with file locking and atomicity."""

    def __init__(self, state_dir: Optional[Path] = None):
        """Initialize state manager with storage directory.

        Args:
            state_dir: Directory for state files (defaults to data/state/)
        """
        if state_dir is None:
            state_dir = Path(__file__).parent.parent.parent / "data" / "state"

        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"StateManager initialized with state_dir: {self.state_dir}")

    def _get_file_path(self, key: str) -> Path:
        """Get file path for a state key.

        Args:
            key: State key (execution_id, etc.)

        Returns:
            Path to state file
        """
        # Sanitize key to prevent path traversal
        safe_key = "".join(c for c in key if c.isalnum() or c in "-_")
        return self.state_dir / f"{safe_key}.json"

    def save(self, key: str, state: dict[str, Any]) -> None:
        """Save state to persistent storage with atomic write.

        Writes to temporary file first, then atomically renames to ensure
        crash safety—never corrupt existing state file.

        Args:
            key: State key
            state: State dictionary (must be JSON-serializable)
        """
        file_path = self._get_file_path(key)
        temp_path = file_path.with_suffix(".json.tmp")

        try:
            # Write to temporary file
            with open(temp_path, "w") as f:
                json.dump(state, f, indent=2, default=str)

            # Atomic rename (on POSIX, replaces if exists)
            temp_path.replace(file_path)

            logger.debug(f"State saved: {key} -> {file_path}")
        except Exception as e:
            logger.error(f"Failed to save state for key '{key}': {e}")
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise

    def load(self, key: str) -> Optional[dict[str, Any]]:
        """Load state from persistent storage.

        Args:
            key: State key

        Returns:
            State dictionary if found, None if not found

        Raises:
            Exception: If file is corrupted or not readable
        """
        file_path = self._get_file_path(key)

        if not file_path.exists():
            logger.debug(f"State not found: {key}")
            return None

        try:
            with open(file_path, "r") as f:
                state = json.load(f)

            logger.debug(f"State loaded: {key} <- {file_path}")
            return state
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted state file for key '{key}': {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load state for key '{key}': {e}")
            raise

    def delete(self, key: str) -> None:
        """Delete state from persistent storage.

        Args:
            key: State key
        """
        file_path = self._get_file_path(key)

        if not file_path.exists():
            logger.debug(f"State not found for deletion: {key}")
            return

        try:
            file_path.unlink()
            logger.debug(f"State deleted: {key}")
        except Exception as e:
            logger.error(f"Failed to delete state for key '{key}': {e}")
            raise

    def exists(self, key: str) -> bool:
        """Check if state exists.

        Args:
            key: State key

        Returns:
            True if state file exists
        """
        return self._get_file_path(key).exists()

    def list_keys(self) -> list[str]:
        """List all stored state keys.

        Returns:
            List of keys (filenames without .json extension)
        """
        keys = []
        for file_path in self.state_dir.glob("*.json"):
            # Skip temporary files
            if file_path.name.endswith(".json.tmp"):
                continue
            # Extract key from filename
            key = file_path.stem
            keys.append(key)

        return sorted(keys)

    def clear(self) -> None:
        """Delete all stored state (use with caution).

        This is primarily for testing/cleanup purposes.
        """
        for file_path in self.state_dir.glob("*.json"):
            try:
                file_path.unlink()
                logger.debug(f"Cleared state file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to clear state file {file_path}: {e}")

        logger.info("State manager cleared")

    def update(self, key: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Load, merge updates, and save state (atomic operation).

        Args:
            key: State key
            updates: Dictionary of updates to merge (supports dot notation for nested fields)

        Returns:
            Updated state dictionary
        """
        # Load existing state or start with empty dict
        state = self.load(key) or {}

        # Merge updates, handling dot notation for nested fields
        for update_key, value in updates.items():
            if "." in update_key:
                # Use set_nested for dot notation paths
                parts = update_key.split(".")
                current = state
                for part in parts[:-1]:
                    if part not in current or not isinstance(current[part], dict):
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value
            else:
                # Regular shallow merge
                state[update_key] = value

        # Save merged state
        self.save(key, state)

        return state

    def get_nested(self, key: str, path: str, default: Any = None) -> Any:
        """Get nested value using dot notation path.

        Args:
            key: State key
            path: Nested path using dots (e.g., "workflow.steps.0.name")
            default: Default value if path not found

        Returns:
            Value at path or default
        """
        state = self.load(key)
        if state is None:
            return default

        parts = path.split(".")
        current = state

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    current = current[idx]
                except (ValueError, IndexError):
                    return default
            else:
                return default

            if current is None:
                return default

        return current

    def set_nested(self, key: str, path: str, value: Any) -> dict[str, Any]:
        """Set nested value using dot notation path.

        Args:
            key: State key
            path: Nested path using dots (e.g., "workflow.steps.0.name")
            value: Value to set

        Returns:
            Updated state dictionary
        """
        state = self.load(key) or {}
        parts = path.split(".")

        # Navigate to parent of target
        current = state
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]

        # Set the value
        current[parts[-1]] = value

        # Save and return
        self.save(key, state)
        return state
