from prefect import flow
from task.task_challan import (
    capture_captcha,
    goto_pay_without_registration,
    fill_amount_and_calculate_total,
    fill_challan_details,
    solve_and_submit_captcha,
    prepare_upi_payment,
)

from task.task_playwright import screenshot as page_screenshot
from prefect.utilities.annotations import quote
from util.artifacts import new_artifact_path
from util.playwright import close_page, get_page


# TODO: Make the workflow retry count configurable.
WORKFLOW_RETRIES = 3


@flow(log_prints=True, retries=WORKFLOW_RETRIES)
def flow_challan(
    department: str,
    division: str,
    treasury: str,
    remarks: str,
    depositor_name: str,
    block_no: str,
    locality: str,
    city: str,
    amount: str,
) -> str:
    page = get_page()
    quote_page = quote(page)
    try:
        goto_pay_without_registration(quote_page)
        page_screenshot(quote_page)

        fill_challan_details(
            quote_page,
            department,
            division,
            treasury,
            remarks,
            depositor_name,
            block_no,
            locality,
            city,
        )

        fill_amount_and_calculate_total(quote_page, amount)

        captcha_path = capture_captcha(quote_page, str(new_artifact_path("captcha")))
        solve_and_submit_captcha(quote_page, captcha_path)
        return prepare_upi_payment(quote_page, amount)
    except Exception:
        try:
            screenshot = new_artifact_path("error")
            page.screenshot(path=screenshot, full_page=True, timeout=5000)
            print(f"Failure screenshot saved to {screenshot.resolve()}")
        except Exception as exc:
            print(f"Could not capture failure screenshot: {exc}")
        raise
    finally:
        close_page(page)
