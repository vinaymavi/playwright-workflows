import os
import argparse

from prefect.blocks.system import Secret
from sqlalchemy import true


parser = argparse.ArgumentParser(description="Create a Prefect Secret block.")
parser.add_argument(
    "name", nargs="?", default="prefect-secret", help="Secret block name"
)
args = parser.parse_args()

secret_value = os.environ.get("PREFECT_SECRET")
if not secret_value:
    raise ValueError("PREFECT_SECRET must be set and non-empty")

Secret(value=secret_value).save(args.name, overwrite=true)
print(f"Secret block '{args.name}' created successfully.")
