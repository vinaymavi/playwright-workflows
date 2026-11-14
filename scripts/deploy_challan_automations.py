"""Register challan deployments and the event-triggered automation."""

import argparse
from pathlib import Path

from prefect import flow

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("work_pool", help="Existing Prefect process work pool")
args = parser.parse_args()

project_root = Path(__file__).resolve().parent.parent

lookup = flow.from_source(
    source=project_root,
    entrypoint="src/flow/flow_challan_lookup.py:flow_challan_lookup",
)
lookup.deploy(name="challan-lookup-local", work_pool_name=args.work_pool)

scheduler = flow.from_source(
    source=project_root,
    entrypoint="src/flow/flow_schedule_challan_lookup.py:flow_schedule_challan_lookup",
)
scheduler.deploy(
    name="challan-lookup-scheduler-local",
    work_pool_name=args.work_pool,
    triggers=[{
        "name": "Schedule lookup after challan creation",
        "expect": ["rajkosh.challan.created"],
        "parameters": {"challan_number": "{{ event.payload.challan_number }}"},
    }],
)
