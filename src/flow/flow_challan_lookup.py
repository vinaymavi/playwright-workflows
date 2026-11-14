"""Retrieve, store, and email a Rajkosh challan copy."""

from prefect import flow
from prefect.utilities.annotations import quote

from task.task_challan_lookup import (
    email_challan_pdf,
    generate_challan_pdf,
    search_challan,
    upload_challan_pdf,
)
from util.playwright import close_page, get_page


@flow(log_prints=True, flow_run_name="challan-copy-{challan_number}", retries=0)
def flow_challan_lookup(
    challan_number: str,
    recipient: str = "vinaymavi@gmail.com",
    sender: str = "onboarding@resend.dev",
) -> str:
    challan_number = challan_number.strip()
    if not challan_number:
        raise ValueError("challan_number must not be empty")
    page = get_page()
    try:
        wrapped_page = quote(page)
        search_challan(wrapped_page, challan_number)
        pdf_path = generate_challan_pdf(wrapped_page, challan_number)
        upload_challan_pdf(pdf_path)
        email_challan_pdf(pdf_path, challan_number, recipient, sender)
        return pdf_path
    finally:
        close_page(page)
