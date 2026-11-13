import os
from collections.abc import Callable
from weakref import WeakKeyDictionary

from playwright.sync_api import Page
from prefect.utilities.annotations import quote

from task.task_playwright import screenshot as page_screenshot
from util.artifacts import new_artifact_path


_traced_pages: WeakKeyDictionary[Page, bool] = WeakKeyDictionary()


def get_page() -> Page:
    """Create a page and start tracing before navigation in debug mode."""
    from browser.browser import browser

    page = browser.get_page()
    try:
        if os.getenv("DEBUG_MODE") == "1":
            page.context.tracing.start(screenshots=True, snapshots=True, sources=True)
            _traced_pages[page] = True
        return page
    except Exception:
        page.close()
        raise


def close_page(page: Page) -> None:
    """Save an active trace and close the page even if saving fails."""
    try:
        if _traced_pages.pop(page, False):
            path = new_artifact_path("trace", "zip")
            page.context.tracing.stop(path=path)
            print(f"Trace saved to {path.resolve()}")
    finally:
        page.close()


def select_with_postback(page: Page, selector: str, label: str) -> None:
    """Select an option and wait for the resulting page navigation."""
    with page.expect_navigation(wait_until="load"):
        page.locator(selector).select_option(label=label)


def interact(
    page: Page,
    action: Callable[[], object],
    slug: str,
) -> None:
    """Perform a form interaction and optionally capture its result."""
    action()
    if os.getenv("DEBUG_MODE") == "1":
        page_screenshot(quote(page), slug=slug)
