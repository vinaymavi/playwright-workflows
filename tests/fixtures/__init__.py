"""Test fixtures for Playwright workflow automation framework."""

from .mock_page import MockPage, create_mock_page
from .mock_web_app import MockWebApp, create_mock_web_app

__all__ = [
    "MockPage",
    "create_mock_page",
    "MockWebApp",
    "create_mock_web_app",
]
