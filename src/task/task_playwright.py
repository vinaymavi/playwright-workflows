from playwright.sync_api import Page
from prefect import task
from pathlib import Path
from util.artifacts import new_artifact_path


@task(log_prints=True)
def open_page(page: Page, url: str, selector: str):

    response = page.goto(url)
    print(
        f"Page URL: {page.url}; HTTP status: {response.status if response else 'unknown'}"
    )
    page.locator(selector).wait_for(state="visible")


@task(log_prints=True)
def screenshot(page: Page, path: str | Path | None = None, slug: str = "page"):
    if path is None:
        path = new_artifact_path(slug)
    page.screenshot(path=path, full_page=True, timeout=5000)
    print(f"Screenshot saved to {Path(path).resolve()}")
