"""Structured JSON logging for Playwright Workflows framework."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from src.framework.execution import ExecutionContext


class JSONFormatter(logging.Formatter):
    """Format logs as JSON with execution context."""

    def __init__(self, execution_id: Optional[str] = None):
        """Initialize formatter with optional execution context."""
        super().__init__()
        self.execution_id = execution_id

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON line."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add execution context if available
        if self.execution_id:
            log_entry["execution_id"] = self.execution_id

        # Add extra fields if present (passed via extra= parameter)
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry)


def setup_logger(
    name: str,
    execution_id: Optional[str] = None,
    log_file: Optional[Path] = None,
    log_level: int = logging.INFO,
) -> logging.Logger:
    """
    Set up a structured JSON logger.

    Args:
        name: Logger name (typically __name__)
        execution_id: Execution ID for context (optional)
        log_file: File path to write logs to (optional)
        log_level: Log level (default INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Clear existing handlers
    logger.handlers.clear()

    formatter = JSONFormatter(execution_id=execution_id)

    # Console handler (stderr for logs, stdout for data)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if log_file specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_execution_event(
    logger: logging.Logger,
    event_type: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    **extra_fields,
) -> None:
    """
    Log an execution event with structured context.

    Args:
        logger: Logger instance
        event_type: Type of event (e.g., 'step_started', 'checkpoint_created')
        message: Human-readable message
        context: Optional context dict
        **extra_fields: Additional fields to include in log
    """
    fields = {
        "event_type": event_type,
        **(context or {}),
        **extra_fields,
    }
    record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )
    record.extra_fields = fields
    logger.handle(record)
