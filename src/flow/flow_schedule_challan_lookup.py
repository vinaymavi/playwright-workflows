"""Schedule a challan lookup after Rajkosh creates a challan."""

from datetime import datetime, timedelta, timezone

from prefect import flow, get_run_logger
from prefect.deployments import run_deployment

LOOKUP_DEPLOYMENT = "flow-challan-lookup/challan-lookup-local"
LOOKUP_DELAY = timedelta(minutes=2)


@flow(log_prints=True, retries=2, retry_delay_seconds=10)
def flow_schedule_challan_lookup(challan_number: str) -> None:
    challan_number = challan_number.strip()
    if not challan_number:
        raise ValueError("challan_number must not be empty")

    scheduled_time = datetime.now(timezone.utc) + LOOKUP_DELAY
    run = run_deployment(
        name=LOOKUP_DEPLOYMENT,
        parameters={"challan_number": challan_number},
        scheduled_time=scheduled_time,
        timeout=0,
        idempotency_key=f"challan-lookup/{challan_number}",
        as_subflow=False,
    )
    get_run_logger().info(
        "Lookup run %s for challan %s scheduled for %s",
        run.id, challan_number, run.expected_start_time,
    )
