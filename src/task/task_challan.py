from playwright.sync_api import Page
from prefect import task
from pathlib import Path
from functools import partial
from util.playwright import interact as interact_with_page


@task(log_prints=True)
def fill_challan_details(
    page: Page,
    department: str,
    division: str,
    treasury: str,
    remarks: str,
    depositor_name: str,
    block_no: str,
    locality: str,
    city: str,
) -> None:
    """Fill the challan fields using the dropdowns' visible labels."""
    interact = partial(interact_with_page, page)

    interact(lambda: page.locator("#ddlDepartment").select_option(label=department), "department")
    interact(lambda: page.locator("#ddlDivision").select_option(label=division), "division")
    interact(lambda: page.locator("#ddlDistrict").select_option(label=treasury), "treasury")
    interact(lambda: page.locator("#txtRemarks").fill(remarks), "remarks")
    interact(lambda: page.locator("#txtName").fill(depositor_name), "depositor-name")
    interact(lambda: page.locator("#txtBlockNo").fill(block_no), "block-no")
    interact(lambda: page.locator("tr").filter(has_text="Locality/Road").locator("input").fill(locality), "locality")
    interact(lambda: page.locator("#txtCity").fill(city), "city")


@task(log_prints=True)
def fill_amount_and_calculate_total(page: Page, amount: str) -> None:
    """Fill the second head, which appears after choosing a department."""
    page.locator("#txtAmt2").fill(amount)
    page.locator("#cmdTotal").click()


@task(log_prints=True)
def capture_captcha(page: Page, path: str) -> str:
    """Save the CAPTCHA for a person to read and return its absolute path."""
    output = Path(path).resolve()
    page.locator("#imgCaptcha").screenshot(path=output)
    return str(output)


@task(log_prints=True)
def goto_pay_without_registration(page: Page) -> None:
    """Open the home page, navigate to the payment form, and verify it loaded."""
    response = page.goto("https://rajkosh.up.nic.in/Default.aspx")
    print(
        f"Home page URL: {page.url}; HTTP status: {response.status if response else 'unknown'}"
    )
    page.get_by_role("link", name="Pay Without Registration").click()
    page.locator("#ddlDepartment").wait_for(state="visible")
