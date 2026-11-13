import os
from collections.abc import Callable

from playwright.sync_api import Page
from prefect.utilities.annotations import quote

from task.task_playwright import screenshot as page_screenshot


def interact(
    page: Page,
    action: Callable[[], object],
    slug: str,
) -> None:
    """Perform a form interaction and optionally capture its result."""
    action()
    if os.getenv("DEBUG_MODE") == "1":
        page_screenshot(quote(page), slug=slug)
