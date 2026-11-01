"""Common pytest fixtures for test suite."""

import asyncio
from pathlib import Path
from typing import Generator

import pytest

from src.utils.logging import setup_logger


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir(tmp_path) -> Generator[Path, None, None]:
    """Provide temporary directory for test files."""
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()
    yield test_data_dir


@pytest.fixture
def logger(temp_dir):
    """Provide test logger with temp directory."""
    log_file = temp_dir / "test.log"
    return setup_logger(
        name="test_logger",
        log_file=log_file,
        level="DEBUG",
    )


@pytest.fixture
def mock_execution_id() -> str:
    """Provide mock execution ID for testing."""
    return "test-exec-12345-abcde"


@pytest.fixture
def mock_workflow_config() -> dict:
    """Provide mock workflow configuration."""
    return {
        "name": "test_workflow",
        "description": "Test workflow for unit tests",
        "timeout": 300,
        "max_retries": 3,
        "checkpoint_timeout": 120,
    }
