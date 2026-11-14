from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from prefect import get_run_logger, task
from pathlib import Path
import pytesseract
from util.artifacts import upload_file_to_gcs
from util.email import send_email
from util.email_templates import challan_payment_email
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
    select_with_postback(page, "#ddlDepartment", department)
    select_with_postback(page, "#ddlDivision", division)
    page.locator("#ddlDistrict").select_option(label=treasury)
    page.locator("#txtRemarks").fill(remarks)
    page.locator("#txtName").fill(depositor_name)
    page.locator("#txtBlockNo").fill(block_no)
    page.locator("#txtRoad").fill(locality)
    page.locator("#txtCity").fill(city)


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
def prepare_upi_payment(page: Page, amount: str, recipient: str = "vinaymavi@gmail.com") -> str:
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
    logger = get_run_logger()
    logger.info("UPI QR code saved to %s", path)
    try:
        response = send_email(
            recipient=recipient,
            sender="onboarding@resend.dev",
            subject=f"Payment QR for challan {challan_number}",
            html=challan_payment_email(amount, challan_number),
            text=f"Challan {challan_number}: pay ₹{amount} using the attached UPI QR code. The QR may expire; payment is not yet confirmed.",
            attachments=[path],
            idempotency_key=f"challan-qr/{challan_number}",
        )
        logger.info("Resend accepted UPI QR email; message ID: %s", response.get("id", "not provided"))
    except Exception:
        logger.warning("UPI QR email failed; local image remains at %s", path, exc_info=True)
    try:
        artifact_id = upload_file_to_gcs(path, key="challan-upi-qr")
        logger.info("UPI QR uploaded; Prefect artifact ID: %s", artifact_id)
    except Exception:
        logger.warning("UPI QR upload failed; local file remains at %s", path, exc_info=True)
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
