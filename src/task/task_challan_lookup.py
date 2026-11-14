"""Search Rajkosh and render the printable challan as a PDF."""

from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from prefect import get_run_logger, task

from util.artifacts import new_artifact_path, upload_file_to_gcs
from util.email import send_email


@task(log_prints=True, retries=0)
def search_challan(page: Page, challan_number: str) -> str:
    page.goto("https://rajkosh.up.nic.in/Default.aspx")
    page.get_by_role("link", name="Search and Print Challan").click()
    page.locator("#txtChallanNo").fill(challan_number)
    # The page can shift under a mouse click when the challan field blurs.
    page.locator("#btnSearch").focus()
    page.locator("#btnSearch").press("Enter")
    result = page.locator("#GridViewChallan").get_by_text(challan_number, exact=True)
    try:
        result.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(f"Rajkosh did not return a result for challan {challan_number}") from exc
    row_text = result.locator("xpath=ancestor::tr[1]").inner_text()
    get_run_logger().info("Challan search result: %s", row_text)
    result.click()
    page.locator("#btnPrint").wait_for(state="visible")
    return row_text


@task(log_prints=True, retries=0)
def generate_challan_pdf(page: Page, challan_number: str) -> str:
    with page.expect_popup() as popup_info:
        page.locator("#btnPrint").click()
    popup = popup_info.value
    try:
        popup.wait_for_load_state("load")
        popup.get_by_text(challan_number, exact=False).first.wait_for(state="visible")
        popup.emulate_media(media="print")
        path = new_artifact_path("challan", "pdf")
        popup.pdf(path=path, format="A4", print_background=True)
        get_run_logger().info("Challan PDF saved to %s", path.resolve())
        return str(path.resolve())
    finally:
        popup.close()


@task(log_prints=True, retries=0)
def upload_challan_pdf(path: str) -> str:
    artifact_id = upload_file_to_gcs(path, key="challan-pdf")
    return str(artifact_id)


@task(log_prints=True, retries=0)
def email_challan_pdf(path: str, challan_number: str, recipient: str, sender: str) -> str:
    result = send_email(
        recipient=recipient,
        sender=sender,
        subject=f"Challan {challan_number}",
        text=f"The requested challan {challan_number} is attached. Please check the document for its payment status.",
        attachments=[Path(path)],
    )
    message_id = result.get("id")
    if not isinstance(message_id, str) or not message_id:
        raise RuntimeError("Resend returned no email ID")
    get_run_logger().info("Challan email accepted by Resend; ID: %s", message_id)
    return message_id
