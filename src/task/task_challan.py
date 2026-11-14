from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from prefect import get_run_logger, task
from prefect.events import emit_event
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse
import pytesseract
from util.artifacts import upload_file_to_gcs
from util.email import send_email
from util.email_templates import challan_payment_email
from util.playwright import select_with_postback
from util.playwright import capture_element


class RajkoshSubmissionError(RuntimeError):
    """The submission returned a Rajkosh error page."""


def wait_for_upi_result(page: Page) -> None:
    """Keep the SBI page alive until its status changes or countdown ends."""
    logger = get_run_logger()
    initial_url = page.url
    deadline = monotonic() + 420  # Fallback if SBI does not expose its countdown.
    initial_status = None
    logger.info("Waiting on the SBI payment page for payment or countdown expiry")

    while monotonic() < deadline:
        if page.url != initial_url:
            try:
                page.wait_for_load_state("load", timeout=15000)
            except PlaywrightTimeoutError:
                logger.warning("Payment page navigated, but the destination is still loading")
            logger.info("Payment page navigated to %s", page.url)
            if page.get_by_label("Redirect to Merchant site").count():
                status = page.locator("p.lblGryText").filter(
                    has_text="Transaction"
                ).locator("xpath=following-sibling::p[1]")
                if status.count():
                    logger.info("SBI transaction status: %s", status.first.inner_text().strip())
                logger.info("Waiting for SBI to return the browser to the merchant")
                try:
                    page.wait_for_url(
                        lambda url: urlparse(url).hostname != "merchant.sbi.bank.in",
                        wait_until="load",
                        timeout=60000,
                    )
                    logger.info("SBI returned the browser to %s", page.url)
                except PlaywrightTimeoutError:
                    logger.warning("SBI did not return to the merchant within 60 seconds")
            return

        try:
            state = page.evaluate("""() => {
                const elements = [...document.querySelectorAll('body *')];
                const label = elements.find(el => el.children.length === 0 &&
                    el.textContent.trim().toLowerCase() === 'transaction status');
                const value = label?.nextElementSibling || label?.parentElement?.nextElementSibling;
                const timer = elements.find(el => el.children.length === 0 &&
                    /^\\s*\\d{1,2}:\\d{2}\\s*(?:mins?)?\\s*$/i.test(el.textContent));
                return {status: value?.innerText?.trim() || null,
                        timer: timer?.textContent?.trim() || null};
            }""")
        except Exception:
            # Navigations temporarily destroy the execution context.
            if page.is_closed():
                logger.warning("SBI payment page was closed before a result was observed")
                return
            page.wait_for_timeout(1000)
            continue

        status = state["status"]
        if status:
            if initial_status is None:
                initial_status = status
                logger.info("Initial SBI transaction status: %s", status)
                if any(word in status.lower() for word in ("paid", "completed", "failed", "expired")):
                    logger.info("SBI transaction is already in a terminal state: %s", status)
                    return
            elif status != initial_status:
                logger.info("SBI transaction status changed: %s", status)
                return
        if state["timer"]:
            minutes, seconds = state["timer"].split()[0].split(":")
            if int(minutes) == 0 and int(seconds) == 0:
                logger.info("SBI payment countdown expired")
                return
        page.wait_for_timeout(1000)

    logger.warning("Stopped waiting after seven minutes; check the payment status on Rajkosh")


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
    # The challan already exists at this point. Do not retry payment creation if
    # event delivery fails; that could create another challan.
    try:
        event = emit_event(
            event="rajkosh.challan.created",
            resource={"prefect.resource.id": f"rajkosh.challan.{challan_number}"},
            payload={"challan_number": challan_number},
        )
        if event is None:
            raise RuntimeError("Prefect event emission is disabled")
        get_run_logger().info("Emitted challan-created event for %s", challan_number)
    except Exception:
        get_run_logger().exception(
            "Could not emit challan-created event for %s; schedule the lookup manually",
            challan_number,
        )
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
    try:
        wait_for_upi_result(page)
    except Exception:
        # Retrying the full flow after a challan is created can create another one.
        logger.exception("Could not observe the SBI payment result for challan %s", challan_number)
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
