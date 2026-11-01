"""Mock Playwright Page object for testing without a real browser."""

from typing import Optional, Any, List, Dict
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass


@dataclass
class MockLocator:
    """Mock Playwright Locator."""

    selector: str
    _page: "MockPage"

    async def click(self, **kwargs) -> None:
        """Mock click action."""
        await self._page.on_click(self.selector)

    async def fill(self, text: str, **kwargs) -> None:
        """Mock fill action."""
        await self._page.on_fill(self.selector, text)

    async def type(self, text: str, **kwargs) -> None:
        """Mock type action (same as fill)."""
        await self._page.on_fill(self.selector, text)

    async def get_attribute(self, name: str, **kwargs) -> Optional[str]:
        """Mock get_attribute action."""
        return await self._page.on_get_attribute(self.selector, name)

    async def text_content(self, **kwargs) -> Optional[str]:
        """Mock text_content action."""
        return await self._page.on_text_content(self.selector)

    async def inner_text(self, **kwargs) -> str:
        """Mock inner_text action."""
        content = await self._page.on_text_content(self.selector)
        return content or ""

    async def is_visible(self, **kwargs) -> bool:
        """Mock is_visible action."""
        return await self._page.on_is_visible(self.selector)

    async def wait_for(self, **kwargs) -> None:
        """Mock wait_for action."""
        await self._page.on_wait_for(self.selector)

    async def is_enabled(self, **kwargs) -> bool:
        """Mock is_enabled action."""
        return await self._page.on_is_enabled(self.selector)

    async def count(self, **kwargs) -> int:
        """Mock count action."""
        return await self._page.on_count(self.selector)


class MockPage:
    """Mock Playwright Page object for testing workflows without a real browser."""

    def __init__(self):
        """Initialize the mock page with default state."""
        self.url: str = "about:blank"
        self.title: str = "Mock Page"
        self._form_data: Dict[str, str] = {}
        self._navigation_history: List[str] = []
        self._interactions: List[Dict[str, Any]] = []
        self._visible_elements: set = set()
        self._enabled_elements: set = set()
        self._element_attributes: Dict[str, Dict[str, str]] = {}
        self._element_text: Dict[str, str] = {}

    def locator(self, selector: str) -> MockLocator:
        """Get a mock locator for the given selector."""
        return MockLocator(selector, self)

    async def goto(self, url: str, **kwargs) -> None:
        """Mock goto (navigation)."""
        self.url = url
        self._navigation_history.append(url)
        self._interactions.append({"type": "goto", "url": url})

    async def content(self) -> str:
        """Mock content retrieval."""
        return f"<html><body><title>{self.title}</title></body></html>"

    async def text_content(self) -> Optional[str]:
        """Mock text content of entire page."""
        return "Mock page content"

    async def get_attribute(self, selector: str, name: str, **kwargs) -> Optional[str]:
        """Mock get_attribute on page."""
        return await self.on_get_attribute(selector, name)

    async def fill(self, selector: str, text: str, **kwargs) -> None:
        """Mock fill on page."""
        await self.on_fill(selector, text)

    async def click(self, selector: str, **kwargs) -> None:
        """Mock click on page."""
        await self.on_click(selector)

    async def type(self, selector: str, text: str, **kwargs) -> None:
        """Mock type on page."""
        await self.on_fill(selector, text)

    async def wait_for_selector(self, selector: str, **kwargs) -> Optional[MockLocator]:
        """Mock wait_for_selector."""
        await self.on_wait_for(selector)
        return self.locator(selector)

    async def wait_for_url(self, url_pattern: str, **kwargs) -> None:
        """Mock wait_for_url."""
        self._interactions.append({"type": "wait_for_url", "pattern": url_pattern})

    async def wait_for_load_state(self, state: str = "load", **kwargs) -> None:
        """Mock wait_for_load_state."""
        self._interactions.append({"type": "wait_for_load_state", "state": state})

    async def pdf(self, path: Optional[str] = None, **kwargs) -> bytes:
        """Mock PDF generation."""
        self._interactions.append({"type": "pdf", "path": path})
        return b"Mock PDF content"

    async def screenshot(self, path: Optional[str] = None, **kwargs) -> bytes:
        """Mock screenshot."""
        self._interactions.append({"type": "screenshot", "path": path})
        return b"Mock screenshot data"

    def on_screen(self) -> bool:
        """Mock check if page is on screen."""
        return True

    async def close(self) -> None:
        """Mock close."""
        self._interactions.append({"type": "close"})

    # Mock internal handlers
    async def on_click(self, selector: str) -> None:
        """Handle click interaction."""
        self._interactions.append({"type": "click", "selector": selector})

    async def on_fill(self, selector: str, text: str) -> None:
        """Handle fill interaction."""
        self._form_data[selector] = text
        self._interactions.append({"type": "fill", "selector": selector, "text": text})

    async def on_get_attribute(self, selector: str, name: str) -> Optional[str]:
        """Handle get_attribute."""
        if selector in self._element_attributes:
            return self._element_attributes[selector].get(name)
        return None

    async def on_text_content(self, selector: str) -> Optional[str]:
        """Handle text_content."""
        return self._element_text.get(selector)

    async def on_is_visible(self, selector: str) -> bool:
        """Handle is_visible."""
        return selector in self._visible_elements or selector not in self._element_text

    async def on_wait_for(self, selector: str) -> None:
        """Handle wait_for."""
        self._interactions.append({"type": "wait_for", "selector": selector})
        self._visible_elements.add(selector)

    async def on_is_enabled(self, selector: str) -> bool:
        """Handle is_enabled."""
        return selector in self._enabled_elements or True

    async def on_count(self, selector: str) -> int:
        """Handle count."""
        return 1

    # Test helper methods
    def set_element_text(self, selector: str, text: str) -> None:
        """Set text content for a selector (for testing)."""
        self._element_text[selector] = text

    def set_element_attribute(self, selector: str, name: str, value: str) -> None:
        """Set element attribute (for testing)."""
        if selector not in self._element_attributes:
            self._element_attributes[selector] = {}
        self._element_attributes[selector][name] = value

    def set_element_visible(self, selector: str, visible: bool = True) -> None:
        """Set element visibility (for testing)."""
        if visible:
            self._visible_elements.add(selector)
        else:
            self._visible_elements.discard(selector)

    def set_element_enabled(self, selector: str, enabled: bool = True) -> None:
        """Set element enabled state (for testing)."""
        if enabled:
            self._enabled_elements.add(selector)
        else:
            self._enabled_elements.discard(selector)

    def get_form_data(self) -> Dict[str, str]:
        """Get form data filled during workflow execution."""
        return self._form_data.copy()

    def get_interactions(self) -> List[Dict[str, Any]]:
        """Get list of all interactions."""
        return self._interactions.copy()

    def reset(self) -> None:
        """Reset mock page state."""
        self.url = "about:blank"
        self.title = "Mock Page"
        self._form_data.clear()
        self._navigation_history.clear()
        self._interactions.clear()
        self._visible_elements.clear()
        self._enabled_elements.clear()
        self._element_attributes.clear()
        self._element_text.clear()


def create_mock_page() -> MockPage:
    """Factory function to create a new mock page."""
    return MockPage()
