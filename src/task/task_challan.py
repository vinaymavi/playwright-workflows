from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from prefect import task
from pathlib import Path
from functools import partial
import pytesseract
from util.playwright import interact as interact_with_page
from util.playwright import select_with_postback
from util.playwright import capture_element


class RajkoshSubmissionError(RuntimeError):
    """The submission returned a Rajkosh error page."""


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

    interact(
        lambda: select_with_postback(page, "#ddlDepartment", department), "department"
    )
    interact(lambda: select_with_postback(page, "#ddlDivision", division), "division")
    interact(
        lambda: page.locator("#ddlDistrict").select_option(label=treasury), "treasury"
    )
    interact(lambda: page.locator("#txtRemarks").fill(remarks), "remarks")
    interact(lambda: page.locator("#txtName").fill(depositor_name), "depositor-name")
    interact(lambda: page.locator("#txtBlockNo").fill(block_no), "block-no")
    interact(lambda: page.locator("#txtRoad").fill(locality), "locality")
    interact(lambda: page.locator("#txtCity").fill(city), "city")


@task(log_prints=True)
def fill_amount_and_calculate_total(page: Page, amount: str) -> None:
    """Fill the second head, which appears after choosing a department."""
    interact = partial(interact_with_page, page)
    interact(lambda: page.locator("#txtAmt2").fill(amount), "amount")
    interact(lambda: page.locator("#cmdTotal").click(), "total")


@task(log_prints=True)
def capture_captcha(page: Page, path: str) -> str:
    """Save the CAPTCHA for a person to read and return its absolute path."""
    output = Path(path).resolve()
    page.locator("#imgCaptcha").screenshot(path=output)
    return str(output)


@task(log_prints=True, retries=0)
def solve_and_submit_captcha(page: Page, captcha_path: str) -> str:
    """Submit one OCR reading; let the flow retry on failure."""
    alerts: list[str] = []

    def handle_dialog(dialog) -> None:
        alerts.append(dialog.message)
        dialog.accept()

    page.on("dialog", handle_dialog)
    try:
        text = pytesseract.image_to_string(captcha_path, config="--psm 7").strip()
        if not text:
            raise ValueError("OCR could not read the CAPTCHA image")
        page.locator("#txtVerify").fill(text)
        try:
            with page.expect_navigation(wait_until="load", timeout=30000):
                page.locator("#btnSubmit").click()
        except PlaywrightTimeoutError:
            if alerts:
                raise RajkoshSubmissionError(f"Website alert: {alerts[-1]}") from None
            raise
        if alerts:
            raise RajkoshSubmissionError(f"Website alert: {alerts[-1]}")
        if "page error" in page.locator("body").inner_text().lower():
            raise RajkoshSubmissionError("Rajkosh returned an error page after submission")
        if page.locator("#txtVerify").count():
            raise RuntimeError("The form is still displayed; submission could not be verified")
        return page.url
    finally:
        page.remove_listener("dialog", handle_dialog)


@task(log_prints=True, retries=0)
def prepare_upi_payment(page: Page) -> str:
    """Proceed to the UPI QR code and save it for the user to scan."""
    page.locator("#popDiv").get_by_role("link", name="Close").click()
    challan_number = page.locator("#txtChallan_no").input_value().strip()
    if not challan_number:
        raise RuntimeError("Challan number is missing from the confirmation page")
    print(f"Challan number: {challan_number}")
    page.locator("#btnProceed").click()
    page.locator('a[onclick="paySubmitUPI(\'UPI\')"]:visible').last.dispatch_event("click")
    page.locator("#Go").click()
    path = capture_element(page, "#qrcodeImg", "upi-qr")
    print(f"UPI QR code saved to {path}")
    return path


@task(log_prints=True)
def goto_pay_without_registration(page: Page) -> None:
    """Open the home page, navigate to the payment form, and verify it loaded."""
    response = page.goto("https://rajkosh.up.nic.in/Default.aspx")
    print(
        f"Home page URL: {page.url}; HTTP status: {response.status if response else 'unknown'}"
    )
    page.get_by_role("link", name="Pay Without Registration").click()
    page.locator("#ddlDepartment").wait_for(state="visible")
