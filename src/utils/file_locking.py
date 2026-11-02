"""File locking and atomic writes for concurrent state management."""

import tempfile
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:
    # Windows fallback
    fcntl = None  # type: ignore


def atomic_write_json(file_path: Path, data: Any) -> None:
    """
    Atomically write JSON data to file using temp+rename pattern.

    Args:
        file_path: Target file path
        data: Python object to serialize as JSON

    Process:
        1. Write to temporary file in same directory
        2. Atomically rename temp to target (POSIX guarantee)
        3. Prevents partial/corrupt writes on crash
    """
    import json

    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory (ensures same filesystem)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=file_path.parent,
        delete=False,
        suffix=".tmp",
        prefix=f".{file_path.name}.") as tmp_file:
        tmp_path = Path(tmp_file.name)
        json.dump(data, tmp_file, indent=2)

    # Atomic rename (POSIX guarantee)
    try:
        tmp_path.replace(file_path)
    except Exception:
        # Cleanup temp file on error
        tmp_path.unlink(missing_ok=True)
        raise


def atomic_read_json(file_path: Path) -> Any:
    """
    Atomically read JSON data from file.

    Args:
        file_path: Target file path

    Returns:
        Parsed JSON object

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    import json

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r") as f:
        return json.load(f)


class FileLock:
    """
    File-based lock using fcntl (Unix) or Windows file locking.

    Enables process-safe concurrent access to shared files.
    """

    def __init__(self, lock_file: Path):
        """
        Initialize lock file.

        Args:
            lock_file: Path to lock file (typically next to data file with .lock suffix)
        """
        self.lock_file = lock_file
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock_handle = None

    def __enter__(self):
        """Acquire lock (blocking)."""
        self._lock_handle = open(self.lock_file, "w")
        if fcntl:
            # Unix: Use fcntl
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX)
        else:
            # Windows: Use os-level locking (basic)
            import msvcrt

            msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        return self

    def __exit__(self, *args):
        """Release lock."""
        if self._lock_handle:
            if fcntl:
                fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            self._lock_handle.close()
        self._lock_handle = None


def locked_read_json(file_path: Path) -> Any:
    """
    Read JSON file with exclusive lock.

    Args:
        file_path: Target file path

    Returns:
        Parsed JSON object
    """
    lock_file = file_path.parent / f"{file_path.name}.lock"

    with FileLock(lock_file):
        return atomic_read_json(file_path)


def locked_write_json(file_path: Path, data: Any) -> None:
    """
    Write JSON file with exclusive lock.

    Args:
        file_path: Target file path
        data: Python object to serialize as JSON
    """
    lock_file = file_path.parent / f"{file_path.name}.lock"

    with FileLock(lock_file):
        atomic_write_json(file_path, data)
