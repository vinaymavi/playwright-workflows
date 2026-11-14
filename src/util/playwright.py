import os
import warnings
from collections.abc import Callable
from weakref import WeakKeyDictionary

from playwright.sync_api import Page
from pathlib import Path
from prefect import get_run_logger
from prefect.utilities.annotations import quote

from task.task_playwright import screenshot as page_screenshot
from util.artifacts import new_artifact_path, upload_file_to_gcs


_traced_pages: WeakKeyDictionary[Page, bool] = WeakKeyDictionary()


def capture_element(page: Page, selector: str, slug: str) -> str:
    """Save a screenshot of one page element and return its path."""
    path = new_artifact_path(slug)
    page.locator(selector).screenshot(path=path)
    return str(Path(path).resolve())


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
            logger = get_run_logger()
            path = new_artifact_path("trace", "zip")
            page.context.tracing.stop(path=path)
            logger.info("Trace saved to %s", path.resolve())
            try:
                artifact_id = upload_file_to_gcs(path, key="challan-trace")
                logger.info("Trace uploaded; Prefect artifact ID: %s", artifact_id)
            except Exception:
                logger.warning("Trace upload failed; local file remains at %s", path.resolve(), exc_info=True)
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
    """Deprecated: use direct Playwright actions and a debug trace instead."""
    warnings.warn(
        "interact is deprecated; use direct Playwright actions and tracing",
        DeprecationWarning,
        stacklevel=2,
    )
    action()
    if os.getenv("DEBUG_MODE") == "1":
        page_screenshot(quote(page), slug=slug)
